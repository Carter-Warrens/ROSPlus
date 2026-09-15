# ROSPlus development progress

Updated 2026-09-14. This checklist describes implemented and verified behavior. It does not mark an entire sprint complete when only part of its acceptance criteria is satisfied. Original 16-week plan: `docs/specifications/todo-original.md`.

## Linux foundation

- [x] Recover source and Git history from Mac archive.
- [x] Preserve supplied requirements, design and original sprint plan.
- [x] Install workspace-local Rust and Go toolchains.
- [x] Add Rust workspace, Go module, React frontend and dependency lockfiles.
- [x] Add Makefile, CI workflow and manual release-candidate packaging workflow.
- [x] Prepare Ubuntu 24.04 / ROS 2 Jazzy installation and stock DDS smoke-test scripts.
- [x] Provide Docker-backed ROS 2 Jazzy development; host installation is optional.
- [x] Run stock C++ talker / Python listener on DDS.

## D1: Rust native executor

- [x] Preallocated in-process message pool, leases, exhaustion and spill accounting.
- [x] Node trait, priority ordering, cooperative tick loop, WCET and deadline accounting.
- [x] Disable callbacks after three consecutive completed overruns.
- [x] Linux SCHED_FIFO, affinity and memory-lock calls with actual result reporting.
- [x] Ownership-handoff microbenchmark with p50/p95/p99 and explicit scope.
- [x] rcl/RMW adapter with standard std_msgs/String type support.
- [ ] General message types, services and actions.
- [x] Dynamic transport adapter loading and Go lifecycle for built-in native endpoints.
- [x] Versioned C ABI and workspace-local arbitrary native node library loading in isolated runtime processes.
- [x] C header, Rust API crate, example plugins and graceful lifecycle callbacks.
- [ ] Multi-endpoint plugins and arbitrary ROS message types.
- [x] Native/legacy String DDS pub/sub in both directions.
- [ ] Cross-mode services.
- [ ] Inter-process zero-copy, per-node reservations and diagnostics topic.
- [x] Conservative #[no_alloc] compiler enforcement for const-compatible functions.
- [ ] Robust handling of non-returning native callbacks.
- [ ] D1 end-to-end latency/CPU/load acceptance tests on target hardware.

## D2: Legacy process supervision

- [x] Python files, built executables and ros2:package:executable targets.
- [x] ROS environment propagation and bounded log capture.
- [x] Process groups, graceful stop, forced escalation, shutdown cleanup.
- [x] Bounded restart policies and duplicate-run rejection.
- [x] Live RSS and Linux process lifetime-average CPU measurement.
- [x] Stock ROS talker/listener and cross-mode integration under supervisor.
- [ ] Restart of descendant-heavy ROS launch configurations under load.
- [ ] Measure supervision overhead against stock ROS 2; do not claim <5% yet.

## D3: Safety

- [x] Separate Rust watchdog process, Unix datagram heartbeat protocol.
- [x] Startup disarmed, stale/replayed heartbeat rejection and latched trip.
- [x] Simulated GPIO transitions and heartbeat-loss subprocess tests.
- [x] Go watchdog connection, live status and automatic node stop on monitor failure.
- [x] Test monitor crash and rejection of new runs after E-Stop.
- [x] Connect watchdog health to actual native runtime-loop progress over a private inherited pipe.
- [x] Trip simulated E-Stop when a native callback stalls or the executor exits unexpectedly.
- [ ] Physical GPIO/watchdog/relay and fail-safe hardware validation.
- [ ] Demonstrate verified 1 kHz PWM and timing bounds on real hardware.

## D4: Migration

- [x] Replace behavior-changing regex generation with conservative AST transformation.
- [x] Preserve supported pub/sub payload and callback statements.
- [x] Unsupported patterns and unvalidated results always exit nonzero.
- [x] Validation scaffolds fail instead of claiming equivalence from file existence.
- [x] Go-native bounded Python call parser with conservative warnings.
- [x] Basic parameter, repeating timer and Trigger-style service conversion helpers with explicit semantic warnings.
- [x] Execute original ROS 1 and generated ROS 2 fixtures for timer/parameter, subscriber callback and Trigger service behavior.
- [x] Build and execute one matching custom message interface with scalar, string and array fields on Noetic/Jazzy.
- [x] Record and replay equivalent native ROS 1/ROS 2 bags and compare transformed outputs exactly.
- [x] Compile and compare paired roscpp/rclcpp nodes; preserve and classify ROS 1 C++ as manual migration.
- [x] Compare paired Fibonacci actionlib/action and TF/TF2 behavior; classify source dependencies as manual.
- [ ] Generate ROS package metadata and broaden custom type mapping to services, actions and nested interfaces.
- [ ] Validate large production workspaces, direct bag-format conversion, simulated time, nodelets and dynamic reconfigure.

## D5: Go backend

- [x] Persistent workspace creation/listing/deletion and restart recovery.
- [x] File read/write/list, traversal and symlink rejection.
- [x] Serialized workspace builds using cargo, colcon or Python syntax validation.
- [x] Authenticated API and strict request-body parsing.
- [x] WebSocket logs, node updates, graph snapshots, metrics and heartbeat.
- [x] Revised OpenAPI validates and live response schemas pass.
- [x] Go race detector tests cover API, persistence, process and watchdog behavior.
- [ ] Fine-grained build progress stages and complete launch-file support.
- [ ] Multi-user isolation, resource limits and production TLS deployment validation.

## D6: Web-IDE

- [x] React node graph, movable nodes and editable connections.
- [x] Publisher/subscriber palette writes real rclpy source files.
- [x] Local Monaco editor, file browser and save action.
- [x] Simple/Expert modes and persistent mode preference.
- [x] Build/run/stop controls, live console and reconnecting WebSocket.
- [x] Browser verification of workspace creation, source loading, build and error streaming.
- [x] Graph connections apply managed-node topic remaps on next run.
- [x] Drag/drop palette and editable edge topics.
- [ ] Rust node authoring, debugger, hardware palette, REPL and hot reload.

## D7–D8: Observability and tests

- [x] Prometheus baseline and explicit unavailable runtime metrics.
- [x] JSON log records and bounded history.
- [x] Unified test command with JUnit suite output.
- [x] ROS bag record/play CLI passthrough.
- [x] Unit, API, process and watchdog integration tests.
- [x] Process CPU sampling and watchdog log rotation.
- [ ] Runtime latency histograms, diagnostics ROS topic and general log rotation.
- [x] Native vs stock rclpy comparison for 10,000 1 KiB messages at 1 kHz with load.
- [ ] Repeat benchmarks across prescribed sizes and target hardware.
- [ ] Full six-sprint end-to-end acceptance suite and compatibility corpus.

## Immediate next gate

Implement the physical GPIO/watchdog backend and qualify relay power removal and 1 kHz hold signal on target hardware. No GPIO character device, PWM device, relay, or watchdog is attached to this Linux host, and the safety binary currently rejects physical mode. Use `scripts/test_migration_validation.sh` and `scripts/test_migration_compatibility.sh` for the completed cross-version migration suites.
