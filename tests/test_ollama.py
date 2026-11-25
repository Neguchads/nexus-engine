import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from nexus_engine.contracts import Rejected
from nexus_engine.ollama import execute, step
from nexus_engine.store import Store


def plan(host="ollama"):
    return {"host":host,"budget":100,"resume":True,"nodes":[{"id":"task","depends_on":[],
            "input":{"model":"local:7b","task":"Return JSON."},"max_tokens":100}]}


def server(**overrides):
    result={"done":True,"done_reason":"stop","model":"local:7b","response":"{\"ok\":true}",
            "prompt_eval_count":10,"eval_count":5}
    result.update(overrides)
    conn=MagicMock();res=conn.getresponse.return_value;res.status=200
    res.read.return_value=json.dumps(result).encode()
    return conn


class LocalAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/"state.db")

    def test_explicit_loopback(self):
        self.store.start("r",plan());conn=server()
        with patch("nexus_engine.ollama.http.client.HTTPConnection",return_value=conn) as connect:
            status=step(self.store,"r",self.store.preview("r")["approval_sha256"])
        connect.assert_called_once_with("127.0.0.1",11434,timeout=60)
        self.assertEqual(conn.request.call_args.args[:2],("POST","/api/generate"))
        self.assertEqual(status["outputs"],{"task":{"ok":True}})
        self.assertEqual(status["reserved_or_reported"],15)
        conn.close.assert_called_once()

    def test_mismatch_does_not_reserve_or_call(self):
        self.store.start("r",plan("codex"))
        with patch("nexus_engine.ollama.http.client.HTTPConnection") as connect:
            with self.assertRaises(Rejected):step(self.store,"r",self.store.preview("r")["approval_sha256"])
            connect.assert_not_called()
        self.assertEqual(self.store.status("r")["pending"],[])

    def test_overbudget_or_timeout_blocks_replay(self):
        self.store.start("r",plan());conn=server(prompt_eval_count=100)
        with patch("nexus_engine.ollama.http.client.HTTPConnection",return_value=conn):
            with self.assertRaises(Rejected):step(self.store,"r",self.store.preview("r")["approval_sha256"])
        self.assertEqual(self.store.status("r")["reserved_or_reported"],100)
        with patch("nexus_engine.ollama.http.client.HTTPConnection") as connect:
            with self.assertRaises(Rejected):step(self.store,"r",self.store.preview("r")["approval_sha256"])
            connect.assert_not_called()

    def test_model_mismatch(self):
        self.store.start("r",plan());req=self.store.next("r",approved=True,approval_sha256=self.store.preview("r")["approval_sha256"])
        with patch("nexus_engine.ollama.http.client.HTTPConnection",return_value=server(model="other:7b")):
            with self.assertRaises(Rejected):execute(req)

    def test_rejects_incomplete_response(self):
        self.store.start("r",plan());req=self.store.next("r",approved=True,approval_sha256=self.store.preview("r")["approval_sha256"])
        with patch("nexus_engine.ollama.http.client.HTTPConnection",return_value=server(done_reason="length")):
            with self.assertRaises(Rejected):execute(req)

    def test_invalid_payload_does_not_reserve(self):
        p=plan();p["nodes"][0]["input"]["model"]="invalid"
        self.store.start("r",p)
        with patch("nexus_engine.ollama.http.client.HTTPConnection") as connect:
            with self.assertRaises(Rejected):step(self.store,"r",self.store.preview("r")["approval_sha256"])
            connect.assert_not_called()
        self.assertEqual(self.store.status("r")["pending"],[])
