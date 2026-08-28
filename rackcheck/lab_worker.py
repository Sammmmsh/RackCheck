"""Internal worker. Never invoke directly: use rackcheck lab run."""
from contextlib import contextmanager
from html import escape
import json
import os
from pathlib import Path
import sys
import tempfile
from .collectors import Collector
from .config import validate
from .diagnostics import evaluate
from .files import write_text
from .lab import assert_isolated
from .lab_services import LabServers
from .models import utc_now
from .reports import compare, render
from .runner import run


def command(argv):
    result = run(argv, 5)
    if result.status != "ok" or result.returncode:
        raise ValueError("Lab setup/cleanup failed: " + " ".join(argv) + ": " + (result.detail or result.stderr))


@contextmanager
def isolated_volume(parent_ids):
    # This check MUST precede every mount or interface mutation in this worker.
    current = assert_isolated(parent_ids)
    command(["mount", "--make-rprivate", "/"])
    command(["ip", "link", "set", "lo", "up"])
    with tempfile.TemporaryDirectory(prefix="rackcheck-lab-") as scratch:
        volume = Path(scratch) / "volume"
        volume.mkdir(mode=0o700)
        command(["mount", "-t", "tmpfs", "-o", "size=8m,nosuid,nodev,noexec,mode=0700", "rackcheck-lab", str(volume)])
        try:
            if not os.path.ismount(volume):
                raise ValueError("Lab volume is not mounted; refusing to fill a host filesystem")
            stats = os.statvfs(volume)
            if stats.f_blocks * stats.f_frsize > 8 * 1024 * 1024:
                raise ValueError("Lab volume exceeds the 8 MiB safety cap")
            yield volume, current
        finally:
            command(["umount", str(volume)])


def fill_volume(volume):
    """Write at most 7.625 MiB, only inside the newly mounted capped tmpfs."""
    if not os.path.ismount(volume) or os.statvfs(volume).f_blocks * os.statvfs(volume).f_frsize > 8 * 1024 * 1024:
        raise ValueError("Refusing disk fill: expected the isolated 8 MiB mount")
    payload = volume / "owned-fault-payload.bin"
    with payload.open("xb") as stream:
        for _ in range(122):
            stream.write(b"x" * 65_536)
    return payload


def capture(config, destination):
    snapshot = Collector(config).collect()
    snapshot.context = "lab"
    report = evaluate(snapshot, config)
    write_text(destination / "snapshot.json", json.dumps(snapshot.to_dict(), indent=2))
    for format_name, suffix in (("json", "json"), ("markdown", "md"), ("html", "html")):
        write_text(destination / ("report." + suffix), render(report, format_name))
    return report


def verify_case(name, baseline, fault, recovered, expected, destination):
    change = compare(fault, recovered)
    write_text(destination / "comparison.json", json.dumps(change, indent=2))
    b = {f.check_id: f.status for f in baseline.findings}
    f = {f.check_id: f.status for f in fault.findings}
    r = {f.check_id: f.status for f in recovered.findings}
    recovered_ids = {item["check_id"] for item in change["changes"] if item["change"] == "RECOVERED"}
    checks = [{"check_id": key, "baseline": b.get(key), "fault": f.get(key), "recovered": r.get(key),
               "verified": b.get(key) == "PASS" and f.get(key) == status and r.get(key) == "PASS" and key in recovered_ids}
              for key, status in expected.items()]
    verified = baseline.status == "PASS" and recovered.status == "PASS" and all(row["verified"] for row in checks)
    return {"name": name, "verified": verified, "baseline_status": baseline.status,
            "fault_status": fault.status, "recovered_status": recovered.status, "checks": checks}


def index_html(cases):
    rows = "".join(
        "<tr><td>" + escape(case["name"]) + "</td><td>" + ("VERIFIED" if case["verified"] else "FAILED") +
        "</td>" + "".join(f'<td><a href="{escape(case["name"])}/{stage}/report.html">{stage}</a></td>'
                         for stage in ("baseline", "fault", "recovered")) + "</tr>" for case in cases)
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>RackCheck lab evidence</title><style>
body{font:16px/1.6 system-ui;margin:40px auto;padding:0 20px;max-width:950px;color:#162235}
table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #ccd3dc;text-align:left}
aside{padding:16px;background:#fff2cc}a{color:#135eab}@media(max-width:600px){td,th{padding:6px;font-size:13px}}
</style><h1>RackCheck / Fault lab</h1>
<aside>Isolated Linux lab. DNS, endpoint and filesystem faults are real within the lab.
Redfish health is simulated. This is not physical hardware or production validation.</aside>
<p>Each case records a fresh baseline, injected fault, and measured recovery.</p>
<table><tr><th>Case</th><th>Result</th><th>Baseline</th><th>Fault</th><th>Recovery</th></tr>""" + rows + "</table></html>"


def execute(destination, parent_ids):
    cases = []
    with isolated_volume(parent_ids) as (volume, namespaces), LabServers() as servers:
        web_url = f"http://127.0.0.1:{servers.web_port}/health"
        rf_url = f"http://127.0.0.1:{servers.redfish.port}"
        config = validate({
            "timeout_seconds": 1,
            "network": {
                "dns": [{"name": "service.rackcheck.test", "server": "127.0.0.1", "port": servers.dns.port,
                         "expected_addresses": ["127.0.0.1"]}],
                "tcp": [{"host": "127.0.0.1", "port": servers.web_port}],
                "http": [{"url": web_url}],
            },
            "storage": {"mounts": [{"path": str(volume), "warn_percent": 80, "fail_percent": 90}]},
            "redfish": {"base_url": rf_url, "allow_http": True, "mock": True},
        })
        write_text(destination / "config.json", json.dumps(config, indent=2))

        def case(name, inject, recover, expected):
            folder = destination / name
            baseline = capture(config, folder / "baseline")
            try:
                inject()
                fault = capture(config, folder / "fault")
            finally:
                recover()
            recovered = capture(config, folder / "recovered")
            cases.append(verify_case(name, baseline, fault, recovered, expected, folder))

        case("dns_failure",
             lambda: setattr(servers.state, "dns_failure", True),
             lambda: setattr(servers.state, "dns_failure", False),
             {"dns:service.rackcheck.test": "FAIL"})
        case("service_stopped", servers.stop_web, servers.start_web,
             {f"tcp:127.0.0.1:{servers.web_port}": "FAIL", "http:" + web_url: "FAIL"})
        case("http_unhealthy",
             lambda: setattr(servers.state, "http_status", 503),
             lambda: setattr(servers.state, "http_status", 200),
             {"http:" + web_url: "FAIL"})
        payload = volume / "owned-fault-payload.bin"
        case("disk_full", lambda: fill_volume(volume), lambda: payload.unlink(missing_ok=True),
             {"filesystem:" + str(volume): "FAIL"})
        case("redfish_critical",
             lambda: setattr(servers.state, "hardware_health", "Critical"),
             lambda: setattr(servers.state, "hardware_health", "OK"),
             {"redfish:" + rf_url + "/redfish/v1/Systems/1": "FAIL"})

    summary = {
        "schema_version": 1, "context": "lab", "finished_at": utc_now(),
        "verified": all(case["verified"] for case in cases), "cases": cases,
        "isolation": {"launcher": parent_ids, "worker": namespaces, "tmpfs_limit_bytes": 8 * 1024 * 1024},
        "cleanup": "Loopback servers stopped, private tmpfs unmounted and scratch directory removed",
        "limitations": ["Redfish health is simulated; no physical BMC tested",
                        "Service fault stops an owned endpoint, not a host systemd unit",
                        "No host DNS, interface, service or storage configuration was changed"],
    }
    write_text(destination / "summary.json", json.dumps(summary, indent=2))
    write_text(destination / "index.html", index_html(cases))
    return summary


def main():
    try:
        summary = execute(Path(sys.argv[1]), json.loads(sys.argv[2]))
        print(json.dumps({"verified": summary["verified"], "cases": len(summary["cases"])}))
        return 0 if summary["verified"] else 1
    except (OSError, ValueError, TypeError) as exc:
        print("rackcheck lab: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
