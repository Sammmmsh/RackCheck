"""Exit 0=PASS/WARN, 1=FAIL, 2=UNKNOWN/input error; --strict makes WARN exit 1."""
import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .collectors import Collector
from .config import load_config
from .diagnostics import evaluate
from .files import read_snapshot, write_text
from .fixtures import SCENARIOS, scenario
from .reports import compare, render


def output(content, path):
    if path:
        write_text(path, content)
    else:
        print(content, end="" if content.endswith("\n") else "\n")


def parser():
    root = argparse.ArgumentParser(prog="rackcheck", description=__doc__)
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command", required=True)
    valid = sub.add_parser("validate", help="Validate and normalize configuration")
    valid.add_argument("config")
    for name, help_text in (("collect", "Collect a read-only Linux snapshot"),
                            ("check", "Collect, diagnose, and report"),
                            ("analyze", "Analyze a saved snapshot offline")):
        item = sub.add_parser(name, help=help_text)
        if name == "analyze":
            item.add_argument("snapshot")
        item.add_argument("--config")
        item.add_argument("--output", "-o")
        if name != "collect":
            item.add_argument("--format", choices=("json", "markdown", "html"), default="markdown")
            item.add_argument("--strict", action="store_true")
        if name == "check":
            item.add_argument("--snapshot-out")
    diff = sub.add_parser("compare", help="Verify changes between two snapshots")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--config")
    diff.add_argument("--output", "-o")
    demo = sub.add_parser("demo", help="Generate labeled synthetic learning cases")
    demo.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="all")
    demo.add_argument("--output-dir", default="artifacts/demo")
    lab = sub.add_parser("lab", help="Run real faults inside isolated Linux namespaces")
    lab_sub = lab.add_subparsers(dest="lab_command", required=True)
    lab_run = lab_sub.add_parser("run", help="Verify five faults and recoveries; never changes host configuration")
    lab_run.add_argument("--output-dir", default="artifacts/lab")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        inputs = [getattr(args, n, None) for n in ("config", "snapshot", "before", "after")]
        outputs = [getattr(args, n, None) for n in ("output", "snapshot_out")]
        resolved_inputs = {Path(p).resolve() for p in inputs if p}
        resolved_outputs = [Path(p).resolve() for p in outputs if p]
        if resolved_inputs.intersection(resolved_outputs) or len(resolved_outputs) != len(set(resolved_outputs)):
            raise ValueError("Output paths must not overwrite inputs or each other")
        if args.command == "validate":
            output(json.dumps(load_config(args.config), indent=2), None)
            return 0
        if args.command == "demo":
            for name in SCENARIOS if args.scenario == "all" else (args.scenario,):
                cfg, snapshot = scenario(name)
                folder = Path(args.output_dir) / name
                write_text(folder / "config.json", json.dumps(cfg, indent=2))
                write_text(folder / "snapshot.json", json.dumps(snapshot.to_dict(), indent=2))
                report = evaluate(snapshot, cfg)
                for format_name, suffix in (("json", "json"), ("markdown", "md"), ("html", "html")):
                    write_text(folder / ("report." + suffix), render(report, format_name))
                print(f"{name}: {report.status} -> {folder}")
            return 0
        if args.command == "lab":
            from .lab import run_lab
            destination, summary = run_lab(args.output_dir)
            print(f"Verified {len(summary['cases'])} isolated fault/recovery cases -> {destination / 'index.html'}")
            return 0
        cfg = load_config(args.config)
        if args.command == "compare":
            before, after = evaluate(read_snapshot(args.before), cfg), evaluate(read_snapshot(args.after), cfg)
            output(json.dumps(compare(before, after), indent=2), args.output)
            return after.exit_code
        snapshot = read_snapshot(args.snapshot) if args.command == "analyze" else Collector(cfg).collect()
        if args.command == "collect":
            output(json.dumps(snapshot.to_dict(), indent=2), args.output)
            return 0 if all(o.status == "ok" for o in snapshot.observations) else 2
        if args.command == "check" and args.snapshot_out:
            write_text(args.snapshot_out, json.dumps(snapshot.to_dict(), indent=2))
        report = evaluate(snapshot, cfg)
        output(render(report, args.format), args.output)
        return 1 if args.strict and report.status == "WARN" else report.exit_code
    except BrokenPipeError:
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(f"rackcheck: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
