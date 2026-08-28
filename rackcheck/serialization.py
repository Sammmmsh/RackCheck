"""Strict, size-limited external JSON input."""
import json
from pathlib import Path


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key: " + key)
        value[key] = item
    return value


def _constant(value):
    raise ValueError("Non-finite JSON number is not permitted: " + value)


def loads(content):
    return json.loads(content, object_pairs_hook=_object, parse_constant=_constant)


def read_text(path, maximum):
    p = Path(path)
    if not p.is_file():
        raise ValueError("Input must be a regular file: " + str(p))
    with p.open("rb") as stream:
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError(f"Input exceeds {maximum} bytes: {p}")
    return content.decode("utf-8-sig")
