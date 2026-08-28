import json
import struct
import sys
import unittest
from unittest.mock import patch, Mock
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

    def test_interruption_terminates_the_child(self):
        proc = Mock()
        proc.wait.side_effect = [KeyboardInterrupt, 0]
        with patch("rackcheck.runner.subprocess.Popen", return_value=proc), patch("rackcheck.runner.os.name", "nt"):
            with self.assertRaises(KeyboardInterrupt):
                run(["unused"], 1)
        proc.kill.assert_called_once()


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

    def test_service_command_error_cannot_look_healthy(self):
        c = Collector({}, runner=lambda *a: CommandResult("ok",
            "LoadState=loaded\nActiveState=active\nSubState=running\n", returncode=1), platform_name="Linux")
        self.assertEqual(c.service("example.service").status, "error")

    def test_smart_nonzero_keeps_health(self):
        c = Collector({}, runner=lambda *a: CommandResult("ok",
            json.dumps({"smart_status": {"passed": False}}), returncode=8), platform_name="Linux")
        o = c.smart("/dev/sda")
        self.assertEqual(o.status, "ok")
        self.assertFalse(o.data["smart_status"]["passed"])
        self.assertEqual(o.data["_exit_status"], 8)

    def test_ipv6_routes_and_partial_failure(self):
        def runner(argv, timeout):
            rows = [{"dst": "default", "gateway": "fe80::1"}] if "-6" in argv else []
            return CommandResult("ok", json.dumps(rows), returncode=0)
        c = Collector({}, runner=runner, platform_name="Linux")
        self.assertEqual(c.routes().data["routes"][0]["family"], "inet6")
        c.runner = lambda argv, timeout: CommandResult("unsupported", detail="missing IPv6") if "-6" in argv else runner(argv, timeout)
        self.assertEqual(c.routes().status, "unsupported")

    def test_scan_deadline_stops_later_commands(self):
        runner = Mock()
        with patch("rackcheck.collectors.time.monotonic", return_value=0):
            collector = Collector({"max_duration_seconds": 1}, runner=runner, platform_name="Linux")
        with patch("rackcheck.collectors.time.monotonic", return_value=2):
            observation = collector.block_devices()
        self.assertEqual(observation.status, "error")
        runner.assert_not_called()

    def test_filesystem_read_is_bounded(self):
        runner = Mock(return_value=CommandResult("error", detail="Collector timed out"))
        c = Collector({}, runner=runner, platform_name="Linux")
        self.assertEqual(c.filesystem({"path": "/hung"}).status, "error")
        self.assertIn("rackcheck.local_worker", runner.call_args.args[0])


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

    def test_aaaa_and_unrelated_records(self):
        q = dns_packet("lab.test", b"\x12\x34", qtype=28)
        prefix = q[:2] + struct.pack("!HHHHH", 0x8180, 1, 1, 0, 0) + q[12:]
        record = struct.pack("!HHIH", 28, 1, 10, 16) + b"\x00" * 15 + b"\x01"
        self.assertEqual(parse_dns_response(prefix + b"\xc0\x0c" + record, q)["addresses"], ["::1"])
        self.assertFalse(parse_dns_response(prefix + b"\x05other\x04test\x00" + record, q)["ok"])

    def test_cname_chain_and_compression_loop(self):
        q = dns_packet("lab.test", b"\x12\x34")
        prefix = q[:2] + struct.pack("!HHHHH", 0x8180, 1, 2, 0, 0) + q[12:]
        alias = b"\x05alias\x04test\x00"
        cname = b"\xc0\x0c" + struct.pack("!HHIH", 5, 1, 10, len(alias)) + alias
        answer = alias + struct.pack("!HHIH", 1, 1, 10, 4) + b"\x7f\x00\x00\x01"
        self.assertEqual(parse_dns_response(prefix + cname + answer, q)["addresses"], ["127.0.0.1"])
        offset = len(prefix)
        cyclic = prefix + struct.pack("!H", 0xC000 | offset)
        with self.assertRaises(ValueError):
            parse_dns_response(cyclic, q)
