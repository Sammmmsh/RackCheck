"""Potentially blocking filesystem syscalls run in a bounded child process."""
import json
import os
import sys


def filesystem_data(path):
    stat = os.statvfs(path)
    used = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
    available = stat.f_bavail * stat.f_frsize
    denominator = used + available
    return {
        "path": path, "is_mount": os.path.ismount(path),
        "total_bytes": stat.f_blocks * stat.f_frsize, "used_bytes": used,
        "available_bytes": available, "used_percent": used * 100 / denominator if denominator else None,
        "inodes_total": stat.f_files, "inodes_free": stat.f_favail,
    }


def main():
    try:
        print(json.dumps(filesystem_data(sys.argv[1]), allow_nan=False))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
