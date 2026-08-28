# Safety and limitations

## Intended use

RackCheck is a local teaching and diagnostic tool, not a privileged management
agent. Run it as an ordinary user on machines and endpoints you are authorized
to inspect. Configuration is trusted operator input. Do not expose the CLI as
a public API accepting arbitrary target URLs; that would require a separate
authorization and network-access policy.

Normal collection reads system state and makes explicitly configured network
connections. It writes only requested reports/snapshots. It never restarts
services, edits DNS, changes routes, deletes application data, runs disk
self-tests or performs BMC actions.

## Process and input boundaries

- Fixed argument lists, no shell execution and no arbitrary command field.
- Command timeouts, bounded stdout retention and an overall scan deadline.
- Filesystem reads and network resolution run in child processes.
- Linux timeout/cancellation terminates the launched process group.
- Strict config validation, finite snapshot data, unique keys and timezone-aware timestamps.
- Atomic report writes; CLI outputs may not overwrite their input paths.

Commands write temporary stdout/stderr files until they finish or time out.
The retained output limit is not a strict disk quota. As with other userspace
tools, an uninterruptible kernel I/O wait or a wedged OS can defeat a hard
wall-clock guarantee. This is not a hostile-code sandbox.

Snapshots are unsigned evidence files. Context labels help prevent accidental
mixing of lab, fixture and live evidence; they do not prove authenticity.
An operator can edit a snapshot or label. Comparison checks matching hostname,
platform, context and chronological order, not cryptographic machine identity.

## Credentials and privacy

Redfish credentials are read from named environment variables in the worker,
not placed in argv or output. Only GET is used; redirects and environment
proxies are disabled. HTTPS certificate verification remains enabled.
Use an account with read-only BMC privileges and appropriate access controls.

No telemetry or external upload is implemented. Nevertheless, reports can
contain hostnames, addresses, hardware information and journal messages.
Selected journal messages can themselves contain secrets written by another
application. Raw logs are not automatically redacted. Review artifacts before
sharing; generated artifacts are ignored by Git by default.

## Fault lab

The lab verifies new user, mount and network namespaces before mutation. Mount
propagation is private. All servers bind loopback in the isolated network.
Only its newly mounted 8 MiB tmpfs is filled, and only its exact payload is
removed. No fallback performs these actions on the host if isolation fails.

The private mount and server cleanup happens before success is recorded.
Namespace IDs and outcomes are saved with the run. See [Lab](lab.md) for
abnormal termination behavior. Do not run the internal worker directly or
modify its isolation guards to make a blocked host work.

## What a report cannot establish

Inventory is not a physical hardware inspection. A route does not prove a
gateway is reachable. A TCP connect does not prove application correctness.
A passing HTTP status does not establish sustained availability. A SMART PASS
does not predict future disk reliability. A mock Redfish PASS says nothing
about a physical server. Single snapshots do not measure uptime or MTTR.

Additional limitations: no fleet orchestration, packet capture, load testing,
historical metrics store, repair automation, BMC resource discovery, or complete
vendor-specific SMART interpretation. A configured interface check does not
fully model bridges, bonds, VRFs, policy routing or every link-state nuance.
