# ROSPlus — TODO & Sprint Plan

## PoC Scope

The Proof of Concept must demonstrate that ROSPlus can:

1. Run a standard ROS 2 talker/listener in Legacy Mode with lower overhead than expected.
2. Run a Native Mode Rust node with sub-500µs latency.
3. Migrate a simple ROS 1 node to ROS 2 automatically with zero manual intervention.
4. Provide a web-based IDE where a user can write, build, and run a node without installing anything locally.
5. Respond to safety monitor heartbeat failures by triggering E-Stop (simulated GPIO).

### PoC Exclusions

The following are explicitly out of scope for the PoC:

- Zenoh router integration (fallback to DDS discovery)
- Kubernetes orchestration
- Hard-RT (PREEMPT_RT) mode
- Full ROS 1 actionlib/tf migration (pub/sub and services only)
- Windows/macOS executor support (CLI only on those platforms)
- Runtime message bridge R-3.2b (static migration R-3.2a only)
- OpenTelemetry integration
- Node communication encryption (SROS2/TLS)
- Safety zones and collision detection

---

## Deliverables

| ID | Deliverable | Description | Acceptance Criteria | Sprint |
|----|-------------|-------------|---------------------|--------|
| D1 | Rust Executor Core | Minimal Rust executor with shared memory pooling and SCHED_FIFO scheduler | Sub-500µs p99 latency for 1KB messages at 1kHz between Native Mode nodes | S1 |
| D2 | Legacy Mode Subprocess Manager | Process manager that spawns, monitors, and captures logs from stock ROS 2 nodes | Stock ROS 2 talker/listener runs unmodified under `turbo run` | S2 |
| D3 | Safety Monitor | Separate Rust binary with heartbeat watchdog and GPIO simulator | Monitor triggers simulated E-Stop within 100ms of heartbeat failure | S2 |
| D4 | Migration Assistant CLI | Go-based AST parser that converts ROS 1 Python nodes to ROS 2 | Converts `rospy` talker to `rclpy` with 100% accuracy, generates validation test | S3 |
| D5 | Web-IDE Backend | Go HTTP server with workspace management, build scheduling, and WebSocket log streaming | User creates workspace, writes code, triggers build, sees output via WebSocket | S4 |
| D6 | Web-IDE Frontend | React SPA with node canvas, Monaco editor, Simple/Expert toggle, and live console | User drags Publisher and Subscriber nodes, connects them, runs, sees graph update | S5 |
| D7 | Observability Stack | Prometheus metrics endpoint, structured JSON logging, /rosplus/diagnostics topic | `turbo benchmark` reports p50/p95/p99 latency; Prometheus scrapes /metrics | S4 |
| D8 | Test Harness | `turbo test` command, bag file support, benchmark comparison mode | `turbo test` runs workspace tests and outputs JUnit XML | S5 |

---

## Sprint Plan (16 Weeks)

### Sprint 0: Infrastructure (Week 1)

- [ ] Initialize monorepo with directory structure per design.md
- [ ] Create `crates/Cargo.toml` workspace with empty crate stubs
- [ ] Create `pkg/go.mod` with dependency declarations
- [ ] Create `frontend/package.json` with dependency declarations
- [ ] Create top-level `Makefile` with `all`, `build`, `test`, `clean` targets
- [ ] Set up GitHub Actions CI pipeline (`.github/workflows/ci.yml`)
- [ ] Set up GitHub Actions release pipeline (`.github/workflows/release.yml`)
- [ ] Define common message types (`.proto` or `.msg` for test fixtures)
- [ ] Create GPIO simulation test harness (`scripts/gpio_simulator.py`)
- [ ] Create `tests/fixtures/` with sample ROS 1 and ROS 2 workspaces
- [ ] Write `scripts/setup_dev.sh` for developer onboarding
- [ ] Document development setup in `docs/developer_guide.md`

### Sprint 1: Rust Executor Core — D1 (Weeks 2–4)

- [ ] Implement `RuntimeConfig` and `TurboRuntime` struct
- [ ] Implement shared memory slab allocator (`shm_pool.rs`)
  - [ ] Fixed-chunk allocation with configurable chunk size
  - [ ] Free list management
  - [ ] Per-node allocation tracking
  - [ ] Pool statistics (total/used/free chunks)
  - [ ] Spill-to-heap with warning emission
- [ ] Implement `SCHED_FIFO` scheduler (`scheduler.rs`)
  - [ ] Priority levels (Critical, High, Normal, Low, Background)
  - [ ] CPU core pinning via `sched_setaffinity`
  - [ ] Deadline miss detection and logging
  - [ ] WCET tracking per node
- [ ] Implement executor spin loop (`executor.rs`)
  - [ ] Configurable tick rate
  - [ ] Node scheduling based on priority
  - [ ] Heartbeat counter for safety monitor
  - [ ] Stats collection (latency, throughput, missed deadlines)
- [ ] Implement `RosPlusNode` trait for Native Mode nodes
- [ ] Implement DDS transport bridge (`transport.rs`)
  - [ ] Topic pub/sub for Native Mode nodes
  - [ ] Shared memory zero-copy for co-located Native nodes
  - [ ] Serialization at Native→DDS boundary for cross-mode communication
- [ ] Implement error types (`error.rs`)
- [ ] Implement C FFI exports (`rosplus_bindings`)
  - [ ] `rosplus.h` header generation via `cbindgen`
  - [ ] All lifecycle, node management, and stats functions
- [ ] Write unit tests for slab allocator
- [ ] Write unit tests for scheduler
- [ ] Write throughput benchmark (criterion)
- [ ] **Milestone check:** 1KB messages at 1kHz with < 500µs p99 latency

### Sprint 2: Legacy Mode + Safety Monitor — D2, D3 (Weeks 5–7)

**Legacy Mode Subprocess Manager (D2):**
- [ ] Implement `ProcessManager` in Rust (or Go via FFI)
  - [ ] Spawn ROS 2 nodes as child processes
  - [ ] Capture stdout/stderr and forward to structured logging
  - [ ] Health monitoring via `/proc/{pid}/stat` polling
  - [ ] Graceful shutdown via SIGTERM → SIGKILL escalation
  - [ ] Configurable restart policy (never, on-failure, always)
- [ ] Implement `turbo run` integration for Legacy Mode
  - [ ] Auto-detect node type by file extension (.py → python3, .cpp → compiled binary)
  - [ ] Pass through ROS 2 environment variables (ROS_DOMAIN_ID, RMW_IMPLEMENTATION, etc.)
  - [ ] Support `--bg` for background execution
- [ ] Test with stock ROS 2 `demo_nodes_py` talker/listener
- [ ] Measure supervision overhead vs. `ros2 run` (target: < 5%)

**Safety Monitor (D3):**
- [ ] Implement `SafetyMonitor` struct (`monitor.rs`)
  - [ ] Heartbeat reception via Unix domain socket
  - [ ] Configurable timeout (default: 50ms soft-RT, 5ms hard-RT)
  - [ ] PWM signal generation (1kHz) to GPIO/simulator
  - [ ] E-Stop trigger logic
- [ ] Implement `GpioController` trait (`gpio.rs`)
  - [ ] `GpioCdev` implementation (real hardware, `gpio-cdev` crate)
  - [ ] `GpioSimulator` implementation (logs to file, `--features simulated_gpio`)
- [ ] Implement Unix domain socket protocol (`socket.rs`)
  - [ ] Binary heartbeat format (16 bytes: timestamp + node_count + flags)
  - [ ] Status response (1 byte)
- [ ] Implement `rosplus-safety` binary (`main.rs`)
  - [ ] CLI arguments: `--gpio-chip`, `--pwm-line`, `--timeout-ms`, `--simulate`
  - [ ] Daemonize option for production deployments
- [ ] Write integration test: inject heartbeat failure → verify GPIO simulator logs E-Stop
- [ ] Write integration test: safety monitor process crash → verify PWM absence
- [ ] **Milestone check:** E-Stop triggers within 100ms of heartbeat failure (simulated)

### Sprint 3: Migration Assistant — D4 (Weeks 8–9)

- [ ] Implement ROS 1 Python AST parser (`parser.go`)
  - [ ] Detect `import rospy` and `from rospy import` patterns
  - [ ] Extract publishers, subscribers, services, timers, parameters
  - [ ] Parse callback functions and message types
  - [ ] Handle multi-file packages (walk directory tree)
- [ ] Implement static mapping table (`mapper.go`)
  - [ ] `rospy.Publisher` → `rclpy.create_publisher`
  - [ ] `rospy.Subscriber` → `rclpy.create_subscription`
  - [ ] `rospy.Service` → `rclpy.create_service`
  - [ ] `rospy.Timer` → `rclpy.create_timer`
  - [ ] `rospy.init_node` → `rclpy.init` + Node class
  - [ ] `rospy.loginfo/warn/error` → `self.get_logger().info/warn/error`
  - [ ] `rospy.spin()` → `rclpy.spin(node)`
  - [ ] `rospy.get_param` → `self.declare_parameter` + `self.get_parameter`
  - [ ] Standard message type mappings
  - [ ] Support for user-provided custom mappings via JSON (`--map`)
- [ ] Implement ROS 2 code generator (`generator.go`)
  - [ ] Generate Node class with proper `__init__`, callbacks, `main()`
  - [ ] Generate `package.xml` and `setup.py`
  - [ ] Generate `// TODO: MANUAL MIGRATION REQUIRED` stubs for unsupported patterns
- [ ] Implement validation test generator (`testgen.go`)
  - [ ] Generate pytest test that launches old + new nodes
  - [ ] Compare published messages over a recording window
  - [ ] Assert message equivalence within tolerance
- [ ] Implement `turbo migrate` CLI command (`cmd/migrate.go`)
  - [ ] `--output`, `--ros1-distro`, `--ros2-distro`, `--generate-tests`, `--dry-run`, `--map`
  - [ ] JSON migration report output
  - [ ] Non-zero exit code on incomplete migration
- [ ] Test with fixture: `tests/fixtures/ros1_workspace/` talker/listener/service
- [ ] **Milestone check:** `turbo migrate tests/fixtures/ros1_workspace/ --output /tmp/ros2_ws` completes in < 5s with 100% accuracy on talker/listener

### Sprint 4: Web-IDE Backend + Observability — D5, D7 (Weeks 10–12)

**Web-IDE Backend (D5):**
- [ ] Implement `WorkspaceManager` (`workspace/manager.go`)
  - [ ] Create workspace with template (empty, talker_listener, camera)
  - [ ] List workspaces, get workspace status
  - [ ] Delete workspace (stop all nodes first)
  - [ ] Per-user isolation via filesystem directories
- [ ] Implement `BuildScheduler` (`build/scheduler.go`)
  - [ ] Detect workspace type (Rust, ROS 2, mixed)
  - [ ] Invoke `cargo build` or `colcon build`
  - [ ] Stream build output via WebSocket
  - [ ] Queue builds per workspace (no concurrent builds)
- [ ] Implement `ProcessManager` (`process/manager.go`)
  - [ ] Spawn/kill nodes by name
  - [ ] Track PIDs and process health
  - [ ] Forward stdout/stderr to WebSocket
- [ ] Implement REST API handlers (`api/rest.go`)
  - [ ] All endpoints per openapi.yaml
  - [ ] Request validation and error responses
- [ ] Implement WebSocket handler (`api/websocket.go`)
  - [ ] Subscribe/unsubscribe per workspace
  - [ ] Log streaming, node status updates, graph topology
  - [ ] Automatic reconnection with exponential backoff (client-side)
- [ ] Implement authentication middleware (`api/middleware.go`)
  - [ ] API token authentication (Bearer header)
  - [ ] CORS configuration
  - [ ] Request logging
- [ ] Implement HTTPS support (TLS 1.2+)
- [ ] Write API integration tests

**Observability (D7):**
- [ ] Implement Prometheus metrics endpoint (`metrics.rs`)
  - [ ] Per-node CPU usage gauge
  - [ ] Per-node memory usage gauge
  - [ ] Message throughput counter
  - [ ] Message latency histogram (p50, p95, p99)
  - [ ] Missed deadlines counter
  - [ ] SHM pool utilization gauge
  - [ ] Safety monitor heartbeat status gauge
- [ ] Implement structured JSON logging
  - [ ] All components: executor, safety monitor, CLI, webserver
  - [ ] Fields: timestamp, level, component, node_name, message
  - [ ] Runtime log-level adjustment via `turbo log-level set`
- [ ] Implement `/rosplus/diagnostics` topic publisher
  - [ ] `diagnostic_msgs/DiagnosticArray` format
  - [ ] 1Hz publish rate
  - [ ] Executor health, safety status, SHM usage, per-node summary
- [ ] Implement log rotation (100MB per file, 10 files retained)
- [ ] Implement `turbo benchmark` command
  - [ ] Configurable message size, frequency, duration
  - [ ] JSON + table output
  - [ ] A/B comparison mode (ROSPlus vs. stock ROS 2)

### Sprint 5: Web-IDE Frontend + Test Harness — D6, D8 (Weeks 13–15)

**Web-IDE Frontend (D6):**
- [ ] Implement node canvas (`Canvas/NodeCanvas.tsx`)
  - [ ] ReactFlow integration with custom node types
  - [ ] Drag-and-drop from palette to canvas
  - [ ] Edge rendering for topic connections
  - [ ] Node selection → property panel
- [ ] Implement node palette (`Canvas/NodePalette.tsx`)
  - [ ] Categories: Core (Publisher, Subscriber, Service, Action), Hardware (Camera, LiDAR, Motor), Safety (Safety Monitor)
  - [ ] Language badge per node type (Rust/Python/C++)
- [ ] Implement code editor (`Editor/CodeEditor.tsx`)
  - [ ] Monaco editor with Python and Rust syntax highlighting
  - [ ] File tree browser for workspace files
  - [ ] Save file → PUT to backend API
- [ ] Implement Simple/Expert toggle (`Controls/SimpleExpertToggle.tsx`)
  - [ ] Simple Mode: hide code editor, YAML, raw topic data, advanced properties
  - [ ] Expert Mode: show everything
  - [ ] Toggle state persisted in browser localStorage
- [ ] Implement live console (`Console/LogViewer.tsx`)
  - [ ] WebSocket connection to `/api/v1/workspace/{id}/logs`
  - [ ] Color-coded log levels (INFO=blue, WARN=yellow, ERROR=red, DEBUG=gray)
  - [ ] Filter by node name and severity
  - [ ] Auto-scroll with manual override
- [ ] Implement toolbar (`Controls/Toolbar.tsx`)
  - [ ] Build, Run, Stop buttons
  - [ ] Node count and status indicator
  - [ ] Average latency display
- [ ] Implement dashboard (`Dashboard/StatsPanel.tsx`)
  - [ ] CPU/memory per node
  - [ ] Latency chart (real-time, 1Hz refresh)
  - [ ] Missed deadlines counter
  - [ ] SHM pool utilization bar
- [ ] Implement responsive layout (collapse palette and properties on narrow screens)

**Test Harness (D8):**
- [ ] Implement `turbo test` command (`cmd/test.go`)
  - [ ] Discover test files (Rust: `cargo test`, Python: `pytest`, C++: `ctest`)
  - [ ] Unified output format
  - [ ] JUnit XML output (`--junit-xml output.xml`)
- [ ] Implement `turbo bag record` and `turbo bag play` commands (`cmd/bag.go`)
  - [ ] Wrapper around `ros2 bag record` and `ros2 bag play`
  - [ ] Ensure bag file format compatibility with stock ROS 2 tools
- [ ] Implement node integration test support
  - [ ] Launch multiple nodes, wait for topic messages, assert
  - [ ] Support both Native and Legacy Mode nodes in same test
- [ ] Implement `turbo benchmark` A/B comparison mode
  - [ ] Run same workload on stock ROS 2, then on ROSPlus
  - [ ] Output side-by-side table with latency, throughput, CPU, memory

### Sprint 6: Integration & Final Testing (Week 16)

- [ ] **E2E Test 1:** User writes Python node in Web-IDE → Builds → Runs in Legacy Mode → Sees output in console
- [ ] **E2E Test 2:** User writes Rust node in Web-IDE → Builds → Runs in Native Mode → Measures latency via dashboard
- [ ] **E2E Test 3:** Migration Assistant converts ROS 1 talker → Generates ROS 2 code → Validation test passes → Runs under ROSPlus
- [ ] **E2E Test 4:** Safety Monitor heartbeat failure → GPIO simulator logs E-Stop → Dashboard shows safety alert
- [ ] **E2E Test 5:** `turbo benchmark` A/B comparison → ROSPlus Native Mode shows lower latency than stock ROS 2
- [ ] **E2E Test 6:** Simple/Expert toggle → Simple Mode hides code/YAML → Expert Mode shows everything
- [ ] **E2E Test 7:** Two Legacy Mode nodes (talker + listener) + one Native Mode node (bridge) all communicate over same DDS transport
- [ ] Performance benchmark suite: compare vs. stock ROS 2 across message sizes (64B, 1KB, 64KB, 1MB)
- [ ] Generate PoC demo recording (screencast or script)
- [ ] Write PoC summary report with benchmark results

---

## Integration Test Plan

### Test Categories

| Category | Tool | Location | Trigger |
|----------|------|----------|---------|
| Rust unit tests | `cargo test` | `crates/*/tests/` | Every PR |
| Rust benchmarks | `cargo bench` | `crates/*/benches/` | Merge to main |
| Go unit tests | `go test` | `pkg/*_test.go` | Every PR |
| Frontend unit tests | `vitest` | `frontend/src/**/*.test.ts` | Every PR |
| Safety integration | `cargo test --features simulated_gpio` | `crates/rosplus_safety/tests/` | Every PR |
| API integration | `pytest` | `tests/integration/test_api.py` | Every PR |
| E2E tests | `pytest` | `tests/e2e/` | Every PR |
| Migration tests | `go test` | `pkg/migration/*_test.go` | Every PR |
| Performance benchmarks | `turbo benchmark` | `tests/benchmarks/` | Merge to main |

### Integration Test Specifications

**IT-001: Executor Lifecycle**
- Start executor with default config → verify stats show 0 nodes running
- Spawn a Native Mode test node → verify stats show 1 node running
- Kill the node → verify stats show 0 nodes running
- Stop executor → verify clean shutdown (no leaked processes)

**IT-002: Shared Memory Pool**
- Allocate N chunks → verify pool stats show N used
- Free all chunks → verify pool stats show 0 used
- Allocate beyond pool capacity → verify graceful spill to heap + warning emission
- Verify no memory leaks after repeated allocate/free cycles (valgrind)

**IT-003: SCHED_FIFO Scheduling**
- Spawn two nodes: one Critical, one Background
- Verify Critical node runs first and has lower average latency
- Verify deadline miss counter increments when a node is artificially delayed

**IT-004: Legacy Mode Subprocess Management**
- Spawn stock ROS 2 `demo_nodes_py talker` → verify process starts, PID tracked
- Verify stdout capture appears in structured logs
- Kill the node → verify process terminates, PID removed
- Spawn a node that crashes immediately → verify error logged, restart policy applied

**IT-005: Safety Monitor Heartbeat**
- Start safety monitor with 50ms timeout and GPIO simulator
- Send heartbeats every 10ms for 5 seconds → verify no E-Stop
- Stop sending heartbeats → verify E-Stop triggered within 100ms
- Verify GPIO simulator log file contains: HIGH→HIGH→...→LOW transition

**IT-006: Safety Monitor Self-Recovery**
- Start safety monitor → verify PWM signal is HIGH
- Kill safety monitor process (SIGKILL) → verify PWM signal stops (simulator logs show no more entries)
- Verify that dead man's switch behavior is inherent (no recovery needed — absence of signal IS the safety action)

**IT-007: Migration Assistant — Simple Node**
- Input: `tests/fixtures/ros1_workspace/talker.py` (rospy publisher)
- Run: `turbo migrate tests/fixtures/ros1_workspace/ --output /tmp/test_migrate`
- Verify: output file contains `rclpy` imports, Node class, `create_publisher`
- Verify: `migration_result.json` shows `files_migrated: 1`, `status: success`
- Verify: generated validation test exists and passes

**IT-008: Migration Assistant — Complex Node (Stub)**
- Input: `tests/fixtures/ros1_workspace/action_server.py` (actionlib)
- Run: `turbo migrate tests/fixtures/ros1_workspace/ --output /tmp/test_migrate`
- Verify: output file contains `// TODO: MANUAL MIGRATION REQUIRED`
- Verify: `migration_result.json` shows `files_manual: 1`, `status: partial`
- Verify: exit code is non-zero

**IT-009: Web-IDE API — Workspace Lifecycle**
- POST `/api/v1/workspace/create` → verify 201 response with workspace ID
- GET `/api/v1/workspace/{id}/status` → verify `idle` status
- POST `/api/v1/workspace/{id}/build` → verify build completes
- POST `/api/v1/workspace/{id}/run` → verify node starts
- POST `/api/v1/workspace/{id}/stop` → verify node stops
- DELETE `/api/v1/workspace/{id}` → verify workspace removed

**IT-010: Web-IDE WebSocket — Log Streaming**
- Connect WebSocket to `/api/v1/workspace/{id}/logs`
- Send `{"type": "subscribe", "workspace_id": "..."}`
- Run a node → verify log messages arrive via WebSocket
- Verify messages have correct JSON structure (timestamp, severity, node, message)

**IT-011: Cross-Mode Communication**
- Spawn a Native Mode publisher (Rust) on `/test_topic`
- Spawn a Legacy Mode subscriber (Python) on `/test_topic`
- Publish 100 messages from Native node
- Verify Legacy node receives all 100 messages via topic subscription
- Measure inter-mode latency (target: < 1ms for 1KB messages)

**IT-012: Prometheus Metrics**
- Start executor with 2 nodes running
- GET `/metrics` → verify response contains Prometheus text format
- Verify presence of: `rosplus_node_cpu_usage`, `rosplus_message_throughput`, `rosplus_message_latency_seconds`, `rosplus_shm_pool_utilization`

**IT-013: Benchmark A/B Comparison**
- Run `turbo benchmark --ab --duration 10s --message-size 1024`
- Verify output contains both "Stock ROS 2" and "ROSPlus Native" columns
- Verify output includes p50, p95, p99 latency and messages/sec

**IT-014: `turbo test` Command**
- Create workspace with a Python test file and a Rust test file
- Run `turbo test --junit-xml results.xml`
- Verify both test suites ran
- Verify `results.xml` is valid JUnit XML

---

## Risk Register

| ID | Risk | Impact | Likelihood | Mitigation |
|----|------|--------|------------|------------|
| R1 | Rust FFI with Python (pyo3) is too slow for Native Mode Python interop | High | Medium | PoC uses Legacy Mode (subprocess) for Python. Native Mode Python interop is a future optimization. Benchmark pyo3 overhead early. |
| R2 | Web-IDE sandbox is insecure (user code execution on server) | High | High | Use containerized sandboxes (Docker) per workspace for the PoC, even though Docker is not mandatory for production. Rate-limit workspace creation. |
| R3 | GPIO not available in CI environments | Medium | Certain | GPIO simulator is the default (`--features simulated_gpio`). All CI tests use the simulator. Real GPIO tested manually on hardware. |
| R4 | Migration Assistant fails on complex Python patterns | Medium | High | Focus PoC on 80% (pub/sub, timers, parameters, services). Generate TODO stubs for complex patterns. The 80/20 rule is explicitly documented. |
| R5 | WebSocket connections drop under load | Low | Medium | Implement automatic reconnection with exponential backoff on the frontend. Server-side heartbeat every 5s to detect stale connections. |
| R6 | SCHED_FIFO requires root or CAP_SYS_NICE | Medium | Certain | Document the capability requirement. Provide `setup_dev.sh` that configures `setcap cap_sys_nice+ep` on the executor binary. Fall back to SCHED_OTHER with a warning. |
| R7 | Shared memory pool exhaustion under high load | Medium | Medium | Configurable pool size per node. Spill-to-heap with visible warning. Monitor via Prometheus gauge. Recommend sizing in documentation. |
| R8 | `ros2_rust` client library is immature | Medium | Medium | Minimize dependency on `rclrs`. Implement topic pub/sub directly via DDS C bindings where necessary. Contribute upstream fixes. |
| R9 | Cobra/Viper Go CLI adds binary size | Low | Certain | Go binary ~15MB is acceptable for the CLI. The Rust executor (< 5MB) is the binary that runs on embedded targets. |
| R10 | Cross-compilation for ARMv7 is painful | Medium | Medium | Provide cross-compilation Docker image for CI. Test on real Pi 4 hardware monthly. Use `cross` (Rust cross-compilation tool). |

---

## Post-PoC Roadmap (Not Scoped)

These items are tracked for future planning but are not part of the 16-week PoC:

- [ ] Zenoh router integration (R-5.1)
- [ ] Hard-RT PREEMPT_RT mode (R-4.1, AC-4.1.2)
- [ ] Runtime message bridge R-3.2b
- [ ] Kubernetes/Helm orchestration (R-5.3)
- [ ] OpenTelemetry distributed tracing (R-8.2, AC-8.2.3)
- [ ] Node communication encryption SROS2/TLS (R-9.2)
- [ ] Safety zones and collision detection (R-4.4)
- [ ] Simulation integration with Gazebo (R-10.3)
- [ ] C++ Migration Assistant support
- [ ] Windows/macOS executor support
- [ ] Multi-user Web-IDE with role-based access control
- [ ] Plugin system for third-party node templates
- [ ] Visual URDF editor in Web-IDE
- [ ] Fleet management dashboard
