"""Synthetic learning cases, never live evidence."""
from .config import validate
from .models import Observation, Snapshot

SCENARIOS = ("healthy", "dns_failure", "service_failure", "disk_full", "permission_denied", "smart_warning")


def scenario(name):
    if name not in SCENARIOS:
        raise ValueError("Unknown fixture scenario")
    cfg = validate({
        "system": {"min_cpus": 2, "min_memory_mb": 1024}, "services": ["rackcheck-demo.service"],
        "network": {"interfaces": ["eth0"], "require_default_route": True,
            "dns": [{"name": "service.lab", "expected_addresses": ["192.0.2.10"]}],
            "tcp": [{"host": "192.0.2.10", "port": 8080}],
            "http": [{"url": "http://192.0.2.10:8080/health"}]},
    })
    rows = {
        "system": {"cpus": 2, "memory_mb": 2048, "kernel": "fixture"},
        "network.interfaces": {"interfaces": [{"ifname": "eth0", "flags": ["UP"], "operstate": "UP",
            "addr_info": [{"family": "inet", "local": "192.0.2.10", "scope": "global"}]}]},
        "network.routes": {"routes": [{"dst": "default", "gateway": "192.0.2.1"}]},
        "storage.devices": {"blockdevices": [{"name": "vda", "type": "disk", "size": 10_000_000_000}]},
        "filesystem:/": {"path": "/", "is_mount": True, "used_percent": 30, "inodes_total": 1000, "inodes_free": 500},
        "service:rackcheck-demo.service": {"LoadState": "loaded", "ActiveState": "active", "SubState": "running"},
        "dns:service.lab": {"ok": True, "addresses": ["192.0.2.10"]},
        "tcp:192.0.2.10:8080": {"ok": True},
        "http:http://192.0.2.10:8080/health": {"ok": True, "status_code": 200},
    }
    if name == "dns_failure":
        rows["dns:service.lab"] = {"ok": False, "error_kind": "dns", "error": "Synthetic NXDOMAIN", "rcode": 3}
    if name == "service_failure":
        rows["service:rackcheck-demo.service"].update(ActiveState="failed", SubState="failed")
        rows["tcp:192.0.2.10:8080"] = {"ok": False, "error_kind": "refused", "error": "Synthetic refusal"}
        rows["http:http://192.0.2.10:8080/health"] = {"ok": False, "error_kind": "refused", "error": "Synthetic refusal"}
    if name == "disk_full":
        rows["filesystem:/"]["used_percent"] = 99
    if name == "smart_warning":
        cfg["storage"]["smart_devices"] = ["/dev/sda"]
        rows["smart:/dev/sda"] = {"smart_status": {"passed": True}, "_exit_status": 64}
    observations = [Observation(k, "ok", v, "synthetic fixture") for k, v in rows.items()]
    if name == "permission_denied":
        observations = [o if o.key != "storage.devices" else Observation(o.key, "error", detail="Synthetic permission denied") for o in observations]
    return cfg, Snapshot("rackcheck-fixture", "Linux", observations, context="fixture")
