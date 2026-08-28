# Learn RackCheck from a networking background

The implementation is ready, but understanding it is a separate task. You do
not need to learn every Linux topic before starting. Work through one complete
diagnostic path, then add the others.

## 1. Get one observable result

Read [Quick start](quickstart.md), run the tests, generate the demo, and open
the DNS-failure HTML report. Explain these three facts in your own words:

- Name resolution failed.
- Direct TCP to the configured expected IP succeeded.
- The report suggests investigating DNS without claiming a proven root cause.

Your networking course already gives you the foundation for this distinction.
Read the raw snapshot to see the measurements behind each statement.

## 2. Learn the Python needed by the project

Focus on dictionaries/lists, functions, loops, exceptions, modules, dataclasses,
JSON and context managers. Trace one small function at a time:

| Read | What to understand |
| --- | --- |
| rackcheck/models.py | Observation versus Finding; why UNKNOWN is separate |
| rackcheck/config.py | Defaults and validation before side effects |
| rackcheck/fixtures.py | How test inputs can exist without real servers |
| rackcheck/diagnostics.py | Pure data in, findings out; no repair commands |
| tests/test_diagnostics.py | Arrange inputs, run a rule, assert the meaning |

Exercise: change a copy of the fixture's filesystem usage from 30 to 85 and
then 95. Predict PASS/WARN/FAIL before running it. Do not alter a real disk.

## 3. Understand the operating-system layer

Learn processes, exit codes, permissions, filesystems, mounts, inodes and systemd.
Run only these read-only commands in your WSL environment:

~~~console
uname -r
ip -j address show
ip -j -4 route show table main
ip -j -6 route show table main
lsblk --json --bytes --output NAME,TYPE,SIZE,MOUNTPOINT
systemctl show --no-pager --property=LoadState,ActiveState,SubState -- systemd-journald.service
~~~

Compare their output to rackcheck/collectors.py. Explain why a missing command
is UNKNOWN, why a missing expected service is a failure, and why enumerating
a disk does not validate physical disk health.

Read runner.py and local_worker.py. Understand why a timeout is needed and why
filesystem reads can block even though they are read-only.

## 4. Follow one complete request

~~~mermaid
sequenceDiagram
  participant U as CLI
  participant C as Collector
  participant W as Probe worker
  participant D as DNS endpoint
  participant R as Rules
  U->>C: Validated expectations
  C->>W: Explicit target and timeout
  W->>D: DNS question
  D-->>W: Reply or failure
  W-->>C: Structured measurement
  C-->>U: Snapshot
  U->>R: Snapshot plus expectations
  R-->>U: Finding and evidence keys
~~~

Read probes.py beside the DNS tests. Identify the transaction ID, flags, counts,
question, resource-record owner, type, TTL and record length. Explain why a
reply with an unrelated address must not satisfy the expected hostname.

## 5. Run the real lab and inspect recovery

Run rackcheck lab run. Study one case directory at a time. Compare baseline,
fault and recovered snapshots, then read comparison.json.

Explain these safety controls without looking at this page: new namespaces,
private mount propagation, loopback-only listeners, capped tmpfs, exact-file
cleanup, no host fallback, and a fresh PASS required for recovery.

The Redfish case is deliberately simulated. Learn the distinction between an
API's reported status and an independent physical inspection.

## 6. Make and test a contribution yourself

Choose one small change after you understand the existing behavior:

- Improve a recovery message based on a case you reproduced.
- Add a new malformed DNS packet to the existing parser tests.
- Add an explicit expectation for a Redfish power state, with tests for
  missing evidence and mocks clearly labeled.

Make a branch, write a focused test, implement the behavior, run the suite,
and commit with a description of the problem and evidence. Keep your learning
notes; do not just copy the final code into a different repository.

## 7. Demonstrate it independently

You are ready to discuss the project when you can:

- Draw the architecture and locate each module.
- Explain observation status versus diagnostic status.
- Run the project from a clean environment.
- Reproduce a lab fault and its recovery.
- Justify timeout, credential and isolation choices.
- Explain how SMART history differs from a current failure.
- Describe the test that would catch a regression.
- Name the limits: virtual hardware, simulated Redfish and no production trial.

A defensible project description, after doing that work, is:

> Developed and validated a Python Linux diagnostics CLI with structured
> evidence, DNS/TCP/HTTP checks, and five isolated fault/recovery scenarios.
> Integrated optional SMART and Redfish health checks, with simulated BMC
> validation and conservative handling of unavailable evidence.

Use wording that matches your actual contribution and explain the AI
assistance if asked. Do not claim production reliability improvements,
physical repair experience, or independent authorship of code you cannot
explain.
