"""Consistent SQLite snapshots; restored copies are inspection-only."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from .contracts import Rejected
from .store import Store


def snapshot(source,destination,*,seal=False):
    source,destination=Path(source),Path(destination)
    if not source.is_file() or source.is_symlink() or not destination.parent.is_dir():
        raise Rejected("existing private source and destination parent required")
    if source.resolve()==destination.resolve():
        raise Rejected("source and destination must differ")
    fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(fd)
    try:
        uri=source.resolve().as_uri()+"?mode=ro"
        with closing(sqlite3.connect(uri,uri=True,timeout=10)) as src:
            with closing(sqlite3.connect(destination,timeout=10)) as dst:
                src.backup(dst)
        restored=Store(destination)
        with restored.transaction() as c:
            c.execute("INSERT OR IGNORE INTO recovery_hold VALUES (1)")
        info=restored.verify_all()
        return {"path":str(destination),"kind":"restored" if seal else "backup",**info}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
