# Implementation status — Linux development checkpoint

Updated 2026-09-14. The original requirements remain the target; [todo](../todo.md) records incomplete acceptance work.

| Component | Implemented and verified | Remaining boundary |
|---|---|---|
| Go API/CLI | Workspaces, files, builds, process groups, restarts, authenticated WebSockets, CPU/RSS; race tests pass | Trusted local programs; no multi-user sandbox |
| React workbench | Monaco, palette, editable graph, managed-topic remapping, build/run/stop and live logs | Debugger, Rust authoring and hardware palette remain open |
| ROS integration | Stock C++/Python and Rust String DDS; native/legacy in both directions; ABI-v1 C/Rust plugins loaded from workspaces in isolated runtime processes | Arbitrary messages, services/actions and multi-endpoint plugins remain open |
| Rust SDK | In-process pool, cooperative budgets, actual scheduling calls, conservative const-based no_alloc | No process-shared pool or preemption of non-returning callbacks |
| Safety | Independent Rust watchdog, replay rejection, latched simulated stop, bounded log rotation, per-native-runtime progress pipes | Physical GPIO, relay and motor-power cutoff remain unverified |
| Migration | Go-native bounded Python call parser; live bag replay; custom message build/use; compiled C++, action and TF paired-port checks; explicit manual C++/actionlib/TF classification | Automatic C++/actionlib/TF conversion, package generation and production workspace corpus remain open |
| Contract/tooling | OpenAPI validates; local tests, clippy, go vet and frontend build pass | CI workflows have not run remotely |

## Evidence

Reports are saved in [reports](../reports/). `local-verification.log` and `test-results.xml` record the local suites. DDS and supervised-DDS reports record real communication through ROS 2 Jazzy in Docker. The browser was exercised against the container service, including a real colcon package build and native publisher/Python listener execution.

`migration-comparison.json` compares ten messages from the supplied ROS 1 constant-payload talker with the Go-generated ROS 2 node. `migration-validation-broader.json` adds a parameterized timer, a subscriber callback that transforms payloads, and an `std_srvs/Trigger` service. Original ROS 1 and generated ROS 2 behavior matched for all three bounded scenarios. Timer comparison permits a different initial counter during graph discovery while requiring the configured parameter and five consecutive counters. These are live fixture checks, not general recorded-bag, timing, custom-interface, or arbitrary-code equivalence.

`migration-compatibility.json` records a second passing corpus: native ROS 1 and ROS 2 bag record/replay with exact transformed outputs, automatic Python conversion using a generated custom message with scalar/string/array fields, compiled roscpp/rclcpp processors, Fibonacci action result/feedback, and TF/TF2 transforms. C++, actionlib and TF use explicit paired manual ports, and the migration report proves their ROS 1 inputs are classified as partial/manual instead of being silently omitted or reported as converted.

## Transport measurements

One same-host sequential run per implementation: 10,000 messages of 1 KiB at 1 kHz, stock RMW, FIFO successfully enabled in a bounded container test with SYS_NICE.

| Implementation | Received | p99 | Maximum | Measured background load |
|---|---:|---:|---:|---:|
| Rust String endpoint | 10,000 | 51.876 µs | 526.249 µs | 80.85% |
| Stock rclpy endpoint | 10,000 | 106.939 µs | 349.596 µs | 78.23% |

See `benchmark-comparison.json` for timing scope and actual scheduling. The configured load was the same but measured background load differed. These results do not establish a universal speedup, hard real-time behavior, arbitrary executor performance or physical safety. A normal-scheduling loaded run measured approximately 2.94 ms p99 and missed the latency target (`dds-latency-loaded.json`). The default workbench uses normal scheduling.

The separate ownership-handoff microbenchmark excludes DDS, serialization and executor dispatch and must not substitute for transport measurements.

## Development environment

Host ROS installation is optional. `bash scripts/start_container.sh` builds/starts the workbench with ROS 2 Jazzy. `bash scripts/test_container.sh` repeats stock DDS and supervised cross-mode checks. Neither launcher grants physical device access. See the README for native host setup if desired.
