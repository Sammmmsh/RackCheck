import unittest
from rackcheck.config import ConfigError, validate
from rackcheck.models import Finding, Observation, Report, Snapshot


class ConfigTests(unittest.TestCase):
    def test_defaults_are_independent(self):
        a = validate({})
        a["services"].append("a.service")
        self.assertEqual(validate({})["services"], [])

    def test_typo_rejected(self):
        with self.assertRaises(ConfigError):
            validate({"netwrok": {}})

    def test_bad_values(self):
        for cfg in ({"timeout_seconds": True}, {"timeout_seconds": float("nan")},
                    {"services": ["--help"]}, {"services": ["a.service", "a.service"]},
                    {"network": {"tcp": [{"host": "x", "port": 0}]}},
                    {"storage": {"mounts": [{"path": "/", "warn_percent": 95, "fail_percent": 90}]}}):
            with self.subTest(cfg=cfg), self.assertRaises(ConfigError):
                validate(cfg)

    def test_credentials_and_url_traversal_rejected(self):
        for rf in ({"base_url": "https://user:secret@server"}, {"base_url": "http://server"},
                   {"base_url": "https://server/redfish"},
                   {"base_url": "http://server", "allow_http": True, "username_env": "USER", "password_env": "PASSWORD"},
                   {"base_url": "https://server", "paths": ["/redfish/v1/../secret"]}):
            with self.subTest(rf=rf), self.assertRaises(ConfigError):
                validate({"redfish": rf})

    def test_explicit_mock_http(self):
        cfg = validate({"redfish": {"base_url": "http://127.0.0.1:8000", "allow_http": True}})
        self.assertEqual(cfg["redfish"]["paths"], ["/redfish/v1/Systems/1"])


class ModelTests(unittest.TestCase):
    def test_snapshot_roundtrip(self):
        snap = Snapshot("test", "Linux", [Observation("system", "ok", {"cpus": 2})])
        self.assertEqual(Snapshot.from_dict(snap.to_dict()), snap)

    def test_bad_schema_and_duplicates(self):
        with self.assertRaises(ValueError):
            Snapshot("test", "Linux", [], schema_version=True)
        with self.assertRaises(ValueError):
            Snapshot("test", "Linux", [Observation("x", "ok"), Observation("x", "ok")])

    def test_unknown_is_not_success(self):
        snap = Snapshot("test", "Linux", [])
        self.assertEqual(Report(snap, []).exit_code, 2)
        self.assertEqual(Report(snap, [Finding("x", "test", "UNKNOWN", "No data")]).status, "UNKNOWN")
        self.assertEqual(Report(snap, [Finding("x", "test", "FAIL", "bad")]).exit_code, 1)


if __name__ == "__main__":
    unittest.main()
