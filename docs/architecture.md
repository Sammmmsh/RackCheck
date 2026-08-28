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
