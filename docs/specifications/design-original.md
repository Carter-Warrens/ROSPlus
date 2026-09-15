# ROSPlus Design Document v1.0

## Table of Contents

1. Architecture Overview
2. Dual-Mode Runtime Design
3. Component Architecture
4. API Boundaries
5. Project Structure
6. Build Configuration
7. CI/CD Pipeline
8. Technology Decisions & Rationale

---

## 1. Architecture Overview

ROSPlus is a Dual-Mode Runtime add-on layer for ROS 2. It sits above the stock ROS 2 installation, providing a high-performance Rust executor for native nodes while delegating legacy nodes to stock ROS 2 as supervised subprocesses. Both execution paths share the same DDS/Zenoh transport layer and are managed uniformly by the ROSPlus supervisory layer.

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Web-IDE (React/TS)                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │ Canvas (Drag- │    │ Code Editor  │    │ Console / Output Panel   │  │
│  │ Drop Nodes)   │    │ (Monaco)     │    │                          │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────┬───────────────┘  │
└─────────┼───────────────────┼───────────────────────┼──────────────────┘
          │ (WebSocket/HTTP)   │                       │
          ▼                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Web-IDE Backend (Go)                                  │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ Workspace        │  │ Build Scheduler  │  │ Process Manager      │  │
│  │ Manager (per-    │  │ (cargo/colcon    │  │ (spawns isolated     │  │
│  │ user sandbox)    │  │  wrapper)        │  │  ROS environments)   │  │
│  └────────┬────────┘  └────────┬─────────┘  └───────────┬──────────┘  │
└───────────┼───────────────────┼────────────────────────┼───────────────┘
            │                   │                        │
            ▼                   ▼                        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          ROSPlus Runtime                                   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                  Supervisory Layer (Rust)                            │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │  │
│  │  │ Process      │  │ Health       │  │ Metrics / Prometheus     │   │  │
│  │  │ Manager      │  │ Monitor      │  │ Endpoint                 │   │  │
│  │  └──────┬──────┘  └──────┬───────┘  └──────────────────────────┘   │  │
│  └─────────┼───────────────┼──────────────────────────────────────────┘  │
│            │               │                                              │
│  ┌─────────▼───────────────▼──────────────────────────────────────────┐  │
│  │               Native Mode (Rust Executor)                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────────┐  │  │
│  │  │ SCHED_FIFO   │  │ Shared      │  │ Zero-Copy Pub/Sub        │  │  │
│  │  │ Scheduler    │◄─┤ Memory Pool │◄─┤                           │  │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │               Legacy Mode (Supervised Subprocesses)                │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐    │  │
│  │  │ rclpy Node   │  │ rclcpp Node  │  │ rclcpp Node          │    │  │
│  │  │ (Python)     │  │ (C++)        │  │ (C++)                │    │  │
│  │  │ [subprocess] │  │ [subprocess] │  │ [subprocess]         │    │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│            ┌──────────────────────────────────┐                           │
│            │ DDS / Zenoh Transport Layer       │                           │
│            │ (shared by Native + Legacy nodes) │                           │
│            └──────────────────────────────────┘                           │
│                                                                           │
│                          │ (Heartbeat via Unix Socket)                    │
│                          ▼                                                │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │               Safety Monitor (Rust, Separate Process)              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────────┐ │  │
│  │  │ Watchdog     │  │ GPIO / GPIO │  │ Process Health            │ │  │
│  │  │ Timer        │──│ Simulator   │──│ Monitor                   │ │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────────────┘ │  │
│  └───────────────────────────┬────────────────────────────────────────┘  │
│                              │ (GPIO Signal / Simulated Log)             │
│                              ▼                                            │
│                      [Hardware Relay / E-Stop]                            │
└───────────────────────────────────────────────────────────────────────────┘

                       ┌──────────────────────┐
                       │  Migration Assistant  │
                       │  (Go CLI)             │
                       │  ┌─────────────────┐  │
                       │  │ AST Parser      │  │
                       │  │ + Mapping Table  │  │
                       │  │ + Test Generator │  │
                       │  └─────────────────┘  │
                       └──────────────────────┘
```

### Data Flow

1. **User writes code** in Web-IDE (or local editor) and triggers `turbo build`.
2. **Build Scheduler** detects language, invokes `cargo build` (Rust) or `colcon build` (C++/Python).
3. **User runs `turbo run`** — the Supervisory Layer determines node type:
   - Rust node → loaded into Native Mode executor (in-process, shared memory).
   - Python/C++ node → spawned as Legacy Mode subprocess (stock ROS 2 executor).
4. **Both node types** publish/subscribe over the same DDS/Zenoh transport.
5. **Safety Monitor** receives heartbeats from the Supervisory Layer via Unix domain socket. If heartbeats stop, PWM signal stops, hardware watchdog cuts motor power.
6. **Metrics** are scraped by Prometheus from the `/metrics` endpoint, and diagnostic messages are published on `/rosplus/diagnostics`.

---

## 2. Dual-Mode Runtime Design

### Native Mode

Native Mode nodes are compiled Rust libraries loaded directly into the ROSPlus executor process. They benefit from:

- **Zero-copy shared memory:** Messages passed between co-located Native nodes never leave the shared memory pool.
- **SCHED_FIFO scheduling:** The executor thread runs at elevated Linux priority with optional CPU pinning.
- **Compile-time allocation enforcement:** Nodes annotated with `#[no_alloc]` cannot allocate heap memory, guaranteeing deterministic execution.
- **Sub-100µs latency:** Intra-process message passing avoids serialization entirely.

Native Mode nodes implement the `RosPlusNode` trait:

```rust
pub trait RosPlusNode: Send + Sync {
    fn init(&mut self, context: &NodeContext) -> Result<(), NodeError>;
    fn spin_once(&mut self) -> Result<SpinResult, NodeError>;
    fn shutdown(&mut self) -> Result<(), NodeError>;
    fn node_info(&self) -> NodeInfo;
}
```

### Legacy Mode

Legacy Mode nodes are standard ROS 2 executables spawned as child processes by the ROSPlus Supervisory Layer. They run on stock `rclpy` or `rclcpp` executors with no modification. The Supervisory Layer provides:

- **Process lifecycle management:** Start, stop, restart, health check.
- **Log capture:** stdout/stderr captured, parsed, and forwarded to the structured logging pipeline.
- **Resource monitoring:** CPU, memory, and thread count tracked per subprocess.
- **Graceful degradation:** If a Legacy node crashes, it is isolated and optionally restarted per its restart policy. Other nodes are unaffected.

### Inter-Mode Communication

Native and Legacy nodes communicate over the same DDS/Zenoh transport layer. From the perspective of topic discovery and message exchange, there is no distinction between a Native publisher and a Legacy publisher. The transport layer handles serialization/deserialization at the boundary.

For co-located Native nodes, shared memory bypasses the transport layer entirely. When a Native node publishes to a topic that a Legacy node subscribes to, the message is serialized once at the Native→DDS boundary and delivered via standard DDS to the Legacy subprocess.

---

## 3. Component Architecture

### 3.1 Rust Executor Core (`turboros_core`)

The central runtime that manages Native Mode nodes.

**Responsibilities:**
- Spin loop with configurable tick rate
- SCHED_FIFO scheduling with priority levels (Critical, High, Normal, Low, Background)
- Shared memory slab allocator (fixed-chunk, user-configurable chunk size)
- Node lifecycle (spawn, health check, kill, restart)
- Heartbeat emission to Safety Monitor
- Stats collection and Prometheus endpoint

**Key Data Structures:**

```rust
pub struct RuntimeConfig {
    pub scheduler: String,          // "SCHED_FIFO" or "SCHED_OTHER"
    pub cpu_core: u32,              // CPU core to pin to (0 = no pinning)
    pub shm_pool_size_mb: u32,      // Shared memory per node (default: 16)
    pub heartbeat_interval_ms: u32, // Heartbeat period (default: 10)
    pub max_nodes: u32,             // Maximum nodes (default: 100)
    pub node_timeout_secs: u32,     // Auto-terminate timeout (0 = disabled)
}

pub enum Priority {
    Critical = 100,
    High = 75,
    Normal = 50,
    Low = 25,
    Background = 0,
}
```

### 3.2 FFI Bridge (`turboros_ffi`)

Provides C-compatible FFI exports so the Go CLI and Web-IDE backend can control the Rust executor via `cgo`.

**Design Decisions:**
- All FFI functions use `extern "C"` with `#[no_mangle]`.
- Opaque pointers (`*mut TurboRuntime`) are used for runtime handles.
- Errors are returned via out-parameters (`*mut *const RuntimeError`).
- Strings returned by the runtime must be freed with `turboros_string_free()`.
- Python interop uses `pyo3` with `prepare_freethreaded_python()` for GIL management.

### 3.3 Safety Monitor (`turboros_safety`)

A standalone Rust binary (not a library) that runs in its own process.

**Design Decisions:**
- Communicates with the main executor via Unix domain socket (not DDS/Zenoh — the safety monitor must not depend on the ROS 2 stack).
- GPIO abstraction trait (`GpioController`) with two implementations: `GpioCdev` (real hardware) and `GpioSimulator` (CI/testing).
- The simulator is a compile-time feature flag (`--features simulated_gpio`), not a runtime toggle.
- Fail-safe by design: if the safety monitor process crashes, the absence of the PWM signal triggers the hardware watchdog automatically. No software recovery path is needed.

### 3.4 Go CLI (`pkg/cli`)

A single `turbo` binary built with `cobra` for command structure and `viper` for configuration.

**Command Tree:**
```
turbo
├── create [name]         # Create workspace or node
│   ├── --template        # workspace, node, talker, camera, migration
│   └── --language        # python, rust, cpp
├── build                 # Build workspace
│   ├── --release         # Release mode
│   └── --target          # Specific package
├── run [target]          # Run node or launch file
│   ├── --bg              # Background mode
│   └── --no-build        # Skip build step
├── stop [node-name]      # Stop node(s)
├── test                  # Run tests
├── deploy                # Deploy to target
├── migrate [source]      # ROS 1 → ROS 2 migration
│   ├── --output          # Output directory
│   ├── --ros1-distro     # Source distro
│   ├── --ros2-distro     # Target distro
│   ├── --generate-tests  # Auto-generate validation tests
│   ├── --dry-run         # Analyze without writing
│   └── --map             # Custom message type mapping JSON
├── benchmark             # Run performance benchmarks
├── bag                   # Bag file operations
│   ├── record            # Record topics
│   └── play              # Play bag file
├── sim                   # Simulation
│   └── launch            # Launch simulator
├── devices               # List connected hardware
├── log-level             # Adjust log verbosity
│   └── set [node] [level]
├── security              # Security tools
│   └── init              # Generate certificates
└── version               # Version info
```

### 3.5 Migration Assistant (`pkg/cli/migration`)

An AST-based code transformer written in Go.

**Pipeline:**
1. **Parse:** Walk source directory, identify ROS 1 files by import patterns (`rospy`, `roscpp`).
2. **Analyze:** Parse Python files into structured `Node` representations (publishers, subscribers, services, parameters).
3. **Map:** Apply the static mapping table (R-3.2a) to transform API calls. For known patterns (pub/sub, timers, logging), generate ROS 2 equivalents automatically. For unknown patterns, generate a stub with `// TODO: MANUAL MIGRATION REQUIRED`.
4. **Generate:** Write ROS 2 Python/C++ files to the output directory.
5. **Test:** For each migrated node, generate a GoogleTest/pytest comparison test that runs the original and migrated nodes against a recorded bag file and asserts output equivalence.
6. **Report:** Write `migration_result.json` with file counts, warnings, and test paths.

**80/20 Rule:** The assistant targets 80% automatic conversion coverage. The remaining 20% (custom messages, actionlib, tf, C++ templates, nodelets) gets stubs and tests. The migration is marked "incomplete" until all generated tests pass.

### 3.6 Web-IDE Backend (`pkg/webserver`)

A Go HTTP server built with `gin` for REST and `gorilla/websocket` for live updates.

**Design Decisions:**
- Per-user workspace isolation via filesystem directories (no shared state between users).
- Build jobs are queued and executed sequentially per workspace (no concurrent builds on the same workspace).
- WebSocket connections deliver log streams, node status updates, and graph topology changes.
- The backend calls the Rust executor via `cgo` FFI for runtime control (start, stop, spawn, kill, stats).

### 3.7 Web-IDE Frontend (`frontend`)

A React/TypeScript SPA using:
- **ReactFlow** for the node graph canvas (drag-and-drop, edge rendering).
- **Monaco Editor** for the code editor (same engine as VS Code).
- **Zustand** for state management.
- **Apollo Client** for GraphQL subscriptions (live updates).
- **Tailwind CSS** for styling.

---

## 4. API Boundaries

All APIs use semantic versioning (`v1/*`). Breaking changes require a new API version.

### Boundary A: Go Tooling ↔ Rust Executor (C FFI)

The Go CLI controls the Rust executor via C-compatible FFI functions exported from `turboros_bindings`.

```c
// turboros.h — C header for Go cgo

// Lifecycle
TurboRuntime* turboros_runtime_new(
    const char* scheduler, uint32_t cpu_core,
    uint32_t shm_pool_size_mb, uint32_t heartbeat_interval_ms,
    uint32_t max_nodes, uint32_t node_timeout_secs,
    RuntimeError** error_out);
uint32_t turboros_runtime_start(TurboRuntime* runtime, RuntimeError** error_out);
uint32_t turboros_runtime_stop(TurboRuntime* runtime, RuntimeError** error_out);
void turboros_runtime_drop(TurboRuntime* runtime);

// Node Management
uint32_t turboros_runtime_spawn_node(
    TurboRuntime* runtime,
    const char* node_path, const char* node_name,
    const char* namespace, const char** args,
    RuntimeError** error_out);
uint32_t turboros_runtime_kill_node(
    TurboRuntime* runtime, const char* node_name,
    RuntimeError** error_out);

// Stats & Heartbeat
const char* turboros_runtime_get_stats(
    TurboRuntime* runtime, RuntimeError** error_out);
uint32_t turboros_runtime_send_heartbeat(
    TurboRuntime* runtime, RuntimeError** error_out);

// Memory
void turboros_string_free(char* s);
```

**Conventions:**
- Return `0` for success, non-zero for error.
- Error details via `RuntimeError** error_out` (code + message).
- Strings returned by the runtime must be freed with `turboros_string_free()`.
- NULL-terminated arrays for variadic arguments (`args`).

### Boundary B: Rust Executor ↔ Python Nodes (pyo3 FFI)

For Native Mode Python interop (future — currently Legacy Mode uses subprocesses):

```c
PythonNode* turboros_python_node_create(
    const char* module_name, const char* class_name,
    FfiError** error_out);
uint32_t turboros_python_node_init(
    PythonNode* node, const char* args_json,
    FfiError** error_out);
int32_t turboros_python_node_spin_once(
    PythonNode* node, FfiError** error_out);
uint32_t turboros_python_node_destroy(
    PythonNode* node, FfiError** error_out);
const char* turboros_python_node_get_name(
    PythonNode* node, FfiError** error_out);
```

### Boundary C: Migration Assistant Internal API (Go)

```go
type MigrationConfig struct {
    SourcePath     string            `json:"source_path"`
    OutputPath     string            `json:"output_path"`
    Ros1Distro     string            `json:"ros1_distro"`
    Ros2Distro     string            `json:"ros2_distro"`
    GenerateTests  bool              `json:"generate_tests"`
    RunTests       bool              `json:"run_tests"`
    MessageTypeMap map[string]string `json:"message_type_map"`
}

type MigrationResult struct {
    FilesAnalyzed int                `json:"files_analyzed"`
    FilesMigrated int                `json:"files_migrated"`
    FilesManual   int                `json:"files_manual"`
    Warnings      []MigrationWarning `json:"warnings"`
    TestFiles     []string           `json:"test_files"`
    Status        string             `json:"status"` // "success", "partial", "failed"
}

func RunMigration(config *MigrationConfig) (*MigrationResult, error)
func ParseROS1Node(filePath string) ([]Node, error)
func GenerateROS2Node(node *Node, config *MigrationConfig) (string, error)
func GenerateComparisonTest(ros1BagPath, ros2Workspace, nodeName string) (string, error)
```

### Boundary D: Web-IDE Backend REST API

See `openapi.yaml` for the full specification. Summary of endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/workspace/create` | Create new workspace |
| GET | `/api/v1/workspace/{id}` | Get workspace details |
| GET | `/api/v1/workspace/{id}/status` | Get workspace status |
| DELETE | `/api/v1/workspace/{id}` | Delete workspace |
| GET | `/api/v1/workspace/{id}/files` | List workspace files |
| GET | `/api/v1/workspace/{id}/file/{path}` | Get file contents |
| PUT | `/api/v1/workspace/{id}/file/{path}` | Save file contents |
| POST | `/api/v1/workspace/{id}/build` | Trigger build |
| POST | `/api/v1/workspace/{id}/run` | Run node or launch file |
| POST | `/api/v1/workspace/{id}/stop` | Stop node(s) |
| GET | `/api/v1/workspace/{id}/graph` | Get node graph topology |
| GET | `/api/v1/workspace/{id}/logs` | WebSocket log stream |
| GET | `/api/v1/workspace/{id}/metrics` | Get runtime metrics |
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |

### Boundary E: Web-IDE WebSocket Protocol

Messages are JSON objects with a `type` field:

**Client → Server:**
```json
{"type": "subscribe", "workspace_id": "abc123"}
{"type": "unsubscribe", "workspace_id": "abc123"}
{"type": "command", "workspace_id": "abc123", "action": "restart_node", "node": "talker"}
```

**Server → Client:**
```json
{"type": "log", "workspace_id": "abc123", "timestamp": "...", "severity": "info", "node": "talker", "message": "..."}
{"type": "node_update", "workspace_id": "abc123", "nodes": [...]}
{"type": "graph_update", "workspace_id": "abc123", "nodes": [...], "edges": [...]}
{"type": "heartbeat", "timestamp": "..."}
{"type": "build_progress", "workspace_id": "abc123", "stage": "compiling", "progress": 0.75}
{"type": "metrics", "workspace_id": "abc123", "data": {...}}
```

### Boundary F: Safety Monitor ↔ Executor (Unix Domain Socket)

The safety monitor communicates with the executor over a Unix domain socket at `/tmp/rosplus_safety.sock`. Protocol is a simple binary heartbeat:

```
Executor → Safety Monitor:
  [8 bytes] timestamp (nanoseconds since epoch, little-endian u64)
  [4 bytes] node_count (little-endian u32)
  [4 bytes] flags (bit 0: executor_healthy, bit 1: all_nodes_ok)

Safety Monitor → Executor:
  [1 byte]  status (0x00 = OK, 0x01 = E-Stop triggered, 0xFF = monitor shutting down)
```

No JSON, no serialization libraries. The protocol must be parseable in < 1 µs.

---

## 5. Project Structure

```
rosplus/
├── README.md
├── LICENSE                           # Apache-2.0
├── CONTRIBUTING.md
├── Makefile                          # Top-level build orchestration
├── .gitignore
├── .github/
│   └── workflows/
│       ├── ci.yml                    # CI pipeline
│       └── release.yml               # Release automation
│
├── crates/                           # Rust workspace
│   ├── Cargo.toml                    # Workspace definition
│   ├── Cargo.lock
│   │
│   ├── rosplus_core/                 # Core executor
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── executor.rs           # Scheduler & spin loop
│   │       ├── node.rs               # Node lifecycle management
│   │       ├── shm_pool.rs           # Shared memory slab allocator
│   │       ├── scheduler.rs          # Priority-based scheduling
│   │       ├── message.rs            # Message type definitions
│   │       ├── transport.rs          # DDS/Zenoh bridge
│   │       ├── metrics.rs            # Prometheus endpoint
│   │       ├── stats.rs              # Performance statistics
│   │       └── error.rs              # Error types
│   │
│   ├── rosplus_ffi/                  # C++/Python interop bridge
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── cpp_bridge.rs         # C++ FFI bindings
│   │       ├── python_bridge.rs      # Python FFI (pyo3)
│   │       ├── message_conversion.rs # ROS 1↔ROS 2 runtime mapping (R-3.2b)
│   │       └── shared_memory.rs      # SHM access for FFI
│   │
│   ├── rosplus_safety/               # Safety Monitor (standalone binary)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── main.rs               # Binary entry point
│   │       ├── monitor.rs            # Heartbeat watchdog
│   │       ├── gpio.rs               # GPIO abstraction (real + simulated)
│   │       ├── estop.rs              # E-Stop logic & dead man's switch
│   │       ├── socket.rs             # Unix domain socket protocol
│   │       └── config.rs             # Configuration parsing
│   │
│   └── rosplus_bindings/             # C-compatible API for Go cgo
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs
│       │   └── go_ffi.rs             # Exports C-callable functions
│       ├── include/
│       │   └── rosplus.h             # C header for Go cgo
│       └── build.rs                  # Header generation (cbindgen)
│
├── pkg/                              # Go packages
│   ├── go.mod
│   ├── go.sum
│   │
│   ├── cli/                          # CLI binary
│   │   ├── main.go                   # Entry point: `turbo` command
│   │   └── cmd/
│   │       ├── create.go
│   │       ├── build.go
│   │       ├── run.go
│   │       ├── stop.go
│   │       ├── test.go
│   │       ├── deploy.go
│   │       ├── migrate.go
│   │       ├── benchmark.go
│   │       ├── bag.go
│   │       ├── sim.go
│   │       ├── devices.go
│   │       ├── log_level.go
│   │       ├── security.go
│   │       └── version.go
│   │
│   ├── migration/                    # AST parser & code generator
│   │   ├── parser.go                 # ROS 1 Python AST parser
│   │   ├── mapper.go                 # Static mapping table (R-3.2a)
│   │   ├── generator.go              # ROS 2 code generator
│   │   ├── testgen.go                # Validation test generator
│   │   └── models.go                 # Data models
│   │
│   ├── runtime/                      # Go wrapper around Rust FFI
│   │   └── runtime.go                # cgo bindings to rosplus_bindings
│   │
│   └── webserver/                    # Web-IDE Backend
│       ├── main.go                   # Entry point
│       ├── api/
│       │   ├── rest.go               # REST handlers
│       │   ├── websocket.go          # WebSocket handler
│       │   └── middleware.go         # Auth, CORS, logging
│       ├── workspace/
│       │   ├── manager.go            # Per-user workspace isolation
│       │   └── templates/            # Project templates
│       │       ├── empty/
│       │       ├── talker_listener/
│       │       └── camera/
│       ├── build/
│       │   └── scheduler.go          # Build job queue
│       └── process/
│           └── manager.go            # Spawn/kill ROS processes
│
├── frontend/                         # Web-IDE Frontend (React/TS)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── Canvas/               # Drag-and-drop node graph
│       │   ├── Editor/               # Monaco code editor
│       │   ├── Console/              # Log viewer & terminal
│       │   ├── Controls/             # Toolbar, Simple/Expert toggle
│       │   └── Dashboard/            # Stats, node health
│       ├── hooks/                    # useWebSocket, useWorkspace, useGraph
│       ├── api/                      # REST & WebSocket clients
│       └── styles/
│
├── examples/                         # Example projects
│   ├── talker_listener/
│   ├── camera_publisher/
│   └── migration_test/               # ROS 1 code for testing migration
│
├── tests/                            # End-to-end & integration tests
│   ├── e2e/
│   ├── integration/
│   └── fixtures/
│       ├── ros1_workspace/
│       ├── ros2_workspace/
│       └── bag_files/
│
├── docs/                             # Documentation
│   ├── requirements.md
│   ├── design.md
│   ├── todo.md
│   ├── openapi.yaml
│   ├── api_reference.md
│   └── tutorials/
│
└── scripts/                          # Build & deployment scripts
    ├── setup_dev.sh
    ├── build_all.sh
    ├── run_tests.sh
    └── gpio_simulator.py             # GPIO mock for CI
```

---

## 6. Build Configuration

### 6.1 Rust Workspace (`crates/Cargo.toml`)

```toml
[workspace]
resolver = "2"
members = [
    "rosplus_core",
    "rosplus_ffi",
    "rosplus_safety",
    "rosplus_bindings",
]

[workspace.package]
version = "0.1.0"
edition = "2021"
authors = ["ROSPlus Contributors"]
license = "Apache-2.0"
repository = "https://github.com/rosplus/rosplus"

[workspace.dependencies]
tokio = { version = "1.0", features = ["full"] }
bytes = "1.5"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
log = "0.4"
tracing = "0.1"
tracing-subscriber = "0.3"
anyhow = "1.0"
thiserror = "1.0"
shared_memory = "0.3"
libc = "0.2"
pyo3 = { version = "0.20", features = ["extension-module"] }
gpio-cdev = "0.6"
nix = { version = "0.27", features = ["sched"] }
prometheus = "0.13"
criterion = { version = "0.5", optional = true }
num_cpus = "1.16"

[profile.release]
lto = true
codegen-units = 1
opt-level = 3
strip = true
```

### 6.2 Go Module (`pkg/go.mod`)

```go
module github.com/rosplus/rosplus

go 1.21

require (
    github.com/spf13/cobra v1.8.0
    github.com/spf13/viper v1.18.2
    github.com/gorilla/websocket v1.5.1
    github.com/gin-gonic/gin v1.9.1
    github.com/stretchr/testify v1.8.4
    github.com/google/uuid v1.5.0
    go.uber.org/zap v1.26.0
    github.com/prometheus/client_golang v1.18.0
)
```

### 6.3 Frontend (`frontend/package.json`)

```json
{
  "name": "rosplus-webide",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@monaco-editor/react": "^4.6.0",
    "reactflow": "^11.10.4",
    "zustand": "^4.4.7",
    "react-router-dom": "^6.20.1",
    "lucide-react": "^0.294.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "tailwindcss": "^3.3.6",
    "typescript": "^5.2.2",
    "vite": "^5.0.8",
    "vitest": "^1.0.4"
  }
}
```

### 6.4 Top-Level Makefile

```makefile
.PHONY: all build frontend test run clean install dev_setup

CARGO := cargo
GO := go
NPM := npm

all: build frontend
	@echo "✅ ROSPlus build complete"

build: rust_build go_build
	@echo "✅ Core binaries built"

rust_build:
	cd crates && $(CARGO) build --release

go_build:
	cd pkg && $(GO) build -o ../bin/turbo ./cli/

frontend:
	cd frontend && $(NPM) install && $(NPM) run build

test: rust_test go_test frontend_test e2e_test
	@echo "✅ All tests passed"

rust_test:
	cd crates && $(CARGO) test --workspace

go_test:
	cd pkg && $(GO) test -v ./...

frontend_test:
	cd frontend && $(NPM) test

e2e_test:
	cd tests/e2e && python -m pytest .

rust_benchmark:
	cd crates && $(CARGO) bench --features benchmark

clean:
	cd crates && $(CARGO) clean
	rm -rf bin/ frontend/dist frontend/node_modules

install: build
	cp ./bin/turbo /usr/local/bin/
	@echo "✅ ROSPlus installed. Run 'turbo' to get started."

run: build
	./bin/turbo run --webide

dev_setup:
	./scripts/setup_dev.sh
```

---

## 7. CI/CD Pipeline

### GitHub Actions CI (`.github/workflows/ci.yml`)

**Jobs:**

1. **rust** — `cargo fmt --check`, `cargo clippy`, `cargo build --release`, `cargo test --workspace`
2. **go** — `go fmt`, `golangci-lint`, `go build`, `go test`
3. **frontend** — `npm ci`, `npm run lint`, `npm run build`, `npm test`
4. **safety** — Build `rosplus_safety` with `--features simulated_gpio`, run integration tests
5. **e2e** — Depends on rust + go + frontend. Runs `make e2e_test`
6. **benchmark** — Runs on `main` only. `cargo bench --features benchmark`. Uploads criterion results as artifacts.
7. **docs** — `cargo doc --workspace --no-deps`. Uploads as artifacts.

### Release Pipeline (`.github/workflows/release.yml`)

Triggered on `v*` tags. Builds all components, creates a tarball, and publishes a GitHub Release with auto-generated release notes.

---

## 8. Technology Decisions & Rationale

| Decision | Chosen | Rejected | Rationale |
|----------|--------|----------|-----------|
| Core runtime language | Rust | Julia, Go, C++ | Zero GC pauses, memory safety without runtime, `#[no_alloc]` for deterministic execution. Zenoh is already Rust. `ros2_rust` client library exists. |
| Tooling language | Go | Rust, Python | Single-binary distribution, excellent stdlib for CLI/HTTP/parsing, fast compilation, easy community contribution. GC pauses irrelevant for CLI tools. |
| Runtime architecture | Dual-Mode (Option C) | Smart Launcher (A), Drop-in Replacement (B) | Preserves 100% legacy compatibility while enabling high-performance native path. Clean separation of concerns. |
| Real-time strategy | Soft-RT default + Hard-RT opt-in | Hard-RT only, Soft-RT only | Soft-RT works on stock Ubuntu (low barrier). Hard-RT available for production robots with PREEMPT_RT. |
| Safety architecture | Separate process + hardware watchdog | In-process safety node | Process isolation ensures safety monitor survives executor crashes. Hardware watchdog ensures fail-safe even if all software fails. |
| Networking (future) | Zenoh | Pure DDS | Zenoh provides centralized discovery (simpler debugging) with distributed resilience. Written in Rust. Hybrid architecture avoids DDS scalability issues. |
| Message pooling | Fixed-chunk slab allocator | Dynamic allocation, ring buffer | Deterministic allocation time, no fragmentation, configurable chunk size per deployment. Spill to heap for oversized messages. |
| Web-IDE frontend | React + ReactFlow + Monaco | Vue, Svelte, custom | ReactFlow handles node graph natively. Monaco is the VS Code editor engine. Large ecosystem for extensions. |
| CLI framework | cobra (Go) | clap (Rust), argparse (Python) | cobra is the Go standard for CLI tools, auto-generates completions, integrates with viper for config. |
| Docker | Recommended, not mandatory | Mandatory | Embedded deployments (Pi, Jetson) can't afford the 5-10% overhead. Native installs via apt/cargo. |
| Julia | Rejected | — | GC pauses break real-time guarantees. 1GB+ RAM for JIT compiler excludes embedded targets. Rust provides the same performance without these drawbacks. |
