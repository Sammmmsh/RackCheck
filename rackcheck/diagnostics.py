"""Deterministic diagnostics; unavailable measurements never mean healthy."""
import math
import ipaddress
from .config import validate
from .models import Finding, Report


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite numeric observation")
    return value


def boolean(value):
    if type(value) is not bool:
        raise ValueError("Expected a boolean observation")
    return value


def evaluate(snapshot, config):
    cfg = validate(config)
    observations = {o.key: o for o in snapshot.observations}
    findings = []

    def rule(check_id, category, key, callback, recovery):
        obs = observations.get(key)
        if obs is None or obs.status != "ok":
            reason = "not collected" if obs is None else obs.detail or obs.status
            findings.append(Finding(check_id, category, "UNKNOWN", "Cannot assess: " + reason, [key] if obs else [], recovery))
            return
        try:
            status, summary = callback(obs.data)
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError) as exc:
            status, summary = "UNKNOWN", "Incomplete or invalid evidence: " + str(exc)
        findings.append(Finding(check_id, category, status, summary, [key], recovery if status != "PASS" else []))

    def capacity(field, minimum, unit):
        def check(data):
            value = numeric(data[field])
            if value < 0:
                raise ValueError("Negative capacity")
            return ("PASS" if value >= minimum else "FAIL", f"{value:g} {unit}; required minimum {minimum:g}")
        return check
    rule("system.cpu", "System", "system", capacity("cpus", cfg["system"]["min_cpus"], "logical CPUs"),
         ["Check VM CPU allocation or server inventory against the expected specification."])
    rule("system.memory", "System", "system", capacity("memory_mb", cfg["system"]["min_memory_mb"], "MiB RAM"),
         ["Check memory allocation; rerun inventory after a verified change."])

    def interfaces(data):
        rows = data["interfaces"]
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Invalid interface inventory")
        return "PASS", f"Enumerated {len(rows)} interfaces; this alone does not prove connectivity"
    rule("network.inventory", "Network", "network.interfaces", interfaces, ["Check iproute2 installation and permissions."])
    for name in cfg["network"]["interfaces"]:
        def interface(data, name=name):
            item = next((r for r in data["interfaces"] if r.get("ifname") == name), None)
            if item is None:
                return "FAIL", f"Expected interface {name} is absent"
            flags, addresses = item.get("flags"), item.get("addr_info")
            if not isinstance(flags, list) or not isinstance(addresses, list):
                raise ValueError("Missing link flags or addresses")
            addressed = any(a.get("family") in ("inet", "inet6") and a.get("scope") != "host" for a in addresses)
            ready = "UP" in flags and addressed and item.get("operstate") != "DOWN"
            return ("PASS" if ready else "FAIL", f"{name}: state={item.get('operstate', 'unknown')}, non-loopback address={addressed}")
        rule("interface:" + name, "Network", "network.interfaces", interface,
             ["Inspect ip address and expected interface configuration.", "Verify end-to-end reachability separately."])
    if cfg["network"]["require_default_route"]:
        def routes(data):
            rows = data["routes"]
            if not isinstance(rows, list):
                raise ValueError("Invalid route inventory")
            present = any(r.get("dst") == "default" and r.get("type", "unicast") == "unicast" for r in rows)
            return ("PASS" if present else "FAIL", "Default route present" if present else "No default route in the collected main table")
        rule("network.default_route", "Network", "network.routes", routes,
             ["Inspect the main routing table and expected gateway.", "A route does not prove gateway reachability."])

    def devices(data):
        rows = data["blockdevices"]
        if not isinstance(rows, list):
            raise ValueError("Invalid block-device inventory")
        return ("PASS" if rows else "UNKNOWN", f"Enumerated {len(rows)} top-level block devices; physical health is a separate check")
    rule("storage.inventory", "Storage", "storage.devices", devices, ["Check lsblk availability and device visibility."])
    for target in cfg["storage"]["mounts"]:
        path = target["path"]
        def filesystem(data, target=target):
            if not boolean(data["is_mount"]):
                return "FAIL", f"{target['path']} exists but is not a mounted filesystem"
            used = numeric(data["used_percent"])
            if not 0 <= used <= 100:
                raise ValueError("Filesystem percentage outside 0..100")
            if data.get("inodes_total", 0) > 0 and data.get("inodes_free") == 0:
                return "FAIL", f"{target['path']} has no free inodes"
            status = "FAIL" if used >= target["fail_percent"] else ("WARN" if used >= target["warn_percent"] else "PASS")
            return status, f"{target['path']}: {used:.1f}% used (warn {target['warn_percent']}%, fail {target['fail_percent']}%)"
        rule("filesystem:" + path, "Storage", "filesystem:" + path, filesystem,
             ["Inspect mount, capacity and inode usage.", "Identify approved retention changes; never delete files automatically.", "Repeat the check after recovery."])
    for name in cfg["services"]:
        def service(data, name=name):
            loaded, active, sub = data["LoadState"], data["ActiveState"], data["SubState"]
            if not all(isinstance(v, str) for v in (loaded, active, sub)):
                raise ValueError("Invalid systemd state")
            status = "PASS" if loaded == "loaded" and active == "active" else (
                "WARN" if loaded == "loaded" and active in ("activating", "deactivating", "reloading") else "FAIL")
            return status, f"{name}: load={loaded}, active={active}, substate={sub}"
        rule("service:" + name, "Services", "service:" + name, service,
             [f"Inspect systemctl status {name} and its journal.", "Check dependencies before an approved restart.", "Verify the service and endpoint after recovery."])
    for kind in ("dns", "tcp", "http"):
        for target in cfg["network"][kind]:
            identity = target["name"] if kind == "dns" else (target["url"] if kind == "http" else f'{target["host"]}:{target["port"]}')
            def network(data, kind=kind, target=target, identity=identity):
                if not boolean(data["ok"]):
                    return "FAIL", f"{identity}: {data.get('error_kind', 'network')} - {data.get('error', 'probe failed')}"
                if kind == "dns":
                    addresses = data["addresses"]
                    if not isinstance(addresses, list) or not addresses or not all(isinstance(address, str) for address in addresses):
                        raise ValueError("Missing resolved addresses")
                    addresses = [str(ipaddress.ip_address(address)) for address in addresses]
                    matches = not target["expected_addresses"] or set(target["expected_addresses"]) <= set(addresses)
                    return ("PASS" if matches else "FAIL", f"{identity} resolved to {', '.join(addresses)}; expected addresses satisfied={matches}")
                if kind == "http":
                    code = numeric(data["status_code"])
                    return ("PASS" if code == target["status"] else "FAIL", f"{identity}: HTTP {code}, expected {target['status']}")
                return "PASS", f"TCP connection to {identity} succeeded"
            rule(kind + ":" + identity, "Network", kind + ":" + identity, network, {
                "dns": ["Check the resolver and hostname.", "Compare with direct connectivity to the expected address."],
                "tcp": ["Check listening socket, service, route and firewall.", "Connection failure alone does not prove the server is down."],
                "http": ["Check DNS, TCP, TLS and application logs.", "Redirects are reported, not followed automatically."],
            }[kind])
    for device in cfg["storage"]["smart_devices"]:
        def smart(data, device=device):
            passed, code = data.get("smart_status", {}).get("passed"), data.get("_exit_status")
            if type(code) is not int or not 0 <= code <= 255:
                return "UNKNOWN", f"{device}: missing or invalid smartctl exit status"
            if passed is False or code & 0x18:
                return "FAIL", f"{device}: SMART reports a health or current attribute failure"
            if data.get("smart_support", {}).get("available") is False:
                return "UNKNOWN", f"{device}: SMART unsupported (common for virtual disks)"
            if code & 7:
                return "UNKNOWN", f"{device}: command/device access errors (status {code})"
            if passed is not True:
                return "UNKNOWN", f"{device}: no explicit SMART health result"
            if code & 0xE0:
                return "WARN", f"{device}: health passed but attribute/error/self-test history needs review"
            return "PASS", f"{device}: SMART health passed; this is not a failure prediction"
        rule("smart:" + device, "Hardware", "smart:" + device, smart,
             ["Review vendor-specific SMART output and permissions.", "Use an approved procedure for physical maintenance."])
    if cfg["redfish"]:
        rf = cfg["redfish"]
        for path in rf["paths"]:
            key = "redfish:" + rf["base_url"] + path
            def redfish(data):
                if not boolean(data["ok"]):
                    return "UNKNOWN", "Cannot retrieve Redfish health: " + str(data.get("error", "probe failed"))
                if numeric(data["status_code"]) != 200:
                    return "UNKNOWN", f"Redfish HTTP {data['status_code']}; no hardware health conclusion"
                resource = data["resource"]
                state = resource["Status"]
                if not isinstance(state, dict):
                    raise ValueError("Missing Redfish Status object")
                health = [state.get(k) for k in ("Health", "HealthRollup") if state.get(k) is not None]
                prefix = data.get("provenance", "BMC-reported")
                summary = f"{prefix}: Health={state.get('Health')}, HealthRollup={state.get('HealthRollup')}, State={state.get('State')}"
                if "Critical" in health:
                    return "FAIL", summary
                if not health or any(h not in ("OK", "Warning", "Critical") for h in health):
                    return "UNKNOWN", summary + "; incomplete or unrecognized health"
                if "Warning" in health or state.get("State") in ("Degraded", "Disabled", "Absent", "UnavailableOffline"):
                    return "WARN", summary
                return "PASS", summary
            rule(key, "Hardware API", key, redfish,
                 ["Inspect the configured resource and its subordinate resources in the BMC.",
                  "Check access, TLS and resource paths before drawing hardware conclusions.",
                  "Use an approved physical maintenance procedure; the mock cannot validate real hardware."])
    for target in cfg["network"]["dns"]:
        dns_key = "dns:" + target["name"]
        dns = observations.get(dns_key)
        if dns and dns.status == "ok" and dns.data.get("ok") is False:
            for endpoint in cfg["network"]["tcp"]:
                tcp_key = f'tcp:{endpoint["host"]}:{endpoint["port"]}'
                tcp = observations.get(tcp_key)
                if endpoint["host"] in target["expected_addresses"] and tcp and tcp.status == "ok" and tcp.data.get("ok") is True:
                    findings.append(Finding("correlation:" + target["name"], "Diagnosis", "WARN",
                        "Name resolution failed while direct TCP to an expected address succeeded; investigate resolver/name configuration",
                        [dns_key, tcp_key], ["Verify DNS settings and records; this does not prove which resolver component failed."]))
                    break
    return Report(snapshot, findings)
