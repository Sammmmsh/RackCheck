from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from rackcheck.cli import main


class CliTests(unittest.TestCase):
    def invoke(self, args):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            result = main(args)
        return result, out.getvalue(), err.getvalue()

    def test_offline_workflow_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.invoke(["demo", "--output-dir", folder])[0], 0)
            for name, expected in (("healthy", 0), ("disk_full", 1), ("permission_denied", 2)):
                root = Path(folder) / name
                code, output, errors = self.invoke(["analyze", str(root / "snapshot.json"),
                    "--config", str(root / "config.json"), "--format", "json"])
                self.assertEqual(code, expected, errors)
                self.assertEqual(json.loads(output)["snapshot"]["context"], "fixture")
                self.assertTrue((root / "report.html").exists())

    def test_input_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text("{}")
            code, _, error = self.invoke(["check", "--config", str(path), "-o", str(path)])
            self.assertEqual(code, 2)
            self.assertIn("overwrite", error)
            self.assertEqual(path.read_text(), "{}")

    def test_bad_snapshot_is_a_controlled_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            path.write_text('{"schema_version": 99}')
            self.assertEqual(self.invoke(["analyze", str(path)])[0], 2)

    def test_strict_warning_exit_code(self):
        with tempfile.TemporaryDirectory() as folder:
            self.invoke(["demo", "--scenario", "smart_warning", "--output-dir", folder])
            root = Path(folder) / "smart_warning"
            command = ["analyze", str(root / "snapshot.json"), "--config", str(root / "config.json")]
            self.assertEqual(self.invoke(command)[0], 0)
            self.assertEqual(self.invoke(command + ["--strict"])[0], 1)
