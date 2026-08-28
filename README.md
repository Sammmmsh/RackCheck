# RackCheck

A Python CLI for Linux server readiness checks, fault diagnosis, and measured
recovery. A data-center operations learning project: inspect the machine,
compare evidence with expectations, explain the finding, and rerun after an
approved repair.

**Start here:** [Quick start](docs/quickstart.md) ·
[Architecture](docs/architecture.md) · [Learning guide](docs/learning.md) ·
[Verification record](docs/verification.md) · [Five Git phases](PHASES.md)

## What is implemented

| Area | Capabilities |
| --- | --- |
| Linux | CPU/RAM inventory, IPv4/IPv6 interfaces and main routes, block devices |
| Services | systemd state and the last five available journal entries |
| Storage | Expected mounts, usable capacity, inode exhaustion, optional SMART |
| Network | DNS resolution and expected addresses, TCP connection, HTTP status |
| Hardware API | Optional read-only Redfish health with explicit mock provenance |
| Diagnosis | PASS/WARN/FAIL/UNKNOWN, narrow DNS/TCP correlation, recovery guidance |
| Evidence | Versioned JSON snapshots, offline replay, JSON/Markdown/HTML reports |
| Recovery | Before/after comparison; recovery requires a new PASS measurement |
| Lab | Five isolated Linux faults with baseline, fault and recovery evidence |

The core uses only Python's standard library. Python 3.10+ is required.
Linux/Ubuntu WSL is required for Linux collectors and the real fault lab.
Windows can run tests, fixtures, network probes and offline analysis.

## First run

From the repository root, in Linux or Ubuntu WSL:

~~~console
python3 -m unittest discover -v
python3 -m rackcheck demo
python3 -m rackcheck check --config examples/server.json --format html --output artifacts/server.html --snapshot-out artifacts/server.json
python3 -m rackcheck lab run
~~~

The demo is entirely synthetic and labeled accordingly. The lab performs real
DNS, endpoint and filesystem failures inside private namespaces, with simulated
Redfish hardware health. Open the index.html path printed by the lab to inspect
all cases. No web server, cloud account, Docker daemon or physical server is
needed. Reports open directly as local HTML files.

For installation in a virtual environment:

~~~console
python3 -m pip install .
rackcheck --help
~~~

Source execution requires no installation. Packaging needs setuptools;
optional YAML configuration needs PyYAML. See the quick start for offline
installation and Windows/WSL instructions.

## Interpret the result

| Report status | Meaning | Exit |
| --- | --- | --- |
| PASS | All evaluated expectations passed | 0 |
| WARN | Attention needed, without a failed or unknown check | 0; 1 with --strict |
| FAIL | At least one evaluated expectation failed | 1 |
| UNKNOWN | Required evidence unavailable or invalid, with no FAIL | 2 |

FAIL takes priority over UNKNOWN, then WARN, then PASS. Inspect the counts and
individual findings: one FAIL can coexist with unknown checks. Optional evidence
such as a journal excerpt does not itself define a health expectation.

**PASS is scoped to the configuration.** It does not prove every application is
reachable, certify hardware, predict disk failure, or authorize a repair.
Only probe endpoints and machines you are authorized to inspect.

## Use and extend it

- [Configuration reference](docs/configuration.md): expected state and bounds.
- [Fault lab](docs/lab.md): isolation, scenarios, artifacts and limitations.
- [Runbooks](docs/runbooks.md): investigate first, verify after a change.
- [Security and limits](docs/security.md): credentials, logs and safe operation.
- [Learning guide](docs/learning.md): follow the code from a networking background.

Reproduce the lab, review the evidence, and understand the code before extending
or demonstrating the project. No production deployment or physical hardware
validation is claimed.
