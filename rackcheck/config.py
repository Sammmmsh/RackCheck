"""Strict configuration parsing. JSON is dependency-free; YAML is optional."""

import copy
import ipaddress
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

DEFAULTS = {
    "schema_version": 1, "timeout_seconds": 3,
    "system": {"min_cpus": 1, "min_memory_mb": 0},
    "network": {"interfaces": [], "require_default_route": False, "dns": [], "tcp": [], "http": []},
    "services": [],
    "storage": {"mounts": [{"path": "/", "warn_percent": 80, "fail_percent": 90}], "smart_devices": []},
    "redfish": None,
}


class ConfigError(ValueError):
    pass


def _object(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ConfigError(f"{name}: expected an object with only {sorted(allowed)}")


def _list(value, name):
    if not isinstance(value, list) or len(value) > 32:
        raise ConfigError(f"{name}: expected a list with at most 32 entries")
    return value


def _text(value, name, maximum=255):
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ConfigError(f"{name}: expected nonempty text without control characters")
    return value


def _number(value, name, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"{name}: expected a finite number")
    if integer and type(value) is not int:
        raise ConfigError(f"{name}: expected an integer")
    if not low <= value <= high:
        raise ConfigError(f"{name}: must be between {low} and {high}")


def validate_url(url, name, allow_http=True):
    _text(url, name, 2048)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ConfigError(f"{name}: invalid URL") from exc
    schemes = {"https", "http"} if allow_http else {"https"}
    if parsed.scheme not in schemes or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ConfigError(f"{name}: use an HTTP(S) URL without embedded credentials or fragment")
    if parsed.query:
        raise ConfigError(f"{name}: query strings are not accepted; keep credentials out of URLs")
    if port is not None:
        _number(port, name + ".port", 1, 65535, True)
    return url


def validate(value: dict) -> dict:
    _object(value, DEFAULTS, "config")
    cfg = copy.deepcopy(DEFAULTS)
    for key, item in value.items():
        if key in ("system", "network", "storage"):
            _object(item, DEFAULTS[key], key)
            cfg[key].update(copy.deepcopy(item))
        else:
            cfg[key] = copy.deepcopy(item)
    if type(cfg["schema_version"]) is not int or cfg["schema_version"] != 1:
        raise ConfigError("schema_version must be 1")
    _number(cfg["timeout_seconds"], "timeout_seconds", 0.1, 30)
    _number(cfg["system"]["min_cpus"], "min_cpus", 1, 65536, True)
    _number(cfg["system"]["min_memory_mb"], "min_memory_mb", 0, 1_000_000_000)
    net = cfg["network"]
    if type(net["require_default_route"]) is not bool:
        raise ConfigError("require_default_route must be boolean")
    for name in _list(net["interfaces"], "interfaces"):
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", _text(name, "interface")):
            raise ConfigError("Invalid interface name")
    for item in _list(net["dns"], "dns"):
        _object(item, {"name", "expected_addresses", "server", "port"}, "dns entry")
        name = _text(item.get("name"), "dns.name")
        if len(name.rstrip(".")) > 253 or not all(re.fullmatch(r"[A-Za-z0-9_-]{1,63}", label) for label in name.rstrip(".").split(".")):
            raise ConfigError("Invalid DNS name")
        item.setdefault("expected_addresses", [])
        for address in _list(item["expected_addresses"], "expected_addresses"):
            try:
                ipaddress.ip_address(address)
            except ValueError as exc:
                raise ConfigError("Invalid expected DNS address") from exc
        if item.get("server") is not None:
            try:
                ipaddress.ip_address(item["server"])
            except ValueError as exc:
                raise ConfigError("DNS server must be an IP address") from exc
        item.setdefault("port", 53)
        _number(item["port"], "dns.port", 1, 65535, True)
    for item in _list(net["tcp"], "tcp"):
        _object(item, {"host", "port"}, "tcp entry")
        _text(item.get("host"), "tcp.host")
        _number(item.get("port"), "tcp.port", 1, 65535, True)
    for item in _list(net["http"], "http"):
        _object(item, {"url", "status"}, "http entry")
        validate_url(item.get("url"), "http.url")
        item.setdefault("status", 200)
        _number(item["status"], "http.status", 100, 599, True)
    for service in _list(cfg["services"], "services"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@:-]{0,127}\.service", _text(service, "service")):
            raise ConfigError("Service must be a safe, fully qualified .service unit name")
    for mount in _list(cfg["storage"]["mounts"], "mounts"):
        _object(mount, {"path", "warn_percent", "fail_percent"}, "mount entry")
        path = _text(mount.get("path"), "mount.path", 4096)
        if not path.startswith("/"):
            raise ConfigError("Mount paths must be absolute Linux paths")
        mount.setdefault("warn_percent", 80)
        mount.setdefault("fail_percent", 90)
        _number(mount["warn_percent"], "warn_percent", 0, 100)
        _number(mount["fail_percent"], "fail_percent", 0, 100)
        if mount["warn_percent"] >= mount["fail_percent"]:
            raise ConfigError("warn_percent must be lower than fail_percent")
    for device in _list(cfg["storage"]["smart_devices"], "smart_devices"):
        if not re.fullmatch(r"/dev/[A-Za-z0-9_./-]+", _text(device, "SMART device")) or ".." in device.split("/"):
            raise ConfigError("SMART devices must be explicit /dev paths without traversal")
    rf = cfg["redfish"]
    if rf is not None:
        _object(rf, {"base_url", "paths", "username_env", "password_env", "allow_http", "mock"}, "redfish")
        rf.setdefault("allow_http", False)
        rf.setdefault("mock", False)
        if type(rf["mock"]) is not bool:
            raise ConfigError("redfish.mock must be boolean")
        if type(rf["allow_http"]) is not bool:
            raise ConfigError("redfish.allow_http must be boolean")
        validate_url(rf.get("base_url"), "redfish.base_url", rf["allow_http"])
        if urlsplit(rf["base_url"]).path not in ("", "/"):
            raise ConfigError("redfish.base_url must be an origin, without a resource path")
        rf["base_url"] = rf["base_url"].rstrip("/")
        rf.setdefault("paths", ["/redfish/v1/Systems/1"])
        for path in _list(rf["paths"], "redfish.paths"):
            _text(path, "redfish path", 1024)
            if not path.startswith("/redfish/v1/") or any(x in path for x in ("..", "?", "#", "%", "\\")):
                raise ConfigError("Redfish paths must stay below /redfish/v1/")
        for key in ("username_env", "password_env"):
            if key in rf and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", _text(rf[key], key)):
                raise ConfigError("Redfish credentials must name environment variables")
        if ("username_env" in rf) != ("password_env" in rf):
            raise ConfigError("Specify both credential environment variable names")
        if "username_env" in rf and urlsplit(rf["base_url"]).scheme != "https":
            raise ConfigError("Redfish credentials require HTTPS, even when allow_http is set")
    unique_groups = [
        cfg["services"], net["interfaces"], [x["name"] for x in net["dns"]],
        [f'{x["host"]}:{x["port"]}' for x in net["tcp"]], [x["url"] for x in net["http"]],
        [x["path"] for x in cfg["storage"]["mounts"]], cfg["storage"]["smart_devices"],
    ]
    if rf:
        unique_groups.append(rf["paths"])
    if any(len(group) != len(set(group)) for group in unique_groups):
        raise ConfigError("Duplicate check targets are not allowed")
    return cfg


def load_config(path=None) -> dict:
    if path is None:
        return validate({})
    p = Path(path)
    if p.stat().st_size > 1_048_576:
        raise ConfigError("Configuration is larger than 1 MiB")
    content = p.read_text(encoding="utf-8")
    try:
        if p.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError as exc:
                raise ConfigError("YAML requires the optional dependency: pip install '.[yaml]'") from exc
            value = yaml.safe_load(content)
        else:
            value = json.loads(content)
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"Cannot parse configuration: {exc}") from exc
    return validate(value)
