"""Durable SQLite queue, reservation journal and content-bound checkpoints.

Local owner-controlled storage only. No sandbox or hostile database protection.
One external request or an explicitly bounded deterministic batch; no automatic retries.
"""
import json
import os
import stat
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .contracts import Rejected, digest, encode, identifier, validate, validate_response
from .context import project

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, plan TEXT NOT NULL, fingerprint TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS steps(
 run_id TEXT NOT NULL REFERENCES runs(id), node TEXT NOT NULL,
 request TEXT NOT NULL, request_hash TEXT NOT NULL,
 answer TEXT, answer_hash TEXT, PRIMARY KEY(run_id,node));
CREATE TABLE IF NOT EXISTS abandoned(
 run_id TEXT PRIMARY KEY REFERENCES runs(id), reason TEXT NOT NULL, evidence_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts(
 run_id TEXT NOT NULL, node TEXT NOT NULL, name TEXT NOT NULL,
 content BLOB NOT NULL, sha TEXT NOT NULL, provenance TEXT NOT NULL,
 PRIMARY KEY(run_id,node,name),
 FOREIGN KEY(run_id,node) REFERENCES steps(run_id,node));
CREATE TABLE IF NOT EXISTS recovery_hold(id INTEGER PRIMARY KEY CHECK(id=1));
"""


class Store:
    def __init__(self, path):
        path = Path(path)
        if path.is_symlink() or not path.parent.is_dir():
            raise Rejected("use a private existing database parent")
        if not path.exists():
            try:
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                os.close(fd)
            except FileExistsError:
                pass
        if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
            raise Rejected("database must be a regular local file")
        self.path = path
        with self.transaction() as conn:
            # Mark and validate schema versions; older alpha DBs have version zero.
            version=conn.execute("PRAGMA user_version").fetchone()[0]
            app=conn.execute("PRAGMA application_id").fetchone()[0]
            names={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            allowed={"runs","steps","abandoned","artifacts","recovery_hold"}
            if version not in (0,1) or app not in (0,1313167445) or names-allowed:
                raise Rejected("unknown database format or version")
            if names and not {"runs","steps","abandoned"}<=names:
                raise Rejected("incomplete Nexus database schema")
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute("PRAGMA application_id=1313167445")
            conn.execute("PRAGMA user_version=1")

    @contextmanager
    def transaction(self):
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA trusted_schema=OFF")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _writable(self,c):
        if c.execute("SELECT 1 FROM recovery_hold WHERE id=1").fetchone():
            raise Rejected("recovered snapshot is sealed for inspection")

    def start(self, run_id, plan):
        if not identifier(run_id):
            raise Rejected("invalid run ID")
        plan, _ = validate(plan)
        with self.transaction() as c:
            self._writable(c)
            row = c.execute("SELECT plan,fingerprint FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is not None:
                if row != (encode(plan), digest(plan)):
                    raise Rejected("run identity conflict")
                if not plan["resume"]:
                    raise Rejected("run exists and resume is not enabled")
                return
            c.execute("INSERT INTO runs VALUES (?,?,?)", (run_id,encode(plan),digest(plan)))

    def _load(self, c, run_id):
        row = c.execute("SELECT plan,fingerprint FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise Rejected("unknown run")
        plan, order = validate(json.loads(row[0]))
        if digest(plan) != row[1]:
            raise Rejected("plan integrity failure")
        known = {n["id"]:n for n in order}
        steps = {}
        for key, req, rh, ans, ah in c.execute(
                "SELECT node,request,request_hash,answer,answer_hash FROM steps WHERE run_id=?", (run_id,)):
            request = json.loads(req)
            if key not in known or digest(request) != rh:
                raise Rejected("request integrity failure")
            node = known[key]
            if (request["run_id"] != run_id or request["node"] != key
                    or request["plan_hash"] != row[1] or request["host"] != plan["host"]
                    or request["max_tokens"] != node["max_tokens"] or request["input"] != node["input"]):
                raise Rejected("request does not match plan")
            if ans is None:
                if ah is not None:
                    raise Rejected("invalid pending checkpoint")
                answer = None
            else:
                answer = validate_response(request,json.loads(ans))
                if digest([request,answer]) != ah:
                    raise Rejected("checkpoint integrity failure")
            steps[key] = (request,answer)
        # Validate every completed/pending node against its predecessor outputs.
        pending = 0
        for key,(request,answer) in steps.items():
            deps = known[key]["depends_on"]
            if any(d not in steps or steps[d][1] is None for d in deps):
                raise Rejected("checkpoint dependency failure")
            if request["dependencies"] != project(known[key],{d:steps[d][1]["output"] for d in deps}):
                raise Rejected("checkpoint dependency mismatch")
            pending += answer is None
        if pending > plan.get("workers", 1):
            raise Rejected("pending reservations exceed worker limit")
        charged = sum(r["max_tokens"] if a is None else a["usage"] for r,a in steps.values())
        if charged > plan["budget"]:
            raise Rejected("budget integrity failure")
        return plan,order,steps,charged

    def _abandoned(self, c, run_id):
        row=c.execute("SELECT reason,evidence_hash FROM abandoned WHERE run_id=?", (run_id,)).fetchone()
        if row and digest([run_id,row[0]])!=row[1]:
            raise Rejected("abandonment integrity failure")
        return row is not None

    def _ready(self, c, run_id, expected_host=None):
        plan,order,steps,charged = self._load(c,run_id)
        if self._abandoned(c,run_id):
            raise Rejected("run permanently abandoned")
        if expected_host is not None and plan["host"] != expected_host:
            raise Rejected("selected host mismatch")
        if any(a is None for r,a in steps.values()):
            raise Rejected("unsettled request; reconcile manually, no redispatch")
        ready = [n for n in order if n["id"] not in steps and
                 all(d in steps and steps[d][1] is not None for d in n["depends_on"])]
        return plan,steps,charged,ready

    def _draft(self, plan, steps, run_id, node):
        return {"run_id":run_id,"node":node["id"],"plan_hash":digest(plan),
                "host":plan["host"],"input":node["input"],"max_tokens":node["max_tokens"],
                "dependencies":project(node,{d:steps[d][1]["output"] for d in node["depends_on"]})}

    def _reserve(self, c, draft):
        self._writable(c)
        request = {**draft,"request_id":secrets.token_hex(24)}
        raw = encode(request)
        c.execute("INSERT INTO steps VALUES (?,?,?,?,NULL,NULL)",
                  (draft["run_id"],draft["node"],raw,digest(request)))
        return request

    def preview(self, run_id, *, expected_host=None):
        """Review the exact next payload without dispatching or reserving it."""
        with self.transaction() as c:
            plan,steps,_,ready=self._ready(c,run_id,expected_host)
            if not ready:
                return None
            draft=self._draft(plan,steps,run_id,ready[0])
            return {"payload":draft,"approval_sha256":digest(draft)}

    def next(self, run_id, *, approved=False, approval_sha256=None, expected_host=None):
        with self.transaction() as c:
            plan,steps,charged,ready=self._ready(c,run_id,expected_host)
            if not ready:
                return None
            draft=self._draft(plan,steps,run_id,ready[0])
            if plan["host"] != "fixture" and (
                    not approved or approval_sha256 != digest(draft)):
                raise Rejected("explicit approval matching the preview hash required")
            if charged + draft["max_tokens"] > plan["budget"]:
                raise Rejected("reservation exceeds budget")
            return self._reserve(c,draft)

    def reserve_batch(self, run_id):
        """Atomically reserve a ready frontier for deterministic fixtures only."""
        with self.transaction() as c:
            plan,steps,charged,ready=self._ready(c,run_id,"fixture")
            selected=ready[:plan.get("workers",1)]
            if charged+sum(n["max_tokens"] for n in selected)>plan["budget"]:
                raise Rejected("batch reservation exceeds budget")
            return [self._reserve(c,self._draft(plan,steps,run_id,n)) for n in selected]

    def submit(self, run_id, answer):
        with self.transaction() as c:
            self._writable(c)
            _,_,steps,_ = self._load(c,run_id)
            if self._abandoned(c,run_id):
                raise Rejected("run permanently abandoned")
            if not isinstance(answer,dict):
                raise Rejected("invalid response")
            for key,(request,old) in steps.items():
                if request["request_id"] != answer.get("request_id"):
                    continue
                answer = validate_response(request,answer)
                if old is not None:
                    if old != answer:
                        raise Rejected("conflicting completion")
                    return
                c.execute("UPDATE steps SET answer=?,answer_hash=? WHERE run_id=? AND node=?",
                          (encode(answer),digest([request,answer]),run_id,key))
                return
            raise Rejected("unknown request ID")

    def status(self, run_id):
        with self.transaction() as c:
            plan,order,steps,charged = self._load(c,run_id)
            done = {k:a["output"] for k,(r,a) in steps.items() if a is not None}
            pending = [r["request_id"] for r,a in steps.values() if a is None]
            return {"host":plan["host"],"completed":len(done),"total":len(order),
                    "reserved_or_reported":charged,"budget":plan["budget"],
                    "pending":pending,"outputs":done,"abandoned":self._abandoned(c,run_id)}

    def abandon(self, run_id, reason):
        """Permanent stop; no rollback of external effects or release of uncertain usage."""
        if not isinstance(reason,str) or not reason.strip() or len(reason)>512:
            raise Rejected("bounded abandonment reason required")
        with self.transaction() as c:
            self._writable(c)
            self._load(c,run_id)
            row=c.execute("SELECT reason FROM abandoned WHERE run_id=?", (run_id,)).fetchone()
            if row:
                if row[0]!=reason:
                    raise Rejected("abandonment already recorded")
                return
            c.execute("INSERT INTO abandoned VALUES (?,?,?)",(run_id,reason,digest([run_id,reason])))

    def audit(self, run_id):
        """Metadata-only report; does not disclose task input or output."""
        with self.transaction() as c:
            plan,order,steps,charged=self._load(c,run_id)
            evidence=[]
            for node in order:
                key=node["id"]
                if key not in steps:
                    evidence.append({"node":key,"state":"waiting"})
                    continue
                req,ans=steps[key]
                evidence.append({"node":key,"state":"pending" if ans is None else "done",
                                 "request_sha256":digest(req),
                                 "completion_sha256":None if ans is None else digest([req,ans]),
                                 "reservation":req["max_tokens"],
                                 "usage":None if ans is None else ans["usage"]})
            return {"schema":1,"run_id":run_id,"plan_sha256":digest(plan),
                    "host":plan["host"],"budget":plan["budget"],"reserved_or_reported":charged,
                    "abandoned":self._abandoned(c,run_id),"steps":evidence,
                    "scope":"local integrity and reported accounting; not provider attestation"}

    def context_report(self,run_id):
        from .context import report
        with self.transaction() as c:
            _,order,steps,_=self._load(c,run_id)
            rows=[]
            for n in order:
                if all(d in steps and steps[d][1] is not None for d in n["depends_on"]):
                    rows.append({"node":n["id"],**report(n,{d:steps[d][1]["output"] for d in n["depends_on"]})})
            return rows

    def merge(self,run_id,nodes):
        from .merge import merge_objects
        if not isinstance(nodes,list) or not nodes or any(not identifier(n) for n in nodes) or len(set(nodes))!=len(nodes):
            raise Rejected("unique explicit merge nodes required")
        with self.transaction() as c:
            _,_,steps,_=self._load(c,run_id)
            if any(n not in steps or steps[n][1] is None for n in nodes):
                raise Rejected("merge requires completed nodes in the same run")
            result=merge_objects({n:steps[n][1]["output"] for n in nodes})
            return {"run_id":run_id,"sources":{n:digest([steps[n][0],steps[n][1]]) for n in nodes},
                    "output":result,"sha256":digest(result)}

    def _artifact_record(self,c,run_id,node,name,steps):
        from hashlib import sha256
        row=c.execute("SELECT content,sha,provenance FROM artifacts WHERE run_id=? AND node=? AND name=?",
                      (run_id,node,name)).fetchone()
        if row is None:
            raise Rejected("artifact not found")
        data,sha,provenance=row
        if (node not in steps or steps[node][1] is None or not isinstance(data,bytes)
                or len(data)>1048576 or sha256(data).hexdigest()!=sha
                or provenance!=digest([run_id,node,name,sha,digest([steps[node][0],steps[node][1]])])):
            raise Rejected("artifact integrity failure")
        return data,{"run_id":run_id,"node":node,"name":name,"sha256":sha,
                     "bytes":len(data),"provenance_sha256":provenance}

    def attach(self,run_id,node,name,data):
        from hashlib import sha256
        if not identifier(node) or not identifier(name) or not isinstance(data,bytes) or len(data)>1048576:
            raise Rejected("invalid artifact name or payload")
        with self.transaction() as c:
            self._writable(c)
            _,_,steps,_=self._load(c,run_id)
            if self._abandoned(c,run_id) or node not in steps or steps[node][1] is None:
                raise Rejected("artifact requires completed non-abandoned node")
            sha=sha256(data).hexdigest()
            provenance=digest([run_id,node,name,sha,digest([steps[node][0],steps[node][1]])])
            existing=c.execute("SELECT 1 FROM artifacts WHERE run_id=? AND node=? AND name=?",
                               (run_id,node,name)).fetchone()
            if existing:
                old,meta=self._artifact_record(c,run_id,node,name,steps)
                if old!=data:
                    raise Rejected("immutable artifact conflict")
                return meta
            if c.execute("SELECT COUNT(*) FROM artifacts WHERE run_id=?",(run_id,)).fetchone()[0]>=32:
                raise Rejected("artifact count limit per run")
            c.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?)",(run_id,node,name,data,sha,provenance))
            return self._artifact_record(c,run_id,node,name,steps)[1]

    def artifact(self,run_id,node,name,*,consumer=None):
        """Owner reads explicitly; logical consumer reads only direct predecessors."""
        if not identifier(node) or not identifier(name):
            raise Rejected("invalid artifact identifier")
        with self.transaction() as c:
            _,order,steps,_=self._load(c,run_id)
            if consumer is not None:
                target=next((n for n in order if n["id"]==consumer),None)
                if target is None or node not in target["depends_on"]:
                    raise Rejected("artifact outside consumer dependency scope")
            return self._artifact_record(c,run_id,node,name,steps)

    def verify_all(self):
        with self.transaction() as c:
            if c.execute("PRAGMA quick_check").fetchall()!=[("ok",)] or c.execute("PRAGMA foreign_key_check").fetchall():
                raise Rejected("database integrity failure")
            ids=[r[0] for r in c.execute("SELECT id FROM runs ORDER BY id")]
            count=0
            for run_id in ids:
                _,_,steps,_=self._load(c,run_id)
                self._abandoned(c,run_id)
                for node,name in c.execute("SELECT node,name FROM artifacts WHERE run_id=?",(run_id,)):
                    self._artifact_record(c,run_id,node,name,steps)
                    count+=1
            return {"runs":len(ids),"artifacts":count,
                    "sealed":bool(c.execute("SELECT 1 FROM recovery_hold WHERE id=1").fetchone())}
