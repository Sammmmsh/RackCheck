# RackCheck report: FAIL

Host: rackcheck-fixture | Context: **fixture**
Collected: 2026-08-29T13:07:06.076643+00:00

**Lab/fixture evidence: not production or physical-hardware validation.**

| Status | Check | Finding |
| --- | --- | --- |
| FAIL | dns:service.lab | service.lab: dns - Synthetic NXDOMAIN |
| WARN | correlation:service.lab | Name resolution failed while direct TCP to an expected address succeeded; investigate resolver/name configuration |
| PASS | system.cpu | 2 logical CPUs; required minimum 2 |
| PASS | system.memory | 2048 MiB RAM; required minimum 1024 |
| PASS | network.inventory | Enumerated 1 interfaces; this alone does not prove connectivity |
| PASS | interface:eth0 | eth0: state=UP, non-loopback address=True |
| PASS | network.default\_route | Default route present |
| PASS | storage.inventory | Enumerated 1 top-level block devices; physical health is a separate check |
| PASS | filesystem:/ | /: 30.0% used (warn 80%, fail 90%) |
| PASS | service:rackcheck-demo.service | rackcheck-demo.service: load=loaded, active=active, substate=running |
| PASS | tcp:192.0.2.10:8080 | TCP connection to 192.0.2.10:8080 succeeded |
| PASS | http:http://192.0.2.10:8080/health | http://192.0.2.10:8080/health: HTTP 200, expected 200 |

## Recovery and evidence

### dns:service.lab

service.lab: dns - Synthetic NXDOMAIN

- Check the resolver and hostname.
- Compare with direct connectivity to the expected address.
- Evidence: dns:service.lab

### correlation:service.lab

Name resolution failed while direct TCP to an expected address succeeded; investigate resolver/name configuration

- Verify DNS settings and records; this does not prove which resolver component failed.
- Evidence: dns:service.lab, tcp:192.0.2.10:8080

### system.cpu

2 logical CPUs; required minimum 2

- Evidence: system

### system.memory

2048 MiB RAM; required minimum 1024

- Evidence: system

### network.inventory

Enumerated 1 interfaces; this alone does not prove connectivity

- Evidence: network.interfaces

### interface:eth0

eth0: state=UP, non-loopback address=True

- Evidence: network.interfaces

### network.default\_route

Default route present

- Evidence: network.routes

### storage.inventory

Enumerated 1 top-level block devices; physical health is a separate check

- Evidence: storage.devices

### filesystem:/

/: 30.0% used (warn 80%, fail 90%)

- Evidence: filesystem:/

### service:rackcheck-demo.service

rackcheck-demo.service: load=loaded, active=active, substate=running

- Evidence: service:rackcheck-demo.service

### tcp:192.0.2.10:8080

TCP connection to 192.0.2.10:8080 succeeded

- Evidence: tcp:192.0.2.10:8080

### http:http://192.0.2.10:8080/health

http://192.0.2.10:8080/health: HTTP 200, expected 200

- Evidence: http:http://192.0.2.10:8080/health

## Observation details

Review identifiers and log messages before sharing.

    {
      "hostname": "rackcheck-fixture",
      "platform": "Linux",
      "observations": [
        {
          "key": "system",
          "status": "ok",
          "data": {
            "cpus": 2,
            "memory_mb": 2048,
            "kernel": "fixture"
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "network.interfaces",
          "status": "ok",
          "data": {
            "interfaces": [
              {
                "ifname": "eth0",
                "flags": [
                  "UP"
                ],
                "operstate": "UP",
                "addr_info": [
                  {
                    "family": "inet",
                    "local": "192.0.2.10",
                    "scope": "global"
                  }
                ]
              }
            ]
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "network.routes",
          "status": "ok",
          "data": {
            "routes": [
              {
                "dst": "default",
                "gateway": "192.0.2.1"
              }
            ]
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "storage.devices",
          "status": "ok",
          "data": {
            "blockdevices": [
              {
                "name": "vda",
                "type": "disk",
                "size": 10000000000
              }
            ]
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "filesystem:/",
          "status": "ok",
          "data": {
            "path": "/",
            "is_mount": true,
            "used_percent": 30,
            "inodes_total": 1000,
            "inodes_free": 500
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "service:rackcheck-demo.service",
          "status": "ok",
          "data": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running"
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "dns:service.lab",
          "status": "ok",
          "data": {
            "ok": false,
            "error_kind": "dns",
            "error": "Synthetic NXDOMAIN",
            "rcode": 3
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "tcp:192.0.2.10:8080",
          "status": "ok",
          "data": {
            "ok": true
          },
          "source": "synthetic fixture",
          "detail": ""
        },
        {
          "key": "http:http://192.0.2.10:8080/health",
          "status": "ok",
          "data": {
            "ok": true,
            "status_code": 200
          },
          "source": "synthetic fixture",
          "detail": ""
        }
      ],
      "context": "fixture",
      "collected_at": "2026-08-29T13:07:06.076643+00:00",
      "schema_version": 1
    }
