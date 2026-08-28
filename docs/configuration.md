# Configuration reference

Run rackcheck validate FILE to see defaults merged with your expectations.
Unknown keys, invalid types, duplicate targets and unsafe target formats are
rejected before collection. JSON is the default. YAML uses optional PyYAML
safe loading and the same semantic validation. Keep a copy of your normalized
configuration alongside snapshots so offline evaluations are reproducible.

## Complete example

This example uses documentation-only addresses. Replace them with authorized
targets; it is not expected to pass as written.

~~~json
{
  "schema_version": 1,
  "timeout_seconds": 3,
  "max_duration_seconds": 120,
  "system": {"min_cpus": 2, "min_memory_mb": 2048},
  "network": {
    "interfaces": ["eth0"],
    "require_default_route": true,
    "dns": [{
      "name": "app.example.test",
      "server": "192.0.2.53",
      "port": 53,
      "expected_addresses": ["192.0.2.10"]
    }],
    "tcp": [{"host": "192.0.2.10", "port": 8080}],
    "http": [{"url": "http://192.0.2.10:8080/health", "status": 200}]
  },
  "services": ["example.service"],
  "storage": {
    "mounts": [{"path": "/", "warn_percent": 80, "fail_percent": 90}],
    "smart_devices": ["/dev/sda"]
  },
  "redfish": {
    "base_url": "https://bmc.example.invalid",
    "paths": ["/redfish/v1/Systems/1"],
    "username_env": "RACKCHECK_BMC_USER",
    "password_env": "RACKCHECK_BMC_PASSWORD",
    "allow_http": false,
    "mock": false
  }
}
~~~

## Fields and defaults

| Setting | Default | Contract |
| --- | --- | --- |
| schema_version | 1 | Only version 1 is supported |
| timeout_seconds | 3 | Per-command/probe budget, 0.1–30 seconds; network worker startup gets up to 0.5 s extra |
| max_duration_seconds | 120 | Overall collection command budget, 1–600 seconds; unstarted observations become errors |
| system.min_cpus | 1 | Minimum logical CPUs, integer |
| system.min_memory_mb | 0 | Minimum MemTotal in MiB; no workload/free-memory claim |
| network.interfaces | [] | Explicit expected interfaces; UP, non-host-scope address, and not DOWN |
| network.require_default_route | false | Require any default route in IPv4 or IPv6 main tables |
| network.dns | [] | System resolver unless a literal-IP server is specified; port defaults to 53 |
| dns.expected_addresses | [] | Every expected address must appear; additional addresses are allowed |
| network.tcp | [] | Explicit host/port connections, not a port scan |
| network.http | [] | Explicit HTTP(S) URL; expected status defaults to 200 |
| services | [] | Explicit safe names ending in .service |
| storage.mounts | Root mount, 80/90% | Absolute Linux mount paths; 0 <= warn < fail <= 100 |
| storage.smart_devices | [] | Explicit /dev paths; read-only smartctl --all |
| redfish | null | Disabled unless configured |

Each target list is limited to 32 entries. Configuration input is limited to
1 MiB and snapshot input to 16 MiB. JSON duplicate keys and non-finite numeric
constants are rejected. Strings may not contain control characters.

### DNS

The system resolver uses getaddrinfo and can return IPv4 and IPv6. A custom
resolver uses bounded UDP queries. It queries A by default, or A/AAAA according
to explicitly expected address families. The parser checks transaction,
question, lengths, compression loops and CNAME ownership; unrelated answer
addresses cannot satisfy the check. It is not a recursive resolver, a DNSSEC
validator, or a replacement for a complete DNS library. Truncated UDP replies
produce a failed probe; TCP fallback is not implemented.

Only a failed resolution plus successful direct TCP to one of its configured
expected IPs creates the DNS correlation. A wrong but successfully resolved
address fails the expectation without claiming a specific root cause.

### HTTP and Redfish

HTTP probes compare status only, not response-body health, latency or uptime.
Redirects are not followed. Environment proxy settings are ignored.
URLs may not embed credentials, query strings or fragments.

Redfish base_url is an origin; paths remain below /redfish/v1/. Only the listed
resources are fetched. It does not crawl collections, discover all components,
or send power/reset/firmware actions. Health and HealthRollup have explicit
OK/Warning/Critical semantics; missing or unrecognized health is UNKNOWN.
PowerState is evidence, not a configured power-state expectation.

TLS verification is enabled and cannot be disabled through configuration.
Set the environment variable names in config, not their secret values.
Authenticated Redfish requires HTTPS even if allow_http is true.
mock=true labels simulated endpoints; it is a declaration, not automatic
hardware detection. HTTP is only an explicit lab convenience.

### Filesystems and SMART

Paths must identify mounts: an ordinary existing directory fails the mount
expectation. Percent used is used/(used + space available to an unprivileged
user), so filesystem reserved space is accounted for. Zero usable capacity is
UNKNOWN. Exhausted inodes fail when inode accounting is available.

SMART is optional and often unavailable on virtual disks. Its exit code is a
bitmask, not a conventional success/failure value. Current failing health or
prefail threshold breaches fail; past attribute/error/self-test history warns;
command/device access errors remain UNKNOWN unless a current failure was
also explicitly reported.

See the upstream
[smartctl manual](https://raw.githubusercontent.com/smartmontools/smartmontools/master/smartmontools/smartctl.8.in)
for the exit-status definitions.
