import os
from pathlib import Path
import tempfile
from .models import Snapshot
from .serialization import loads, read_text


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
    return Snapshot.from_dict(loads(read_text(path, 16_777_216)))
