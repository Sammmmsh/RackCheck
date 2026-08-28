# Implementation phases

Each phase is a separate Git commit with its verification recorded here.

1. Foundation: repository, models, strict configuration, CLI skeleton.
2. Collection: bounded commands, Linux inventory, services, storage, DNS/TCP/HTTP.
3. Diagnosis: rules, reports, offline replay, comparisons, fixtures, full CLI.
4. Lab and hardware API: isolated faults, recovery, Redfish, provenance tests.
5. Verification and learning: Linux integration, hardening, packaging, walkthroughs.

## Phase 1

- Implemented versioned contracts and strict JSON/optional YAML configuration.
- Established standard-library unittest suite and dependency-free CLI.
- Validation: python -m unittest discover -v; configuration validation.
- Installed Ubuntu WSL is available for later Linux validation.

## Phase 2

- Added Linux CPU/RAM, interfaces, routing, block-device, filesystem, systemd,
  journal, and optional read-only SMART collection.
- DNS/TCP/HTTP probes run in bounded child processes, including DNS resolution.
- Added a custom-resolver DNS parser with transaction, length, and truncation checks.
- Added subprocess timeout/output limits; no shell execution or automatic repairs.
- Verification includes collection/parser tests and Windows/Linux unittest runs.

## Phase 3

- Added deterministic rules, targeted DNS correlation, and recovery guidance.
- Added JSON, Markdown and escaped, self-contained HTML reports.
- Added offline snapshots, six labeled fixtures, and conservative before/after
  comparisons: recovery requires a newly observed PASS.
- Verification: 29 tests passed on Windows and Ubuntu WSL; all six fixtures
  produced their expected status. A read-only WSL scan produced a PASS report.
  This validates the configured virtual Linux checks, not physical hardware.

## Phase 4

- Added bounded, GET-only Redfish resource collection with environment-based
  credentials, TLS verification, no redirects, and explicit mock provenance.
- Added an opt-in rootless lab guarded by user, mount and network namespaces.
- Verified five real lab fault/recovery workflows in Ubuntu WSL: DNS SERVFAIL,
  stopped endpoint, HTTP 503, capped tmpfs capacity, and simulated Redfish health.
- Each case measured PASS -> FAIL -> PASS and produced snapshots, reports,
  recovery comparisons and namespace evidence; normal cleanup completed.
- Verification: 38 tests passed on Windows and Ubuntu WSL. No physical BMC,
  disk SMART device, or production host was used for fault injection.

## Phase 5

- Hardened JSON/YAML errors, finite data and timestamps, cancellation cleanup,
  filesystem timeouts, scan deadlines, IPv6 routes and custom-resolver DNS.
- Corrected SMART history severity and rejected service-command errors and
  blackhole routes as healthy evidence.
- Added setup/configuration/security documentation, runbooks, a module map,
  learning exercises and a GitHub Actions test workflow.
- Final verification: 57 tests passed on both Windows and Ubuntu WSL. The five
  isolated lab cases were rerun successfully with the completed code.
- Built and installed the wheel offline in a fresh Windows environment;
  verified its CLI and network worker outside the source directory.
- Validated the YAML example and a read-only systemd/journal scan in WSL;
  inspected the HTML index and failure report in the browser.
- See docs/verification.md for exact evidence and untested areas. CI is
  configured but not run; physical SMART/BMC validation is not claimed.
