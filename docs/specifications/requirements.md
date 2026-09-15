# ROSPlus Requirements Document v1.0

## Executive Summary

ROSPlus is a **Dual-Mode Runtime add-on layer** (not a fork) for ROS 2. It provides a high-performance Rust executor for native nodes while delegating legacy `rclpy`/`rclcpp` nodes to stock ROS 2 — both communicating over the same DDS/Zenoh transport. The project dramatically simplifies the developer experience via a "Simple/Expert" GUI toggle, hardens the system for real-time performance with a hardware-backed safety monitor, automates ROS 1→2 migration, and scales to multi-robot fleets.

### Core Architecture: Dual-Mode Runtime

ROSPlus operates two execution paths within a single supervisory framework:

- **Native Mode:** Nodes written in Rust (or using the ROSPlus SDK) run inside the ROSPlus Rust executor with full performance guarantees: shared memory pooling, `SCHED_FIFO` scheduling, compile-time allocation enforcement, and zero-copy transport.
- **Legacy Mode:** Existing `rclpy` and `rclcpp` nodes are spawned as standard ROS 2 subprocesses, monitored and managed by ROSPlus but executing on the stock ROS 2 executor. No code changes required.

Both modes share the same DDS/Zenoh transport layer and are managed uniformly by the ROSPlus CLI, Web-IDE, and safety monitor.

### Language Strategy

- **Rust** — Core executor, real-time scheduler, message pipeline, safety monitor, shared memory allocator.
- **Go** — Unified CLI (`turbo`), Migration Assistant, Web-IDE backend.
- **Python** — Retained for legacy ROS 2 node support. Deprecated for new performance-critical packages.
- **React/TypeScript** — Web-IDE frontend.

### Design Principles

- **Progressive Disclosure:** Complexity is hidden behind a Simple/Expert toggle. Beginners see drag-and-drop; experts see raw code, metrics, and YAML.
- **Add-On, Not a Fork:** 80% of the top 100 ROS 2 packages must run unmodified on ROSPlus.
- **Fail-Safe by Default:** The safety monitor physically cuts motor power if the software stack fails.
- **Native Installs First:** Docker is recommended but never mandatory.

---

## 1. Developer Experience & Learning Curve

### R-1.1: Zero-Config Development Environment

Users can start developing within 5 minutes without installing ROS 2 locally.

**Acceptance Criteria:**

- **AC-1.1.1:** A browser-based IDE (Web-IDE) shall be provided with a fully configured ROS 2 + Rust/Go environment.
- **AC-1.1.2:** Users may optionally download a native installer (`.deb`, `.msi`, `.pkg`) that sets up the entire toolchain without requiring Docker. Docker is recommended but not mandatory.
- **AC-1.1.3:** The system shall automatically detect connected USB cameras, LiDARs, and serial devices upon launch and populate the node palette accordingly.

### R-1.2: Intuitive Concept Visualization (Progressive Disclosure)

Nodes, topics, and communication flows are visualized as an interactive graph with complexity gated behind a toggle.

**Acceptance Criteria:**

- **AC-1.2.1:** A "Simple Mode" toggle shall hide all YAML, launch-file configurations, and raw topic data. Only high-level node descriptions and connections are shown.
- **AC-1.2.2:** "Expert Mode" reveals the underlying ROS 2 code, topic data streams, performance metrics, and launch-file YAML.
- **AC-1.2.3:** Users may drag-and-drop nodes from a palette onto a canvas. The system shall generate standard ROS 2 packages (Rust/Python/C++) behind the scenes, including `package.xml`, `CMakeLists.txt` or `Cargo.toml`, and launch files.
- **AC-1.2.4:** Double-clicking a node shall open a debugger view showing the underlying code, stack trace, recent log outputs, and per-node latency/throughput metrics.

### R-1.3: Unified CLI Experience

A single, intuitive command-line interface replaces the fragmented ROS 2 CLI.

**Acceptance Criteria:**

- **AC-1.3.1:** The CLI shall support commands: `turbo create`, `turbo build`, `turbo run`, `turbo stop`, `turbo test`, `turbo deploy`, `turbo migrate`, and `turbo benchmark`.
- **AC-1.3.2:** The CLI shall provide shell auto-completion for all subcommands, flags, and parameter values (including discovered node names and topic names).
- **AC-1.3.3:** Error messages shall include actionable suggestions with context (e.g., "Failed to find LiDAR. Did you mean /dev/ttyUSB0? Run `turbo devices` to list connected hardware.").
- **AC-1.3.4:** The CLI shall distribute as a single, statically-linked Go binary for Linux, macOS, and Windows with zero runtime dependencies.

### R-1.4: Interactive Development Environment

Built-in tools for live experimentation and debugging.

**Acceptance Criteria:**

- **AC-1.4.1:** The Web-IDE shall include a built-in REPL for live code experimentation (Python and Rust via `evcxr`).
- **AC-1.4.2:** Code changes to Python nodes shall hot-reload without requiring a full workspace rebuild.
- **AC-1.4.3:** Visual debugging shall support breakpoints, variable inspection, and topic message inspection for both Native and Legacy mode nodes.

---

## 2. Language Strategy & Dependency Management

### R-2.1: Core Runtime in Rust (Native Mode Executor)

The high-performance executor, real-time scheduler, and message pipeline are implemented in Rust.

**Acceptance Criteria:**

- **AC-2.1.1 (Throughput):** The Rust executor shall process ≥ 1,000,000 messages (1 KB each) per second without exceeding 50% CPU on an Intel i7-class (4+ core) processor.
- **AC-2.1.2 (Latency):** Native Mode nodes shall achieve ≤ 100 µs p99 intra-process latency for 1 KB messages under 80% CPU load.
- **AC-2.1.3 (Jitter):** Native Mode nodes on a standard Ubuntu kernel shall maintain < 1 ms jitter; on a PREEMPT_RT kernel, < 100 µs jitter.
- **AC-2.1.4 (Zero-Copy):** The Rust executor shall support zero-copy shared memory communication between co-located Native Mode nodes.
- **AC-2.1.5 (Footprint):** The Rust runtime shall compile to a binary < 5 MB for ARMv7 (Raspberry Pi 4) deployments.

### R-2.2: Developer Tooling in Go

The Unified CLI, Migration Assistant, and Web-IDE backend are written in Go.

**Acceptance Criteria:**

- **AC-2.2.1:** The Go-based tooling shall have no runtime dependencies (no Python, no Node.js, no JVM required to run the CLI itself).
- **AC-2.2.2:** The CLI shall install on Linux, macOS, and Windows via a single binary download or `go install`.

### R-2.3: Python Interoperability (Legacy Mode)

Existing ROS 2 Python nodes run unmodified under ROSPlus supervision.

**Acceptance Criteria:**

- **AC-2.3.1:** Legacy Mode Python nodes shall run on the stock `rclpy` executor, spawned and monitored by ROSPlus as supervised subprocesses.
- **AC-2.3.2:** The performance overhead of ROSPlus supervision (process spawning, health monitoring, log capture) shall not exceed 5% compared to running the same node via `ros2 run`.
- **AC-2.3.3:** Python dependencies shall be managed per-project using a lockfile, preventing cross-project version conflicts.

### R-2.4: C++ Interoperability (Legacy Mode)

Existing ROS 2 C++ nodes run unmodified under ROSPlus supervision.

**Acceptance Criteria:**

- **AC-2.4.1:** Legacy Mode C++ nodes shall run on the stock `rclcpp` executor, spawned and monitored by ROSPlus as supervised subprocesses.
- **AC-2.4.2:** C++ nodes compiled against standard ROS 2 libraries shall require no source changes or relinking to run under ROSPlus.

---

## 3. ROS 1 → ROS 2 Migration

### R-3.1: Automated Migration Assistant (AST-Based)

A Go-based tool that analyzes ROS 1 codebases and generates ROS 2 equivalents using Abstract Syntax Tree transformation.

**Acceptance Criteria:**

- **AC-3.1.1:** The assistant shall convert standard ROS 1 `talker/listener` and `service` nodes (Python) to ROS 2 in < 5 seconds with 100% functional accuracy.
- **AC-3.1.2:** For complex constructs (custom message types, `actionlib` servers, `tf` usage, C++ nodelets), the assistant shall generate a functionally equivalent stub in ROS 2 format and insert a `// TODO: MANUAL MIGRATION REQUIRED` annotation with a description of what needs human review.
- **AC-3.1.3:** For every migrated node, the assistant shall automatically generate a side-by-side validation test that compares the output of the original ROS 1 node against the new ROS 2 node over a recorded bag file.
- **AC-3.1.4:** Migration shall be marked "incomplete" until the generated validation test passes, preventing silent runtime failures. The `turbo migrate` command shall exit with a non-zero status code if any validation test fails.

### R-3.2a: Static Migration Mapping Table

A compile-time lookup table that maps ROS 1 API constructs to their ROS 2 equivalents, used by the Migration Assistant during code transformation.

**Acceptance Criteria:**

- **AC-3.2a.1:** The mapping table shall cover: `rospy` → `rclpy` (publishers, subscribers, services, parameters, timers, logging), `actionlib` → ROS 2 `action`, `tf` → `tf2`, `dynamic_reconfigure` → ROS 2 parameters, and standard message types.
- **AC-3.2a.2:** The mapping table shall be extensible — users can add custom message type mappings via a JSON configuration file passed to `turbo migrate --map custom_types.json`.

### R-3.2b: Runtime Message Bridge

A Rust-based runtime library that translates ROS 1 message formats to ROS 2 equivalents on the fly, enabling mixed ROS 1/ROS 2 environments during incremental migration.

**Acceptance Criteria:**

- **AC-3.2b.1:** The runtime bridge shall perform message translation with < 100 µs latency for standard message types (geometry_msgs, sensor_msgs, std_msgs).
- **AC-3.2b.2:** A node using the bridge API shall automatically detect whether it is running in a ROS 1 or ROS 2 environment at startup and select the appropriate transport.
- **AC-3.2b.3:** The bridge shall support bidirectional communication: ROS 1 nodes can publish to topics that ROS 2 nodes subscribe to, and vice versa.

---

## 4. Real-Time Safeguards

### R-4.1: Dual-Mode Real-Time Executor

The Rust executor defaults to Soft Real-Time and offers an optional Hard Real-Time mode.

**Acceptance Criteria:**

- **AC-4.1.1 (Soft-RT Default):** On a standard Ubuntu 22.04/24.04 installation under 80% CPU load, Native Mode nodes shall maintain < 1 ms jitter for priority-designated nodes using `SCHED_FIFO`.
- **AC-4.1.2 (Hard-RT Optional):** If a `PREEMPT_RT` kernel is detected at startup, the executor shall automatically enable CPU isolation (`sched_setaffinity`) and memory locking (`mlockall`), achieving < 100 µs jitter for priority-designated nodes.
- **AC-4.1.3 (Dashboard Warning):** When running in Soft-RT mode, the GUI dashboard and CLI shall display a persistent advisory: "Hard real-time disabled. Install PREEMPT_RT for deterministic control."
- **AC-4.1.4 (No Kernel Requirement):** Soft-RT mode shall require zero kernel modifications, patches, or special boot parameters. It shall work on a stock Ubuntu/Debian installation.

### R-4.2: Runtime Monitoring & Auto-Termination

The executor monitors node performance and enforces execution budgets.

**Acceptance Criteria:**

- **AC-4.2.1:** The dashboard shall display a per-node "Missed Deadlines" counter updated in real-time.
- **AC-4.2.2:** If a node exceeds its configured CPU time slice by > 10% for three consecutive scheduling cycles, the executor shall terminate and optionally restart the node, logging the event with severity WARN.
- **AC-4.2.3:** Native Mode Rust nodes annotated with `#[no_alloc]` shall fail compilation if they attempt heap allocation within the annotated scope, enforcing deterministic memory usage at compile time.
- **AC-4.2.4:** The executor shall track worst-case execution time (WCET) per node and expose it via the stats API and dashboard.

### R-4.3: Safety Monitor (Dead Man's Switch)

The safety monitor runs as a separate OS process, independent of the ROS 2 stack, and uses a hardware watchdog to enforce fail-safe behavior.

**Acceptance Criteria:**

- **AC-4.3.1 (Process Isolation):** The safety monitor shall run in its own Linux process with a dedicated memory space. It shall not link against any ROS 2 library.
- **AC-4.3.2 (Dead Man's Switch):** The safety monitor shall send a continuous 1 kHz PWM signal to a hardware watchdog timer to hold the main motor power relay closed. If the signal stops, the watchdog times out and the motors physically lose power.
- **AC-4.3.3 (Heartbeat Timeout):** If the main ROSPlus executor fails to respond to the safety monitor's heartbeat within 50 ms (Soft-RT) or 5 ms (Hard-RT), the safety monitor shall stop the PWM signal, causing the watchdog to cut motor power within 100 ms.
- **AC-4.3.4 (GPIO Simulator):** For development, CI/CD, and non-robot deployments, a GPIO simulator shall be provided that logs all signal transitions to a structured log file instead of driving physical pins. The simulator shall be the default; physical GPIO is an opt-in deployment configuration.
- **AC-4.3.5 (Self-Monitoring):** If the safety monitor process itself crashes, the absence of the PWM signal shall cause the hardware watchdog to trigger an E-Stop automatically (fail-safe by design — no software intervention required).

### R-4.4: Safety Zones & Collision Detection

Configurable software safety boundaries for spatial awareness.

**Acceptance Criteria:**

- **AC-4.4.1:** Users shall be able to define rectangular and polygonal safety zones in a YAML configuration file. When a robot's reported position enters a zone, a configurable action shall be triggered (warn, slow, stop).
- **AC-4.4.2:** Safety zone violations shall be published on a dedicated `/rosplus/safety/violations` topic for downstream consumption.

---

## 5. Scalability & Networking

### R-5.1: Hybrid Networking Architecture (Zenoh + Routers)

Replace pure DDS distributed discovery with Zenoh intelligent routers for centralized discovery and resilient communication.

**Acceptance Criteria:**

- **AC-5.1.1:** A fleet of 50 robots shall be discoverable by the central router within 10 seconds of boot.
- **AC-5.1.2:** The system shall maintain a continuous heartbeat between routers. If the primary router fails, a backup router shall assume control within 500 ms (configurable). The failover shall use a heartbeat-based leader election, not consensus protocols.
- **AC-5.1.3:** During router failover, in-flight messages shall be buffered by nodes for up to 2 seconds (configurable). No messages shall be silently dropped during a clean failover.
- **AC-5.1.4:** DDS shall remain the default transport for the PoC and single-robot deployments. Zenoh shall be an opt-in configuration for multi-robot fleets.

### R-5.2: Fixed-Chunk Message Pooling

Shared memory is pre-allocated into fixed-size chunks to prevent fragmentation and runtime allocation costs.

**Acceptance Criteria:**

- **AC-5.2.1:** The shared memory allocator shall use a slab allocator with user-configurable chunk sizes (default: 1 MB per node).
- **AC-5.2.2:** Variable-length data (e.g., point clouds, images) exceeding the chunk size shall gracefully spill to standard heap memory. When spill occurs, a performance warning shall be emitted on the `/rosplus/diagnostics` topic and shown in the GUI dashboard.
- **AC-5.2.3:** Nodes may reserve dedicated shared memory segments at startup via configuration, guaranteeing they will never face allocation failures at runtime.
- **AC-5.2.4:** Configurable shared memory allocation shall default to handling high-bandwidth sensors (4K cameras at 30 fps) without spill on a standard deployment.

### R-5.3: Orchestration Support (Optional)

Lightweight orchestration for deploying multi-robot systems.

**Acceptance Criteria:**

- **AC-5.3.1:** The system shall provide Helm charts for deploying ROSPlus nodes to a Kubernetes cluster (cloud or edge).
- **AC-5.3.2:** If the orchestration control plane becomes unreachable, nodes shall continue operating in their last known good configuration. The robot shall not stop or enter a degraded state solely due to loss of orchestration connectivity.
- **AC-5.3.3:** Predetermined failover conditions and responses shall be configurable per-node (e.g., "if network partition > 30s, switch to autonomous navigation mode").

---

## 6. Embedded & Lightweight Deployment

### R-6.1: Native Installation (No Mandatory Docker)

Docker is recommended for development and CI but not required for production deployments.

**Acceptance Criteria:**

- **AC-6.1.1:** The system shall install via `apt-get`, `cargo install`, or a shell script — not requiring a Docker pull.
- **AC-6.1.2:** The Rust runtime shall compile for and run on ARMv7 (Raspberry Pi 4) and ARMv8 (Jetson Nano/Orin) with < 256 MB RAM usage for the core executor process.
- **AC-6.1.3:** Pre-built binaries shall be provided for: x86_64 Linux, ARMv7 Linux, ARMv8 Linux. macOS and Windows binaries are provided for the CLI only (the Rust executor targets Linux).

---

## 7. Community & Ecosystem

### R-7.1: Add-On Layer Compatibility

ROSPlus is a compatibility layer that runs on top of standard ROS 2.

**Acceptance Criteria:**

- **AC-7.1.1:** 80% of the top 100 most-used ROS 2 packages on GitHub shall run unmodified on ROSPlus in Legacy Mode with zero code changes.
- **AC-7.1.2:** If a Legacy Mode package fails to run, the system shall log a clear error identifying the incompatibility and suggest a workaround or compatibility shim.
- **AC-7.1.3:** ROSPlus shall not modify, patch, or replace any files in the stock ROS 2 installation. It shall coexist cleanly with `ros2` CLI and `colcon` builds.

### R-7.2: Documentation & Tutorials (80/20 Focus)

Documentation covers the 80% use-case thoroughly.

**Acceptance Criteria:**

- **AC-7.2.1:** The documentation shall include 20 canonical tutorials covering: Installing ROSPlus, Writing a Publisher/Subscriber (Rust), Writing a Publisher/Subscriber (Python, Legacy Mode), Using a USB Camera, Integrating a LiDAR, Running Navigation (Nav2), Using the Migration Assistant, Configuring the Safety Monitor, Deploying a Multi-Robot Fleet, and Using the Web-IDE.
- **AC-7.2.2:** Every major feature (Real-Time mode, Migration Assistant, GUI, Safety Monitor) shall have a "Getting Started" tutorial with estimated completion time < 15 minutes.
- **AC-7.2.3:** API reference documentation shall be auto-generated from Rust doc comments (`cargo doc`) and Go doc comments (`go doc`).

### R-7.3: Standardized Defaults

Move the ecosystem toward sane defaults to eliminate configuration sprawl.

**Acceptance Criteria:**

- **AC-7.3.1:** The system shall auto-detect hardware parameters (baud rates, camera resolutions, USB device paths) via `udev` rules and populate default configurations, eliminating manual YAML edits for common hardware.
- **AC-7.3.2:** A "ROSPlus Standard" configuration guide shall be published, recommending default QoS settings, DDS/Zenoh profiles, network topologies, and safety zone templates for common robot archetypes (mobile base, arm, drone).

---

## 8. Observability & Diagnostics

### R-8.1: Structured Logging

All ROSPlus components emit structured, machine-parseable logs.

**Acceptance Criteria:**

- **AC-8.1.1:** All ROSPlus components (executor, safety monitor, CLI, Web-IDE backend) shall emit structured JSON logs to stdout/stderr with fields: `timestamp` (ISO 8601), `level` (DEBUG/INFO/WARN/ERROR/FATAL), `component`, `node_name` (if applicable), and `message`.
- **AC-8.1.2:** Log verbosity shall be configurable per-component and per-node at runtime via the CLI (`turbo log-level set <node> DEBUG`) or the dashboard, without restarting the node.
- **AC-8.1.3:** Logs shall be persisted to disk in a configurable log directory with automatic rotation (default: 100 MB per file, 10 files retained).

### R-8.2: Metrics & Monitoring

Runtime metrics are exposed for both internal dashboards and external monitoring systems.

**Acceptance Criteria:**

- **AC-8.2.1:** The Rust executor shall expose a Prometheus-compatible `/metrics` HTTP endpoint with gauges and histograms for: per-node CPU usage, per-node memory usage, message throughput (messages/sec), message latency (p50, p95, p99), missed deadlines count, shared memory pool utilization, and safety monitor heartbeat status.
- **AC-8.2.2:** The Web-IDE dashboard shall display real-time charts for latency, throughput, and resource usage, refreshed at ≥ 1 Hz.
- **AC-8.2.3:** The system shall support optional integration with OpenTelemetry for distributed tracing across multi-robot fleets. This is a post-PoC deliverable.

### R-8.3: Diagnostics Topic

A dedicated ROS 2 topic for system-level diagnostics.

**Acceptance Criteria:**

- **AC-8.3.1:** ROSPlus shall publish diagnostic messages to `/rosplus/diagnostics` using the standard `diagnostic_msgs/DiagnosticArray` message type, including: executor health, safety monitor status, shared memory pool usage, per-node health summary, and router connectivity (when Zenoh is enabled).
- **AC-8.3.2:** Diagnostic messages shall be published at 1 Hz minimum.

---

## 9. Security

### R-9.1: Web-IDE Authentication & Authorization

The Web-IDE shall not be accessible without authentication.

**Acceptance Criteria:**

- **AC-9.1.1:** The Web-IDE shall require authentication via username/password or API token before granting access to any workspace.
- **AC-9.1.2:** Each user shall have an isolated workspace. Users shall not be able to access, modify, or observe other users' workspaces, nodes, or logs.
- **AC-9.1.3:** The Web-IDE backend shall serve all traffic over HTTPS (TLS 1.2+). HTTP connections shall be redirected to HTTPS.

### R-9.2: Node Communication Security

Inter-node communication shall support encryption and authentication.

**Acceptance Criteria:**

- **AC-9.2.1:** ROSPlus shall support DDS Security (SROS2) for encrypted, authenticated communication between nodes. This shall be an opt-in configuration, not enabled by default (to avoid performance overhead in trusted-network deployments).
- **AC-9.2.2:** When Zenoh is used as the transport, TLS encryption shall be supported for router-to-router and node-to-router communication.
- **AC-9.2.3:** The CLI shall provide `turbo security init` to generate certificates and configure SROS2/Zenoh TLS with sane defaults.

### R-9.3: Supply Chain & Build Security

Build artifacts shall be verifiable.

**Acceptance Criteria:**

- **AC-9.3.1:** All official ROSPlus release binaries shall be signed with a GPG key published on the project website.
- **AC-9.3.2:** `Cargo.lock` and `go.sum` shall be committed to the repository. CI shall verify dependency integrity on every build.

---

## 10. Testing Infrastructure

### R-10.1: Built-In Test Harness

ROSPlus provides integrated testing capabilities for node developers.

**Acceptance Criteria:**

- **AC-10.1.1:** The `turbo test` command shall discover and run all test files in the workspace (Rust: `cargo test`, Python: `pytest`, C++: `gtest/ctest`), reporting results in a unified format.
- **AC-10.1.2:** The test harness shall support node integration tests where multiple nodes are launched, allowed to exchange messages, and then assertions are checked against recorded topic data. This shall work for both Native Mode and Legacy Mode nodes.
- **AC-10.1.3:** Test results shall be output in JUnit XML format for CI/CD integration.

### R-10.2: Bag File Support

Recording and playback of topic data for testing and debugging.

**Acceptance Criteria:**

- **AC-10.2.1:** ROSPlus shall support recording topic data to ROS 2 bag files via `turbo bag record <topics>` and playing them back via `turbo bag play <file>`.
- **AC-10.2.2:** Bag files recorded under ROSPlus shall be fully compatible with stock ROS 2 `ros2 bag` tools, and vice versa.
- **AC-10.2.3:** The Migration Assistant's side-by-side validation tests (R-3.1) shall use bag files as the canonical input/output comparison format.

### R-10.3: Simulation Integration

ROSPlus integrates with standard robotics simulators.

**Acceptance Criteria:**

- **AC-10.3.1:** ROSPlus shall support Gazebo (Harmonic+) as a simulation backend. Users shall be able to launch simulated robots via `turbo sim launch <world_file>`.
- **AC-10.3.2:** The Web-IDE shall support a "Simulation Mode" where dragged-and-dropped nodes connect to a simulated robot instead of physical hardware.
- **AC-10.3.3:** The GPIO simulator (R-4.3, AC-4.3.4) shall integrate with the simulation environment so that the safety monitor can be tested end-to-end in simulation.

### R-10.4: Performance Benchmarking

Built-in tools for measuring and comparing system performance.

**Acceptance Criteria:**

- **AC-10.4.1:** The `turbo benchmark` command shall run a standardized throughput and latency test (configurable message size, frequency, and duration) and output results in JSON and human-readable table format.
- **AC-10.4.2:** Benchmark results shall include: messages per second, p50/p95/p99 latency, CPU usage, memory usage, missed deadlines, and shared memory spill events.
- **AC-10.4.3:** The benchmark shall support A/B comparison mode: run the same workload on stock ROS 2 and ROSPlus, then output a side-by-side comparison table.

---

## 11. Non-Functional Requirements

### R-11.1: Platform Support

- **AC-11.1.1:** The full ROSPlus stack (executor, CLI, Web-IDE) shall be supported on Ubuntu 22.04 LTS and 24.04 LTS (x86_64 and ARM64).
- **AC-11.1.2:** The CLI shall additionally support macOS (Apple Silicon and Intel) and Windows 10/11 (x86_64) for remote development workflows (connecting to a Linux-based robot or server).
- **AC-11.1.3:** The Rust executor shall cross-compile for ARMv7 (Raspberry Pi 4) and ARMv8 (Jetson Nano, Jetson Orin) targets.

### R-11.2: Performance Targets (Consolidated)

All performance targets apply to Native Mode nodes unless otherwise specified.

| Metric | Target | Conditions |
|--------|--------|------------|
| Throughput | ≥ 1,000,000 msgs/sec (1 KB) | i7-class, 4+ cores, < 50% CPU |
| Intra-process latency (p99) | ≤ 100 µs | Native Mode, same process |
| Inter-process latency (p99) | ≤ 500 µs | Native Mode, shared memory |
| Jitter (Soft-RT) | < 1 ms | Stock Ubuntu, 80% CPU load |
| Jitter (Hard-RT) | < 100 µs | PREEMPT_RT kernel |
| Legacy Mode overhead | < 5% | vs. stock `ros2 run` |
| Runtime binary size | < 5 MB | ARMv7 target |
| Runtime RAM usage | < 256 MB | Core executor, no nodes |
| Safety E-Stop response | < 100 ms | From heartbeat failure to power cut |
| Router failover | < 500 ms | Heartbeat-based election |
| Fleet discovery | < 10 sec | 50 robots, Zenoh router |
| Migration (simple node) | < 5 sec | talker/listener, Python |

### R-11.3: Reliability

- **AC-11.3.1:** The ROSPlus executor shall not crash due to a single node failure. Node failures shall be isolated, logged, and optionally restarted per the node's restart policy.
- **AC-11.3.2:** The safety monitor shall achieve 99.999% uptime (< 5.26 minutes downtime per year) as measured by heartbeat continuity.

---

## 12. Implementation Priorities

| Priority | Requirement | Theme | Complexity | Dependencies |
|----------|-------------|-------|------------|--------------|
| **P0** | Web-IDE + Unified CLI (R-1.x) | DX | Medium | None |
| **P0** | Rust Executor + Shared Memory Pool (R-2.1, R-5.2) | Core | High | None |
| **P0** | Legacy Mode Subprocess Manager (R-2.3, R-2.4) | Core | Medium | R-2.1 |
| **P1** | Go-based Migration Assistant (R-3.1, R-3.2a) | Migration | Medium | R-1.3 |
| **P1** | Soft-RT Scheduler (R-4.1) | Safety | High | R-2.1 |
| **P1** | Safety Monitor + GPIO Simulator (R-4.3) | Safety | Medium | R-4.1 |
| **P1** | Structured Logging + Metrics (R-8.1, R-8.2) | Observability | Medium | R-2.1 |
| **P2** | Runtime Message Bridge (R-3.2b) | Migration | High | R-3.2a |
| **P2** | Zenoh Router Integration (R-5.1) | Scalability | Medium | None |
| **P2** | Web-IDE Authentication (R-9.1) | Security | Low | R-1.1 |
| **P2** | Test Harness + Bag Support (R-10.1, R-10.2) | Testing | Medium | R-1.3 |
| **P3** | Hard-RT PREEMPT_RT Mode (R-4.1) | Safety | Low | R-4.1 |
| **P3** | K8s Orchestration (R-5.3) | Scalability | High | R-5.1 |
| **P3** | Simulation Integration (R-10.3) | Testing | Medium | R-10.1 |
| **P3** | Node Communication Encryption (R-9.2) | Security | Medium | R-5.1 |
| **P3** | Safety Zones (R-4.4) | Safety | Low | R-4.3 |
| **P3** | OpenTelemetry Integration (R-8.2) | Observability | Medium | R-8.2 |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Native Mode** | Nodes running inside the ROSPlus Rust executor with full performance guarantees. |
| **Legacy Mode** | Stock ROS 2 nodes (`rclpy`/`rclcpp`) spawned as supervised subprocesses by ROSPlus. |
| **Soft-RT** | Soft real-time scheduling using `SCHED_FIFO` on a stock Linux kernel. Best-effort low latency. |
| **Hard-RT** | Hard real-time scheduling using `PREEMPT_RT` kernel with CPU isolation and memory locking. |
| **Dead Man's Switch** | A hardware safety mechanism where motor power requires a continuous signal; absence of the signal cuts power. |
| **Slab Allocator** | A memory allocation strategy that pre-allocates fixed-size chunks to avoid runtime allocation overhead and fragmentation. |
| **Progressive Disclosure** | A UI design pattern where complexity is hidden by default and revealed on demand. |
| **GPIO Simulator** | A software substitute for physical GPIO pins that logs signal transitions, enabling safety monitor testing without hardware. |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-20 | Kareem Williams / Claude | Initial consolidated requirements. Incorporates 23-question adversarial review, all theme decisions, Option C (Dual-Mode Runtime), Julia removed in favor of Rust/Go, GPIO simulator as default, R-3.2 split into static/runtime, performance targets reconciled, observability/security/testing sections added, product renamed to ROSPlus. |
