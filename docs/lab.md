# Isolated fault lab

Run from Linux or Ubuntu WSL, in the repository root:

~~~console
python3 -m rackcheck lab run
~~~

Prerequisites: Python 3.10+, util-linux (unshare, mount, umount, lsblk), iproute2,
and a kernel/policy that permits unprivileged user, mount and network namespaces.
Run as your normal user. RackCheck does not require or silently invoke sudo.
If isolation is unavailable, it refuses to inject faults. The offline demo
command remains available, but it is not a substitute for a verified lab run.

## What happens

The launcher creates a uniquely named output directory and starts a child in
three new namespaces. The worker checks that all three namespace IDs differ
from the launcher before changing a mount or interface. It makes mount
propagation private, enables only its own loopback interface, and mounts an
8 MiB tmpfs under a new temporary directory.

Loopback-only HTTP, DNS and Redfish test servers then support five cases:

| Case | Injection | Required recovery evidence |
| --- | --- | --- |
| DNS failure | Lab DNS server returns SERVFAIL | Expected address resolves again |
| Service stopped | Close the owned HTTP listener | TCP connects and HTTP returns 200 |
| HTTP unhealthy | Listener remains up but returns 503 | HTTP returns 200 again |
| Disk full | Write 7.625 MiB inside the capped tmpfs | Usage drops below the threshold after removing that exact file |
| Redfish critical | Mock resource reports Critical | Mock resource reports OK again |

Each case captures a new baseline, fault and recovery. A case passes only if
the baseline and recovered reports are PASS, the targeted fault is detected,
and the comparison marks its check as RECOVERED. UNKNOWN cannot verify recovery.

This is a real network/filesystem lab with simulated hardware status. The
service case tests an owned endpoint, not stopping a host systemd unit.
Systemd collection is tested independently. The lab is a teaching tool, not
a general container sandbox for running untrusted programs.

## Artifacts and cleanup

Open the printed index.html. Each case has three report formats, three raw
snapshots, and a comparison.json. The run's config.json records the ephemeral
ports and mount path; use it for offline analysis, not for another live scan
after cleanup. summary.json includes namespace evidence and per-check outcomes.

On normal completion the servers stop, tmpfs is unmounted, and the scratch
directory is removed before a successful summary is written. The launcher has
a 120-second overall timeout. An abrupt kill can leave an empty temporary
directory; namespace mounts disappear when their last processes exit. A failed
run remains failed and any partial output is retained for investigation.

No host DNS configuration, network interface, system service or disk is changed.
The output directory is intentionally persistent. Do not delete it if you want
to retain the evidence.

## Hardware API scope

The Redfish collector performs GET requests to explicitly configured resources.
It checks Status.Health and Status.HealthRollup (OK, Warning, Critical) and
preserves State as evidence. Missing health, authentication failures and
unrecognized fields cannot establish a healthy result. It does not enumerate
every resource or perform hardware actions.

The implemented values follow the
[DMTF Redfish Resource and Schema Guide](https://redfish.dmtf.org/schemas/v1/DSP2046_2024.1.html).
Real BMC access requires authorized endpoints and a trusted TLS certificate.
Credentials come from environment variables; never put them in config or URLs.
The loopback mock explicitly enables HTTP and identifies itself as simulated.
