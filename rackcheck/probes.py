"""Network primitives run in a child process for an overall wall-clock bound."""

import ipaddress
import json
import os
import socket
import struct
import urllib.error
import urllib.request


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
        if read_body:
            body = response.read(1_048_577)
            if len(body) > 1_048_576:
                raise ValueError("HTTP response exceeds 1 MiB")
            result["body"] = json.loads(body)
        return result


def _skip_name(data: bytes, offset: int) -> int:
    for _ in range(128):
        if offset >= len(data):
            raise ValueError("Truncated DNS name")
        size = data[offset]
        if size & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("Truncated DNS pointer")
            pointer = ((size & 0x3F) << 8) | data[offset + 1]
            if pointer >= len(data):
                raise ValueError("Invalid DNS pointer")
            return offset + 2
        if size & 0xC0 or size > 63:
            raise ValueError("Invalid DNS label")
        offset += 1
        if size == 0:
            return offset
        offset += size
    raise ValueError("DNS name exceeds label limit")


def dns_packet(name, transaction=None):
    transaction = os.urandom(2) if transaction is None else transaction
    labels = b"".join(bytes([len(label)]) + label.encode("ascii") for label in name.rstrip(".").split("."))
    question = labels + b"\x00" + struct.pack("!HH", 1, 1)
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
    addresses = []
    for _ in range(answers):
        offset = _skip_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("Truncated DNS resource record")
        kind, family, _, length = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        if offset + length > len(data):
            raise ValueError("Truncated DNS record data")
        if family == 1 and ((kind == 1 and length == 4) or (kind == 28 and length == 16)):
            addresses.append(str(ipaddress.ip_address(data[offset:offset + length])))
        offset += length
    if not addresses:
        return {"ok": False, "error_kind": "dns", "error": "No address answers received"}
    return {"ok": True, "addresses": sorted(set(addresses))}


def dns_query(target, timeout):
    if not target.get("server"):
        addresses = socket.getaddrinfo(target["name"], None, type=socket.SOCK_STREAM)
        return {"ok": True, "addresses": sorted({a[4][0] for a in addresses})}
    server = target["server"]
    family = socket.AF_INET6 if ipaddress.ip_address(server).version == 6 else socket.AF_INET
    request = dns_packet(target["name"])
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.connect((server, target["port"]))
        sock.send(request)
        reply = sock.recv(65_535)
    return parse_dns_response(reply, request)


def probe(kind, target, timeout):
    try:
        if kind == "dns":
            return dns_query(target, timeout)
        if kind == "tcp":
            with socket.create_connection((target["host"], target["port"]), timeout=timeout):
                return {"ok": True}
        if kind == "http":
            return http_get(target["url"], timeout)
        raise ValueError("Unknown probe type")
    except socket.gaierror as exc:
        return {"ok": False, "error_kind": "resolution", "error": str(exc)}
    except (TimeoutError, socket.timeout):
        return {"ok": False, "error_kind": "timeout", "error": "Network operation timed out"}
    except ConnectionRefusedError:
        return {"ok": False, "error_kind": "refused", "error": "Connection refused"}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"ok": False, "error_kind": "network", "error": str(exc)}
