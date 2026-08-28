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
