# Quick start

## 1. Open the project

On Windows, open Ubuntu WSL from your terminal:

~~~console
wsl -d Ubuntu
~~~

Then change to the RackCheck repository. A Windows path such as
C:\Users\name\Projects\rackcheck becomes /mnt/c/Users/name/Projects/rackcheck.
Do not use the Windows Python executable for Linux collection.

~~~console
python3 --version
python3 -m rackcheck --help
python3 -m unittest discover -v
~~~

The module commands assume your working directory is the repository root.
On native Windows, substitute python for python3 for demos, tests and offline
analysis. Linux inventory will be explicitly unsupported.

## 2. Learn without touching a server

~~~console
python3 -m rackcheck demo
python3 -m rackcheck analyze artifacts/demo/dns_failure/snapshot.json --config artifacts/demo/dns_failure/config.json --format markdown
~~~

The second command deliberately exits 1 because the saved case contains a
failure. Open artifacts/demo/dns_failure/report.html. See the DNS failure and
successful direct TCP probe: the correlation narrows investigation, but does
not identify a specific faulty resolver component.

## 3. Read-only Linux scan

~~~console
python3 -m rackcheck validate examples/server.json
python3 -m rackcheck check --config examples/server.json --snapshot-out artifacts/before.json --format html --output artifacts/before.html
~~~

The sample expects a default route and checks the root filesystem. Your machine
can legitimately fail these expectations. Adjust configuration to the intended
system, not merely to make an unexplained failure disappear.

For an authorized systemd machine, examples/systemd.json also inspects journald.
Journals can be unavailable to your account; do not grant broad privileges just
to remove an unknown result.

## 4. Reproduce all five lab failures

~~~console
python3 -m rackcheck lab run
~~~

The printed index.html links 15 reports: baseline, fault and recovery for each
case. Temporary mounts and servers are removed when the run completes.
See [Lab](lab.md) if namespaces are blocked by your environment.

## 5. Compare a real recovery

After an independently approved repair, take another snapshot using the same
configuration and compare:

~~~console
python3 -m rackcheck collect --config examples/server.json --output artifacts/after.json
python3 -m rackcheck compare artifacts/before.json artifacts/after.json --config examples/server.json --output artifacts/recovery.json
~~~

Use two snapshots from the same host, platform and context, in chronological
order. A failed check becoming UNKNOWN is UNVERIFIED, not recovered.

## Optional installation

Use a project-local virtual environment, not system Python:

~~~console
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/rackcheck --version
~~~

On Windows the executables are under .venv\Scripts instead of .venv/bin.
Some Ubuntu installations need the distribution's python3-venv package for
this optional installation path. This does not affect source-tree execution.
Source-tree commands need no pip, venv, or network access. A previously built
wheel installs offline with:

~~~console
python3 -m pip install --no-index --no-deps /path/to/rackcheck-0.1.0-py3-none-any.whl
~~~

The build command, with setuptools and wheel already installed:

~~~console
python3 -m pip wheel . --no-build-isolation --no-deps --no-index --wheel-dir artifacts/package
~~~

Optional YAML: install the yaml extra in the virtual environment with
python3 -m pip install '.[yaml]'. JSON has the same configuration semantics
and needs no third-party library.
examples/server.yaml is the YAML equivalent of the basic server profile.

## Common setup problems

| Symptom | Meaning / next step |
| --- | --- |
| No module named rackcheck | Run from the repository root or install the package |
| ip or lsblk unavailable | Use your distribution's normal iproute2/util-linux installation process |
| Cannot connect to system bus | systemd may not manage this environment; do not fake a service PASS |
| smartctl unavailable | SMART is optional; configure it only for an available, authorized device |
| Unshare operation not permitted | Rootless lab blocked; use a suitable VM, not host-level fault injection |
| Exit 1 with a report | A check failed; this is not necessarily a crash |
| Exit 2 with a report | Required evidence is unknown; inspect individual findings |

## CLI reference

~~~console
rackcheck validate CONFIG
rackcheck collect [--config CONFIG] [--output SNAPSHOT]
rackcheck check [--config CONFIG] [--format json|markdown|html] [--output REPORT] [--snapshot-out SNAPSHOT] [--strict]
rackcheck analyze SNAPSHOT [--config CONFIG] [--format json|markdown|html] [--output REPORT] [--strict]
rackcheck compare BEFORE AFTER [--config CONFIG] [--output COMPARISON]
rackcheck demo [--scenario all|healthy|dns_failure|service_failure|disk_full|permission_denied|smart_warning] [--output-dir DIR]
rackcheck lab run [--output-dir DIR]
~~~

Collect reports collection completeness, not health: it returns 2 if any
observation could not be collected. Compare returns the after-report's exit
status. Demo exits 0 after generating intentionally failing fixtures.
