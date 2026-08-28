# Verification record

Completed locally on 2026-08-28. Results below describe the tested environments,
not a production certification.

| Check | Environment | Observed result |
| --- | --- | --- |
| Regression suite | Windows, Python 3.12.13 | 57 tests passed |
| Regression suite | Ubuntu WSL2, Python 3.12.3 | 57 tests passed |
| Live Linux inventory | WSL2 | Configured checks passed |
| systemd and journal collection | WSL2 journald unit | 7 evaluated checks passed; journal observation collected |
| Six synthetic scenarios | Windows and Linux test workflows | Expected PASS/FAIL/WARN/UNKNOWN outcomes |
| Real isolated fault lab | WSL2, rootless namespaces | All five cases verified baseline -> fault -> recovery |
| YAML profile | Existing WSL PyYAML | Example validated successfully |
| Offline wheel build | Windows setuptools/pip | Built without dependency downloads |
| Offline installation | New project-local Windows venv | Installed CLI and worker ran outside the source directory |
| HTML report QA | Chromium-based browser | Index navigation, visible findings, counts, evidence and provenance checked |
| Git whitespace check | Local repository | No whitespace errors |

## Final lab run

Local evidence is under
[the final lab index](../artifacts/final-lab/run-20260828T141733Z-1aec2179/index.html)
and [its summary](../artifacts/final-lab/run-20260828T141733Z-1aec2179/summary.json).

| Case | Baseline | Injected condition | After recovery |
| --- | --- | --- | --- |
| DNS SERVFAIL | PASS | FAIL | PASS |
| Owned service listener stopped | PASS | FAIL | PASS |
| HTTP 503 | PASS | FAIL | PASS |
| 8 MiB tmpfs over capacity threshold | PASS | FAIL | PASS |
| Mock Redfish Critical | PASS | FAIL | PASS |

Each case includes three snapshots, JSON/Markdown/HTML reports, and an explicit
comparison. The summary records different launcher/worker namespace IDs and
successful normal cleanup. Redfish is simulated; other faults occur only in
the private lab.

## Reproduce

~~~console
python3 -m unittest discover -v
python3 -m rackcheck demo
python3 -m rackcheck check --config examples/systemd.json --format json --output artifacts/live/systemd-report.json
python3 -m rackcheck lab run
~~~

Local test logs are in artifacts/verification/windows-tests.txt and
artifacts/verification/linux-tests.txt. Artifacts are intentionally ignored by
Git because they can contain machine identifiers and journal messages. Those
links describe this workspace; regenerate evidence after cloning elsewhere.

## Package

The locally tested wheel is artifacts/package/rackcheck-0.1.0-py3-none-any.whl.
SHA-256:

~~~text
46011f279095075a7ba299a80d6afadd7a0ad8f2abab73cfe366e2b43cf51eb6
~~~

Its console entry point reported 0.1.0 from the isolated installation, and a
child HTTP worker successfully checked the local report endpoint while the
working directory was outside the source package.

## Not tested or not claimed

- Physical server maintenance, real SMART hardware, or an authenticated physical BMC.
- A production deployment, fleet scale, uptime, MTTR improvement or sustained load.
- Python 3.10 locally; the code targets 3.10+ and CI includes that version.
- GitHub-hosted CI execution: the workflow is configured but has not been pushed or run.
- Linux wheel installation: WSL lacks pip/ensurepip; Linux source execution and
  the complete lab were verified without installing system packages.

No host service, DNS setting, route or physical disk was changed for fault testing.
