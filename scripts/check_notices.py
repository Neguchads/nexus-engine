"""Verify the exact legal notices from the checkout are present in the wheel."""
import argparse
from pathlib import Path
from zipfile import ZipFile


def check(wheel,root):
    with ZipFile(wheel) as z:
        for notice in ("LICENSE","CREDITS.md"):
            members=[n for n in z.namelist() if ".dist-info/" in n and n.rsplit("/",1)[-1]==notice]
            if len(members)!=1:
                raise ValueError("missing or ambiguous notice: "+notice)
            # Normalize text line endings across platform checkouts.
            shipped=z.read(members[0]).decode("utf-8").replace("\r\n","\n")
            if shipped!=(root/notice).read_text(encoding="utf-8"):
                raise ValueError("notice mismatch: "+notice)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("wheel",type=Path);a=p.parse_args()
    check(a.wheel,Path(__file__).resolve().parents[1])
    print("LICENSE and CREDITS.md match the checkout")
