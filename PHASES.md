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
