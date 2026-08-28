# RackCheck

Linux server readiness and fault diagnostics with evidence, recovery runbooks,
and repeatable lab scenarios. Implementation stages are in [PHASES.md](PHASES.md).

Python 3.10+ is required. The core has no third-party runtime dependencies.
Run commands from the repository root without installing anything:

~~~console
python -m rackcheck --version
python -m rackcheck validate examples/server.json
python -m unittest discover -v
~~~

Collectors produce observations. Rules evaluate observations against expected
configuration. Reports preserve evidence and explain recovery steps. Missing
tools, permissions, and unsupported hardware produce UNKNOWN rather than a
fabricated healthy result.

Read [docs/architecture.md](docs/architecture.md) for contracts and trust boundaries.
This tool does not certify hardware, predict disk failure, or perform repairs.
