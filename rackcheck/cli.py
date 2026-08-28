import argparse
import json
import sys
from . import __version__
from .config import ConfigError, load_config


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rackcheck")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate and normalize configuration")
    validate.add_argument("config")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            print(json.dumps(load_config(args.config), indent=2))
        return 0
    except (ConfigError, OSError) as exc:
        print(f"rackcheck: {exc}", file=sys.stderr)
        return 2
