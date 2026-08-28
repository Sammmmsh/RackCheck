import unittest
from rackcheck.diagnostics import evaluate
from rackcheck.fixtures import scenario, SCENARIOS
from rackcheck.reports import compare, render


class DiagnosticsTests(unittest.TestCase):
    def test_scenarios(self):
        expected = {"healthy": "PASS", "dns_failure": "FAIL", "service_failure": "FAIL",
                    "disk_full": "FAIL", "permission_denied": "UNKNOWN", "smart_warning": "WARN"}
        for name in SCENARIOS:
            cfg, snap = scenario(name)
            with self.subTest(name=name):
                self.assertEqual(evaluate(snap, cfg).status, expected[name])

    def test_dns_correlation_requires_matching_direct_address(self):
        cfg, snap = scenario("dns_failure")
        self.assertTrue(any(f.check_id.startswith("correlation:") for f in evaluate(snap, cfg).findings))
        cfg["network"]["dns"][0]["expected_addresses"] = ["192.0.2.99"]
        self.assertFalse(any(f.check_id.startswith("correlation:") for f in evaluate(snap, cfg).findings))

    def test_missing_or_invalid_data_cannot_pass(self):
        for data in ({}, {"cpus": True, "memory_mb": float("nan")}):
            cfg, snap = scenario("healthy")
            snap.observations[0].data = data
            self.assertEqual(evaluate(snap, cfg).status, "UNKNOWN")
        cfg, snap = scenario("healthy")
        next(o for o in snap.observations if o.key == "dns:service.lab").data["addresses"] = [True]
        self.assertEqual(evaluate(snap, cfg).status, "UNKNOWN")

    def test_missing_mount_and_inodes(self):
        for change in ({"is_mount": False}, {"inodes_free": 0}):
            cfg, snap = scenario("healthy")
            next(o for o in snap.observations if o.key == "filesystem:/").data.update(change)
            self.assertEqual(evaluate(snap, cfg).status, "FAIL")

    def test_virtual_smart_is_unknown(self):
        cfg, snap = scenario("smart_warning")
        snap.observations[-1].data = {"smart_support": {"available": False}, "_exit_status": 0}
        self.assertEqual(evaluate(snap, cfg).status, "UNKNOWN")

    def test_smart_current_failure_history_and_access_bits(self):
        for code, expected in ((0, "PASS"), (8, "FAIL"), (16, "FAIL"), (32, "WARN"),
                               (64, "WARN"), (128, "WARN"), (2, "UNKNOWN"), (None, "UNKNOWN")):
            cfg, snap = scenario("smart_warning")
            snap.observations[-1].data = {"smart_status": {"passed": True}, "_exit_status": code}
            with self.subTest(code=code):
                self.assertEqual(evaluate(snap, cfg).status, expected)

    def test_ipv6_default_route(self):
        cfg, snap = scenario("healthy")
        next(o for o in snap.observations if o.key == "network.routes").data = {"routes": [{"dst": "default", "family": "inet6"}]}
        self.assertEqual(evaluate(snap, cfg).status, "PASS")

    def test_blackhole_default_is_not_a_usable_route(self):
        cfg, snap = scenario("healthy")
        next(o for o in snap.observations if o.key == "network.routes").data = {"routes": [{"dst": "default", "type": "blackhole"}]}
        self.assertEqual(evaluate(snap, cfg).status, "FAIL")


class ReportTests(unittest.TestCase):
    def test_html_escapes_host_and_evidence(self):
        cfg, snap = scenario("healthy")
        snap.hostname = "<script>alert(1)</script>"
        snap.observations[0].detail = "<img src=x onerror=bad()>"
        html = render(evaluate(snap, cfg), "html")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("fixture", html)

    def test_compare_only_proves_recovery_with_a_pass(self):
        cfg, before = scenario("disk_full")
        _, after = scenario("healthy")
        diff = compare(evaluate(before, cfg), evaluate(after, cfg))
        self.assertEqual(next(c for c in diff["changes"] if c["check_id"] == "filesystem:/")["change"], "RECOVERED")
        next(o for o in after.observations if o.key == "filesystem:/").status = "error"
        diff = compare(evaluate(before, cfg), evaluate(after, cfg))
        self.assertEqual(next(c for c in diff["changes"] if c["check_id"] == "filesystem:/")["change"], "UNVERIFIED")

    def test_compare_rejects_different_hosts(self):
        cfg, before = scenario("healthy")
        _, after = scenario("healthy")
        after.hostname = "different"
        with self.assertRaises(ValueError):
            compare(evaluate(before, cfg), evaluate(after, cfg))

    def test_compare_rejects_old_evidence_and_other_provenance(self):
        cfg, before = scenario("healthy")
        _, after = scenario("healthy")
        before.collected_at, after.collected_at = "2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"
        with self.assertRaises(ValueError):
            compare(evaluate(before, cfg), evaluate(after, cfg))
        after.collected_at = "2026-01-03T00:00:00+00:00"
        after.context = "live"
        with self.assertRaises(ValueError):
            compare(evaluate(before, cfg), evaluate(after, cfg))

    def test_markdown_does_not_create_injected_links(self):
        cfg, snap = scenario("healthy")
        snap.hostname = "[click](https://example.invalid)"
        markdown = render(evaluate(snap, cfg), "markdown")
        rendered_text = "\n".join(line for line in markdown.splitlines() if not line.startswith("    "))
        self.assertNotIn("[click](", rendered_text)
        self.assertIn(r"\[click\]", rendered_text)
