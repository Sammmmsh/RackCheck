"""Opt-in fault lab. Mutations occur only after namespace isolation is verified."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import uuid
from .runner import run


def namespace_ids():
    return {name: os.readlink("/proc/self/ns/" + name) for name in ("user", "mnt", "net")}


def assert_isolated(parent_ids):
    current = namespace_ids()
    if set(parent_ids) != set(current) or any(current[k] == parent_ids[k] for k in current):
        raise ValueError("Lab refused: user, mount and network namespaces must all differ from the launcher")
    return current


def run_lab(output_dir):
    if platform.system() != "Linux":
        raise ValueError("The real fault lab requires Linux/Ubuntu WSL with user, mount and network namespaces. Use demo for offline fixtures.")
    required = ("unshare", "mount", "umount", "ip", "lsblk")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise ValueError("Lab prerequisites missing: " + ", ".join(missing))
    parents = namespace_ids()
    root = Path(output_dir).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = root / ("run-" + stamp + "-" + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True, exist_ok=False)
    argv = ["unshare", "--user", "--map-root-user", "--mount", "--net", "--fork",
            sys.executable, "-m", "rackcheck.lab_worker", str(destination), json.dumps(parents)]
    result = run(argv, timeout=120, max_bytes=262_144)
    if result.status != "ok" or result.returncode:
        raise ValueError("Isolated lab failed; no host-level fallback is permitted. " +
                         (result.detail or result.stderr[-2000:] or result.stdout[-2000:]) +
                         f"\nPartial artifacts, if any: {destination}")
    summary_path = destination / "summary.json"
    if not summary_path.is_file():
        raise ValueError("Lab worker did not produce verification evidence")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("verified") is not True:
        raise ValueError(f"Lab did not verify every fault and recovery; inspect {summary_path}")
    return destination, summary
