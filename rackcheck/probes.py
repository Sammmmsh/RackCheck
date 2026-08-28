"""Network primitives run in a child process for an overall wall-clock bound."""

import ipaddress
import base64
import json
import os
import socket
import struct
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_get(url, timeout, headers=None, read_body=False):
    # Ignore proxy environment variables; do not forward credentials on redirects.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        result = {"ok": True, "status_code": response.code}
        if read_body and 200 <= response.code < 300:
            body = response.read(1_048_577)
            if len(body) > 1_048_576:
                raise ValueError("HTTP response exceeds 1 MiB")
            result["body"] = json.loads(body)
        return result


def redfish_query(target, timeout):
    """GET only. Credentials are read inside the worker, never passed in argv."""
    headers = {"Accept": "application/json"}
    if "username_env" in target:
        if urlsplit(target["base_url"]).scheme != "https":
            return {"ok": False, "error_kind": "credentials", "error": "Credentials require HTTPS"}
        user = os.environ.get(target["username_env"])
        password = os.environ.get(target["password_env"])
        if not user or not password:
            return {"ok": False, "error_kind": "credentials", "error": "Required credential environment variable is unset"}
        if ":" in user or max(len(user), len(password)) > 4096:
            return {"ok": False, "error_kind": "credentials", "error": "Invalid Basic authentication credentials"}
        token = base64.b64encode((user + ":" + password).encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic " + token
    result = http_get(target["base_url"] + target["path"], timeout, headers, read_body=True)
    body = result.pop("body", None)
    result["provenance"] = "configured mock" if target.get("mock") else "BMC-reported; not independently verified"
    if result["status_code"] == 200:
        if not isinstance(body, dict):
            raise ValueError("Redfish response must be a resource object")
        if body.get("@odata.id", target["path"]) != target["path"]:
            raise ValueError("Redfish resource identity does not match the requested path")
        # Whitelist evidence. Do not retain arbitrary API response bodies or headers.
        result["resource"] = {k: body[k] for k in ("Id", "Name", "@odata.id", "Status", "PowerState") if k in body}
        if isinstance(body.get("Status"), dict):
            result["resource"]["Status"] = {k: body["Status"][k] for k in ("State", "Health", "HealthRollup") if k in body["Status"]}
    return result


def _read_name(data: bytes, offset: int) -> tuple[str, int]:
    labels, seen, end = [], set(), None
    for _ in range(128):
        if offset >= len(data) or offset in seen:
            raise ValueError("Truncated or cyclic DNS name")
        seen.add(offset)
        size = data[offset]
        if size & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("Truncated DNS pointer")
            pointer = ((size & 0x3F) << 8) | data[offset + 1]
            if pointer >= len(data):
                raise ValueError("Invalid DNS pointer")
            if end is None:
                end = offset + 2
            offset = pointer
            continue
        if size & 0xC0 or size > 63:
            raise ValueError("Invalid DNS label")
        offset += 1
        if size == 0:
            name = ".".join(labels).lower()
            if len(name) > 253:
                raise ValueError("DNS name exceeds length limit")
            return name, end if end is not None else offset
        if offset + size > len(data):
            raise ValueError("Truncated DNS label")
        labels.append(data[offset:offset + size].decode("ascii"))
        offset += size
    raise ValueError("DNS name exceeds label limit")


def dns_packet(name, transaction=None, qtype=1):
    transaction = os.urandom(2) if transaction is None else transaction
    labels = b"".join(bytes([len(label)]) + label.encode("ascii") for label in name.rstrip(".").split("."))
    question = labels + b"\x00" + struct.pack("!HH", qtype, 1)
    return transaction + struct.pack("!HHHHH", 0x0100, 1, 0, 0, 0) + question


def parse_dns_response(data: bytes, request: bytes) -> dict:
    if len(data) < 12 or data[:2] != request[:2]:
        raise ValueError("Invalid DNS transaction")
    flags, questions, answers, _, _ = struct.unpack("!HHHHH", data[2:12])
    if not flags & 0x8000 or flags & 0x7800 or questions != 1:
        raise ValueError("Invalid DNS response header")
    if flags & 0x0200:
        return {"ok": False, "error_kind": "truncated", "error": "UDP DNS reply is truncated; TCP fallback is not implemented"}
    if data[12:len(request)] != request[12:]:
        raise ValueError("DNS question does not match request")
    rcode = flags & 15
    if rcode:
        return {"ok": False, "error_kind": "dns", "rcode": rcode, "error": f"DNS returned rcode {rcode}"}
    if answers > 128:
        raise ValueError("Too many DNS answers")
    offset = len(request)
    records, aliases = [], {}
    requested_name, question_end = _read_name(request, 12)
    requested_type = struct.unpack("!H", request[question_end:question_end + 2])[0]
    for _ in range(answers):
        owner, offset = _read_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("Truncated DNS resource record")
        kind, family, _, length = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        if offset + length > len(data):
            raise ValueError("Truncated DNS record data")
        if family == 1 and kind == requested_type and ((kind == 1 and length == 4) or (kind == 28 and length == 16)):
            records.append((owner, str(ipaddress.ip_address(data[offset:offset + length]))))
        elif family == 1 and kind == 5:
            alias, end = _read_name(data, offset)
            if end != offset + length:
                raise ValueError("Invalid DNS CNAME record")
            aliases[owner] = alias
        offset += length
    valid_names = {requested_name}
    name = requested_name
    while name in aliases:
        name = aliases[name]
        if name in valid_names:
            raise ValueError("Cyclic DNS alias chain")
        valid_names.add(name)
    addresses = [address for owner, address in records if owner in valid_names]
    if not addresses:
        return {"ok": False, "error_kind": "dns", "error": "No address answers received"}
    return {"ok": True, "addresses": sorted(set(addresses))}


def dns_query(target, timeout):
    if not target.get("server"):
        addresses = socket.getaddrinfo(target["name"], None, type=socket.SOCK_STREAM)
        return {"ok": True, "addresses": sorted({a[4][0] for a in addresses})}
    server = target["server"]
    family = socket.AF_INET6 if ipaddress.ip_address(server).version == 6 else socket.AF_INET
    # Query AAAA when explicitly expected; otherwise A is the custom-resolver default.
    types = sorted({28 if ipaddress.ip_address(a).version == 6 else 1 for a in target.get("expected_addresses", [])} or {1})
    addresses = []
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.connect((server, target["port"]))
        for qtype in types:
            request = dns_packet(target["name"], qtype=qtype)
            sock.send(request)
            reply = sock.recv(65_535)
            result = parse_dns_response(reply, request)
            if not result["ok"]:
                return result
            addresses.extend(result["addresses"])
    return {"ok": True, "addresses": sorted(set(addresses))}


def probe(kind, target, timeout):
    try:
        if kind == "dns":
            return dns_query(target, timeout)
        if kind == "tcp":
            with socket.create_connection((target["host"], target["port"]), timeout=timeout):
                return {"ok": True}
        if kind == "http":
            return http_get(target["url"], timeout)
        if kind == "redfish":
            return redfish_query(target, timeout)
        raise ValueError("Unknown probe type")
    except socket.gaierror as exc:
        return {"ok": False, "error_kind": "resolution", "error": str(exc)}
    except (TimeoutError, socket.timeout):
        return {"ok": False, "error_kind": "timeout", "error": "Network operation timed out"}
    except ConnectionRefusedError:
        return {"ok": False, "error_kind": "refused", "error": "Connection refused"}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"ok": False, "error_kind": "network", "error": str(exc)}
