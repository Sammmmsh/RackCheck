import json
import os
from pathlib import Path
import tempfile
from .models import Snapshot


def write_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_snapshot(path):
    p = Path(path)
    if p.stat().st_size > 16_777_216:
        raise ValueError("Snapshot is larger than 16 MiB")
    return Snapshot.from_dict(json.loads(p.read_text(encoding="utf-8")))
