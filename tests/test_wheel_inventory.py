import base64
import csv
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from scripts.verify_wheel import inspect_wheel


def build(path,*,bad=False,unsafe=False):
    info="nexus_engine-0.1.0a7.dist-info/"
    files={"nexus_engine/__init__.py":b"__version__='0.1.0a7'",
           info+"METADATA":b"Metadata-Version: 2.1\nName: nexus-engine\nVersion: 0.1.0a7\n",
           info+"WHEEL":b"Wheel-Version: 1.0\nTag: py3-none-any\n"}
    if unsafe:files["nexus_engine/../bad.py"]=b"x"
    out=io.StringIO();writer=csv.writer(out)
    for name,data in files.items():
        h=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        writer.writerow((name,"sha256="+("bad" if bad else h),len(data)))
    writer.writerow((info+"RECORD","",""))
    files[info+"RECORD"]=out.getvalue().encode()
    with ZipFile(path,"w") as z:
        for name,data in files.items():z.writestr(name,data)


class WheelInventoryTests(unittest.TestCase):
    def test_inventory_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"nexus_engine-0.1.0a7-py3-none-any.whl"
            build(p);r=inspect_wheel(p)
            self.assertEqual(r["version"],"0.1.0a7");self.assertEqual(r["runtime_dependencies"],[])
            build(p,bad=True)
            with self.assertRaisesRegex(ValueError,"hash mismatch"):inspect_wheel(p)
            build(p,unsafe=True)
            with self.assertRaisesRegex(ValueError,"unsafe member"):inspect_wheel(p)
