# Investigation runbooks

These are investigation sequences, not permission to change a system.
Capture the failing snapshot first. Make repairs only through the machine's
approved procedure, then capture fresh evidence with the same configuration.

| Finding | Read-only investigation | Recovery evidence |
| --- | --- | --- |
| DNS failure, direct TCP passes | Check expected name/address, resolver and record; compare system and explicit resolver results | Expected DNS address returned; endpoint still reachable |
| TCP refuses connection | Check service state and listening socket with systemctl/ss; distinguish refusal from timeout | Fresh connection succeeds |
| TCP timeout | Inspect route, expected interface and firewall policy; timeout alone cannot localize the fault | Fresh connection plus application check |
| HTTP 503 | TCP can be healthy; inspect service dependencies and journal | Expected HTTP status observed |
| Interface missing/down | Inspect ip address and expected device identity; check cabling only through approved procedures | Link/address expectation and relevant endpoint probes pass |
| No default route | Inspect both main tables and expected gateway; policy routing may need separate analysis | Expected route observed and destination reachability confirmed |
| systemd inactive/failed | Inspect unit load/active/substate, result and journal; check dependencies before restarting | Unit active and required endpoint check passes |
| Filesystem high usage | Inspect mount, capacity and inodes; identify data ownership and approved retention | Same mount exists, usage below threshold and free inodes available |
| SMART current failure | Review the explicit device and vendor output; follow hardware incident procedure | Approved maintenance and new evidence; no reliability guarantee |
| SMART historical warning | Review the dated attribute/error/self-test history; do not equate old records with current failure | Document investigation; historical records may remain |
| Redfish Critical | Inspect configured BMC resource and components; distinguish a mock from real hardware | Fresh authorized BMC health, plus physical procedure where required |
| UNKNOWN | Check tool, permission, timeout, platform and schema support | A fresh valid observation; unknown is not a pass |

## Example: DNS isolation

1. Save a failing report and raw snapshot.
2. Confirm the failed DNS name and the expected IP are the same intended service.
3. Examine whether direct TCP to that expected IP succeeded.
4. Investigate resolver/record configuration if the transport still works.
5. After an approved change, rerun the same DNS and transport expectations.
6. Compare snapshots and retain the recovered evidence.

The correlation is a hypothesis supported by two measurements. It does not
prove a particular resolver, network appliance, or DNS record caused the fault.

## Operator record

For your own learning or an authorized incident, record:

- Time, affected expectation and snapshot path.
- What you observed versus what you inferred.
- Proposed change, approval and exact scope.
- Before/after findings and any unresolved UNKNOWN or WARN.
- Remaining limitations and next investigation.

Do not report production downtime or an MTTR improvement from a synthetic case.
