import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rackcheck.config import validate
from rackcheck.diagnostics import evaluate
from rackcheck.fixtures import scenario
from rackcheck.lab import assert_isolated, run_lab
from rackcheck.lab_services import LabServers
from rackcheck.lab_worker import fill_volume, isolated_volume, verify_case
from rackcheck.models import Observation
from rackcheck.probes import probe, redfish_query


class IsolationTests(unittest.TestCase):
    def test_refuses_shared_namespaces_before_any_mutation(self):
        namespaces = {"user": "user:[1]", "mnt": "mnt:[2]", "net": "net:[3]"}
        with patch("rackcheck.lab.namespace_ids", return_value=namespaces), patch("rackcheck.lab_worker.command") as command:
            for key in namespaces:
                changed = {k: v + "x" for k, v in namespaces.items()}
                changed[key] = namespaces[key]
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "refused"):
                    with isolated_volume(changed):
                        self.fail("Must not enter")
            command.assert_not_called()

    def test_refuses_nonlinux(self):
        with patch("rackcheck.lab.platform.system", return_value="Windows"):
            with self.assertRaisesRegex(ValueError, "requires Linux"):
                run_lab("unused")

    def test_refuses_to_fill_an_ordinary_directory(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, "Refusing disk fill"):
            fill_volume(Path(folder))

    def test_unknown_recovery_is_not_verified(self):
        cfg, baseline = scenario("healthy")
        _, fault = scenario("dns_failure")
        _, recovered = scenario("healthy")
        next(o for o in recovered.observations if o.key == "dns:service.lab").status = "unsupported"
        with tempfile.TemporaryDirectory() as folder:
            result = verify_case("dns", evaluate(baseline, cfg), evaluate(fault, cfg), evaluate(recovered, cfg),
                                 {"dns:service.lab": "FAIL"}, Path(folder))
        self.assertFalse(result["verified"])


class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servers = LabServers().__enter__()
        cls.url = f"http://127.0.0.1:{cls.servers.web_port}"
        cls.rf_url = f"http://127.0.0.1:{cls.servers.redfish.port}"

    @classmethod
    def tearDownClass(cls):
        cls.servers.__exit__(None, None, None)

    def test_real_dns_fault_and_recovery(self):
        target = {"name": "service.rackcheck.test", "server": "127.0.0.1", "port": self.servers.dns.port}
        try:
            self.assertEqual(probe("dns", target, 1)["addresses"], ["127.0.0.1"])
            self.servers.state.dns_failure = True
            self.assertEqual(probe("dns", target, 1)["rcode"], 2)
        finally:
            self.servers.state.dns_failure = False
        self.assertTrue(probe("dns", target, 1)["ok"])

    def test_http_does_not_follow_redirects(self):
        self.assertEqual(probe("http", {"url": self.url + "/redirect"}, 1)["status_code"], 302)

    def test_redfish_health_and_provenance(self):
        cfg, snapshot = scenario("healthy")
        cfg["redfish"] = {"base_url": self.rf_url, "allow_http": True, "mock": True}
        cfg = validate(cfg)
        target = {**cfg["redfish"], "path": "/redfish/v1/Systems/1"}
        key = "redfish:" + self.rf_url + target["path"]
        try:
            for health, status in (("OK", "PASS"), ("Warning", "WARN"), ("Critical", "FAIL"), ("vendor-unknown", "UNKNOWN")):
                with self.subTest(health=health):
                    self.servers.state.hardware_health = health
                    data = probe("redfish", target, 1)
                    snapshot.observations = [o for o in snapshot.observations if o.key != key] + [Observation(key, "ok", data)]
                    finding = next(f for f in evaluate(snapshot, cfg).findings if f.check_id == key)
                    self.assertEqual(finding.status, status)
                    self.assertIn("configured mock", finding.summary)
        finally:
            self.servers.state.hardware_health = "OK"

    def test_redfish_http_error_and_malformed_json(self):
        target = {"base_url": self.url, "path": "/unauthorized", "mock": True}
        data = probe("redfish", target, 1)
        self.assertEqual(data["status_code"], 401)
        self.assertNotIn("resource", data)
        target["path"] = "/invalid-json"
        self.assertFalse(probe("redfish", target, 1)["ok"])

    def test_credentials_are_not_echoed(self):
        target = {"base_url": "https://bmc.example.invalid", "path": "/redfish/v1/Systems/1",
                  "username_env": "RACKCHECK_TEST_USER", "password_env": "RACKCHECK_TEST_PASSWORD"}
        with patch.dict("os.environ", {}, clear=True), patch("rackcheck.probes.http_get") as get:
            data = redfish_query(target, 1)
            self.assertEqual(data["error_kind"], "credentials")
            get.assert_not_called()
        with patch.dict("os.environ", {"RACKCHECK_TEST_USER": "reader", "RACKCHECK_TEST_PASSWORD": "test-secret"}):
            with patch("rackcheck.probes.http_get", return_value={"ok": True, "status_code": 200, "body": {
                "Status": {"Health": "OK"}, "CredentialLeak": "test-secret"}}):
                self.assertNotIn("test-secret", str(redfish_query(target, 1)))
