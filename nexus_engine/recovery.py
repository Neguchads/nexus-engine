"""Consistent SQLite snapshots; restored copies are inspection-only in alpha 4."""
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from .contracts import Rejected
from .store import Store


def snapshot(source,destination,*,seal=False):
    source,destination=Path(source),Path(destination)
    if not source.is_file() or source.is_symlink() or not destination.parent.is_dir():
        raise Rejected("existing private source and destination parent required")
    if source.resolve()==destination.resolve() or destination.exists() or destination.is_symlink():
        raise Rejected("destination must be a new path")
    # Prepare and seal privately, then publish without overwriting via a hard link.
    # On filesystems without hard links, fail closed rather than publish a partial copy.
    with tempfile.TemporaryDirectory(prefix=".nexus-snapshot-",dir=destination.parent) as tmp:
        staged=Path(tmp)/"snapshot.db"
        uri=source.resolve().as_uri()+"?mode=ro"
        with closing(sqlite3.connect(uri,uri=True,timeout=10)) as src:
            names={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"runs","steps","abandoned"}<=names:
                raise Rejected("source is not a Nexus database")
            with closing(sqlite3.connect(staged,timeout=10)) as dst:
                src.backup(dst)
        os.chmod(staged,0o600)
        restored=Store(staged)
        with restored.transaction() as c:
            c.execute("INSERT OR IGNORE INTO recovery_hold VALUES (1)")
        info=restored.verify_all()
        with staged.open("rb") as f:
            os.fsync(f.fileno())
        os.link(staged,destination)
    return {"path":str(destination),"kind":"restored" if seal else "backup",**info}
