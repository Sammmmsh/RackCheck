"""Internal subprocess entry point; not a user-facing command."""

import json
import sys
from .probes import probe


def main():
    payload = json.loads(sys.argv[1])
    print(json.dumps(probe(payload["kind"], payload["target"], payload["timeout"])))


if __name__ == "__main__":
    main()
