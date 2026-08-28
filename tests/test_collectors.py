import json
import struct
import sys
import unittest
from rackcheck.collectors import Collector
from rackcheck.probes import dns_packet, parse_dns_response
from rackcheck.runner import CommandResult, run


class RunnerTests(unittest.TestCase):
    def test_missing_executable(self):
        self.assertEqual(run(["rackcheck-no-such-executable"], 1).status, "unsupported")

    def test_timeout(self):
        result = run([sys.executable, "-c", "import time; time.sleep(10)"], 0.1)
        self.assertIn("timed out", result.detail)

    def test_output_limit(self):
        result = run([sys.executable, "-c", "print('x' * 200)"], 2, max_bytes=100)
        self.assertEqual(result.status, "error")


class CollectorTests(unittest.TestCase):
    def test_nonlinux_is_explicit(self):
        snap = Collector({}, platform_name="Windows").collect()
        self.assertTrue(all(o.status == "unsupported" for o in snap.observations))

    def test_malformed_ip_json(self):
        c = Collector({}, runner=lambda *a: CommandResult("ok", "{}"), platform_name="Linux")
        self.assertEqual(c.interfaces().status, "error")

    def test_service_not_found_is_observed(self):
        c = Collector({}, runner=lambda *a: CommandResult("ok",
            "LoadState=not-found\nActiveState=inactive\nSubState=dead\n", returncode=1), platform_name="Linux")
        self.assertEqual(c.service("absent.service").data["LoadState"], "not-found")

    def test_smart_nonzero_keeps_health(self):
        c = Collector({}, runner=lambda *a: CommandResult("ok",
            json.dumps({"smart_status": {"passed": False}}), returncode=8), platform_name="Linux")
        o = c.smart("/dev/sda")
        self.assertEqual(o.status, "ok")
        self.assertFalse(o.data["smart_status"]["passed"])
        self.assertEqual(o.data["_exit_status"], 8)


class DnsTests(unittest.TestCase):
    def test_success(self):
        q = dns_packet("lab.test", b"\x12\x34")
        reply = q[:2] + struct.pack("!HHHHH", 0x8180, 1, 1, 0, 0) + q[12:]
        reply += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 10, 4) + b"\x7f\x00\x00\x01"
        self.assertEqual(parse_dns_response(reply, q)["addresses"], ["127.0.0.1"])

    def test_nxdomain_and_truncation(self):
        q = dns_packet("lab.test", b"\x12\x34")
        for flags, kind in ((0x8183, "dns"), (0x8380, "truncated")):
            reply = q[:2] + struct.pack("!HHHHH", flags, 1, 0, 0, 0) + q[12:]
            self.assertEqual(parse_dns_response(reply, q)["error_kind"], kind)

    def test_bad_packets(self):
        q = dns_packet("lab.test", b"\x12\x34")
        for reply in (b"", q, b"\x00\x00" + q[2:]):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                parse_dns_response(reply, q)
