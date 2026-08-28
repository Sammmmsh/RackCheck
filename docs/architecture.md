# Architecture

~~~mermaid
flowchart LR
  C[JSON or optional YAML configuration] --> R[Diagnostic rules]
  L[Read-only Linux collectors] --> S[Versioned snapshot]
  N[Explicit network probes] --> S
  B[Optional Redfish GET requests] --> S
  S --> R
  R --> O[JSON / Markdown / HTML incident report]
  O --> D[Operator fixes and before/after comparison]
  F[Isolated fault lab] --> L
  F --> N
~~~

## Contracts

- Observation: stable key, collection status, structured data, source, detail.
- Snapshot: schema version, UTC time, hostname, platform, provenance (live,
  lab, or fixture), and unique observations.
- Finding: stable check ID, category, PASS/WARN/FAIL/UNKNOWN, evidence keys,
  and human-reviewed recovery instructions.
- Report: snapshot plus findings. FAIL takes priority over UNKNOWN, then WARN,
  then PASS. No findings means UNKNOWN.

## Boundaries

The CLI owns file I/O. Configuration is strictly validated before commands or
requests run. Collectors never change OS settings. Rules never execute commands.
Reports escape untrusted content. The lab has an explicit lifecycle and never
injects faults into the machine's system DNS, root filesystem, or unrelated
services. Simulated observations remain distinguishable from live evidence.

JSON is the default to keep installation offline and dependency-free. YAML is an
optional convenience. Both normalize to the same model.

## Module map

| Module | Responsibility | Must not do |
| --- | --- | --- |
| cli.py | Parse commands, coordinate workflows, enforce output/input separation | Execute arbitrary config commands |
| config.py / serialization.py | Validate expected state and external input | Trust unknown fields or unsafe URLs |
| collectors.py | Gather and label OS/API observations within budgets | Turn unavailable evidence into PASS |
| runner.py | Fixed subprocess argv, timeouts and interruption cleanup | Use a shell |
| local_worker.py / probe_worker.py | Isolate potentially blocking operations | Perform repairs |
| probes.py | Bounded DNS/TCP/HTTP/Redfish primitives | Follow redirects with credentials |
| models.py | Versioned data contracts and provenance | Infer diagnosis |
| diagnostics.py | Pure expectation evaluation and narrow correlation | Run commands or mutate the host |
| reports.py / files.py | Escaped reports, atomic output, comparisons | Claim UNKNOWN proves recovery |
| fixtures.py | Synthetic offline teaching cases | Claim live evidence |
| lab.py / lab_worker.py / lab_services.py | Guarded fault lifecycle and verification | Fall back to injecting on the host |

## Why these choices

The standard library keeps the basic workflow installable offline and small
enough to study. Sequential collection makes evidence and time budgets easier
to reason about; fleet-scale concurrency is outside scope. Potentially blocking
network and filesystem work runs in a bounded child process.

Rules are independent of collection, so the same saved snapshot can be replayed
without touching the machine. JSON preserves the raw evidence; reports are views
of it. Configuration is supplied explicitly for offline analysis rather than
silently guessing the original expectations.

The fault lab sits outside the normal collector path. Recovery actions are
restricted to lab-owned objects; the diagnostic CLI has no repair command.

## Status and recovery

Collection status describes whether a fact was measured: ok, error or
unsupported. A successful measurement may describe an unhealthy machine.
Diagnostic status describes whether that measurement meets an expectation.

Comparison joins stable check IDs. FAIL/WARN -> PASS is RECOVERED;
missing/UNKNOWN after evidence is UNVERIFIED; newly observed checks are
NOW_OBSERVED. The comparison is a measured state change, not proof that a
particular intervention caused recovery.
