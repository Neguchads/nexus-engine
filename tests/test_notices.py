import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from scripts.check_notices import check


class NoticeTests(unittest.TestCase):
    def test_presence_and_exact_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wheel=root/"test.whl"
            for name in ("LICENSE","CREDITS.md"):(root/name).write_text(name+"\n",encoding="utf-8")
            def write(credits):
                with ZipFile(wheel,"w") as z:
                    z.writestr("pkg.dist-info/licenses/LICENSE","LICENSE\n")
                    if credits is not None:z.writestr("pkg.dist-info/licenses/CREDITS.md",credits)
            write("CREDITS.md\n");check(wheel,root)
            write(None)
            with self.assertRaises(ValueError):check(wheel,root)
            write("wrong")
            with self.assertRaises(ValueError):check(wheel,root)
