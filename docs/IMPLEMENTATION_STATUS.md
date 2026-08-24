# Implementation status

This record distinguishes running behavior from scaffolding and future native
integration. It is intentionally conservative.

| Capability | Status | Evidence |
|---|---|---|
| Isolated workspace lifecycle | Running | Unit tests + REST API exercise |
| Workspace file boundary | Running | Traversal rejection test |
| Legacy Python supervision | Running reference path | Build/run/status/log API exercise |
| Structured logs | Running | Captured subprocess output |
| REST health, workspace, graph, logs, metrics | Running | Local end-to-end API exercise |
| Prometheus endpoint | Running baseline | `/metrics` exposition |
| Heartbeat watchdog / simulated E-Stop | Running | Sub-100 ms test and CLI exercise |
| ROS 1 Python pub/sub migration | Running supported path | Fixture migration test |
| Generated migration validation | Scaffold | Requires ROS/bag execution environment |
| Native Rust executor | Adapter boundary | Rust + ROS 2 toolchain required |
| DDS/Zenoh inter-mode transport | Adapter boundary | ROS 2 environment required |
| Hardware E-Stop | Adapter boundary | GPIO/watchdog hardware required |
| Real-time latency targets | Unverified | Target Linux/RT hardware benchmark required |
| Go production CLI / WebSocket backend | Deferred | Reference service uses Python/polling |
| React/Monaco Web-IDE | Deferred | Lightweight browser console supplied |

## Implementation decisions

1. Unsupported native execution fails closed; it never falls back and claims
   Native Mode.
2. Workspace paths are resolved before access and must remain below their
   assigned root.
3. The safety watchdog is independent of workspace logic and writes a durable
   simulated GPIO transition record.
4. Migration output is not called validated merely because it compiles. A test
   scaffold and report are generated for subsequent bag-based equivalence.

## Specification reconciliation

- Fix the duplicate `schema:` key in the supplied OpenAPI `NotFound` response.
- Decide whether simulated GPIO is a compile-time build profile (design) or a
  runtime option (TODO). The production-safe recommendation is a distinct build
  profile, with hardware mode explicit and non-default during development.
- Decide whether log polling is retained as fallback after the WebSocket service
  is introduced.

