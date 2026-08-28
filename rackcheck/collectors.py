"""Read-only collectors. Unsupported facts stay unknown."""

import json
import os
from pathlib import Path
import platform
import socket
import sys
from .config import validate
from .models import Observation, Snapshot
from .runner import run


class Collector:
    def __init__(self, config, runner=run, platform_name=None):
        self.config = validate(config)
        self.run = runner
        self.timeout = self.config["timeout_seconds"]
        self.platform_name = platform_name or platform.system()

    def command(self, key, argv, parse):
        if self.platform_name != "Linux":
            return Observation(key, "unsupported", source=" ".join(argv), detail="Linux collector requires Linux")
        result = self.run(argv, self.timeout)
        if result.status != "ok":
            return Observation(key, result.status, source=" ".join(argv), detail=result.detail)
        try:
            data = parse(result)
            return Observation(key, "ok", data, " ".join(argv))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            detail = f"{exc}; {result.stderr[:500]}".strip("; ")
            return Observation(key, "error", source=" ".join(argv), detail=detail)

    def inventory(self):
        key = "system"
        if self.platform_name != "Linux":
            return Observation(key, "unsupported", detail="Linux inventory requires Linux")
        try:
            mem = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                name, value = line.split(":", 1)
                mem[name] = int(value.split()[0])
            return Observation(key, "ok", {"cpus": os.cpu_count(), "memory_mb": mem["MemTotal"] / 1024,
                "kernel": platform.release()}, "/proc/meminfo; os.cpu_count")
        except (OSError, ValueError, KeyError) as exc:
            return Observation(key, "error", detail=str(exc))

    @staticmethod
    def json_list(result, field):
        if result.returncode:
            raise ValueError(f"Command exited with code {result.returncode}")
        value = json.loads(result.stdout)
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            raise ValueError("Expected an array of objects")
        return {field: value}

    def interfaces(self):
        return self.command("network.interfaces", ["ip", "-j", "address", "show"],
                            lambda r: self.json_list(r, "interfaces"))

    def routes(self):
        def parse(result):
            data = self.json_list(result, "routes")
            return data
        return self.command("network.routes", ["ip", "-j", "route", "show", "table", "main"], parse)

    def block_devices(self):
        def parse(result):
            data = json.loads(result.stdout)
            if result.returncode or not isinstance(data.get("blockdevices"), list):
                raise ValueError("Cannot read block-device inventory")
            return data
        return self.command("storage.devices", ["lsblk", "--json", "--bytes", "--output", "NAME,TYPE,SIZE,MOUNTPOINT"], parse)

    def service(self, name):
        def parse(result):
            fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
            if not {"LoadState", "ActiveState", "SubState"} <= fields.keys():
                raise ValueError("systemd did not return service state")
            return fields
        return self.command("service:" + name, ["systemctl", "show", "--no-pager",
            "--property=LoadState,ActiveState,SubState,Result,MainPID", "--", name], parse)

    def service_logs(self, name):
        def parse(result):
            if result.returncode:
                raise ValueError("Journal unavailable or inaccessible")
            entries = []
            for line in result.stdout.splitlines():
                row = json.loads(line)
                entries.append({k: row.get(k) for k in ("__REALTIME_TIMESTAMP", "PRIORITY", "MESSAGE")})
            return {"entries": entries, "scope": "last 5 available entries, not complete service history"}
        return self.command("logs:" + name, ["journalctl", "--no-pager", "--lines=5", "--output=json", "--unit", name], parse)

    def filesystem(self, target):
        path = target["path"]
        if self.platform_name != "Linux":
            return Observation("filesystem:" + path, "unsupported", detail="Linux filesystem collector requires Linux")
        try:
            stat = os.statvfs(path)
            used = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
            available = stat.f_bavail * stat.f_frsize
            denominator = used + available
            return Observation("filesystem:" + path, "ok", {
                "path": path, "is_mount": os.path.ismount(path),
                "total_bytes": stat.f_blocks * stat.f_frsize, "used_bytes": used,
                "available_bytes": available, "used_percent": used * 100 / denominator if denominator else None,
                "inodes_total": stat.f_files, "inodes_free": stat.f_favail,
            }, "os.statvfs; os.path.ismount")
        except OSError as exc:
            return Observation("filesystem:" + path, "error", detail=str(exc))

    def smart(self, device):
        def parse(result):
            data = json.loads(result.stdout)
            if not isinstance(data, dict):
                raise ValueError("Invalid SMART JSON")
            # smartctl exit status is a bitmask; nonzero can mean a real disk warning.
            data["_exit_status"] = result.returncode
            return data
        return self.command("smart:" + device, ["smartctl", "--json", "--all", device], parse)

    def network_probe(self, kind, target):
        identity = target["name"] if kind == "dns" else (target["url"] if kind == "http" else f'{target["host"]}:{target["port"]}')
        key = kind + ":" + identity
        payload = json.dumps({"kind": kind, "target": target, "timeout": self.timeout})
        result = self.run([sys.executable, "-m", "rackcheck.probe_worker", payload], self.timeout + 0.5)
        if result.status != "ok" or result.returncode:
            return Observation(key, "error", source=kind + " probe", detail=result.detail or result.stderr[:500])
        try:
            data = json.loads(result.stdout)
            if not isinstance(data, dict) or type(data.get("ok")) is not bool:
                raise ValueError("Invalid network probe result")
            return Observation(key, "ok", data, kind + " probe")
        except ValueError as exc:
            return Observation(key, "error", detail=str(exc))

    def collect(self):
        observations = [self.inventory(), self.interfaces(), self.routes(), self.block_devices()]
        for target in self.config["storage"]["mounts"]:
            observations.append(self.filesystem(target))
        for service in self.config["services"]:
            observations.extend((self.service(service), self.service_logs(service)))
        for device in self.config["storage"]["smart_devices"]:
            observations.append(self.smart(device))
        for kind in ("dns", "tcp", "http"):
            observations.extend(self.network_probe(kind, target) for target in self.config["network"][kind])
        return Snapshot(socket.gethostname(), self.platform_name, observations)
