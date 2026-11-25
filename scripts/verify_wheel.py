"""Verify a built Nexus wheel without extracting it; emit local inventory."""
import argparse
import base64
import csv
import hashlib
import io
import json
import re
import stat
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


def inspect_wheel(path):
    path=Path(path)
    if path.stat().st_size>16*1024*1024:raise ValueError("oversized wheel")
    with ZipFile(path) as z:
        infos=z.infolist();names=[x.filename for x in infos]
        if len(set(names))!=len(names) or len(names)>128 or sum(x.file_size for x in infos)>16*1024*1024:
            raise ValueError("invalid wheel inventory")
        for item in infos:
            n=item.filename
            if (item.is_dir() or "\\" in n or n.startswith("/") or
                    any(p in ("",".","..") for p in n.split("/")) or
                    stat.S_ISLNK(item.external_attr>>16)):
                raise ValueError("unsafe member")
            if not (n.startswith("nexus_engine/") or re.fullmatch(r"nexus_engine-[^/]+\.dist-info/.+",n)):
                raise ValueError("unexpected wheel member")
        metadata=[n for n in names if n.endswith(".dist-info/METADATA")]
        records=[n for n in names if n.endswith(".dist-info/RECORD")]
        if len(metadata)!=1 or len(records)!=1:raise ValueError("invalid metadata layout")
        meta=BytesParser().parsebytes(z.read(metadata[0]))
        if meta["Name"]!="nexus-engine" or meta.get_all("Requires-Dist"):
            raise ValueError("unexpected package or dependency")
        version=meta["Version"]
        if path.name!=f"nexus_engine-{version}-py3-none-any.whl":raise ValueError("wheel identity mismatch")
        rec=records[0]
        rows=list(csv.reader(io.StringIO(z.read(rec).decode("utf-8"))))
        if any(len(r)!=3 for r in rows) or len(rows)!=len(names) or {r[0] for r in rows}!=set(names):
            raise ValueError("RECORD inventory mismatch")
        inventory=[]
        for name,encoded,size in rows:
            data=z.read(name);sha=hashlib.sha256(data)
            if name==rec:
                if encoded or size:raise ValueError("unexpected RECORD self hash")
            elif encoded!="sha256="+base64.urlsafe_b64encode(sha.digest()).decode().rstrip("=") or size!=str(len(data)):
                raise ValueError("RECORD hash mismatch")
            inventory.append({"path":name,"size":len(data),"sha256":sha.hexdigest()})
    return {"schema":1,"name":"nexus-engine","version":version,
            "wheel":path.name,"wheel_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "runtime_dependencies":[],"files":sorted(inventory,key=lambda r:r["path"]),
            "scope":"local package inventory and RECORD verification, not a signature or vulnerability audit"}


def main():
    p=argparse.ArgumentParser();p.add_argument("wheel",type=Path);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(inspect_wheel(a.wheel),indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":main()
