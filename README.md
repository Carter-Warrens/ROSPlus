# ROSPlus

**Faster where it matters. Compatible where it counts. Safe when software fails.**

This repository is an executable control-plane reference slice derived from the
ROSPlus requirements, design, OpenAPI contract, and PoC sprint plan. ROSPlus is
an add-on layer for ROS 2, not a fork.

The native integration plan is mapped directly to the official ROS 2 upstream
repositories in [`docs/UPSTREAM_ROS2.md`](docs/UPSTREAM_ROS2.md).

## What runs in this slice

- API-compatible isolated workspace lifecycle
- Secure file access with path-boundary enforcement
- Python legacy-node supervision and structured log capture
- Python syntax build validation
- Graph, metrics, status, logs, health, and Prometheus endpoints
- Independent heartbeat watchdog with simulated GPIO E-Stop
- ROS 1 Python publisher/subscriber migration for the supported 80/20 path
- Generated migration validation scaffold and migration report
- Lightweight Simple/Expert browser console
- Standard-library test suite

## Native boundaries that remain external

The official ROS 2 source is publicly available upstream. This local build
environment does not currently provide a compiled ROS 2 installation, Rust/Go
toolchains, DDS/Zenoh runtime, PREEMPT_RT, or GPIO hardware. The following are
therefore explicit adapters, not simulated claims:

- Rust native executor and shared-memory zero-copy transport
- `SCHED_FIFO`, CPU affinity, and measured latency guarantees
- DDS interoperability with stock `rclpy` / `rclcpp`
- Hardware watchdog PWM and physical motor relay
- Go CLI / WebSocket production service and React Web-IDE
- ROS 2 package compatibility and benchmark certification

Those capabilities must be compiled and validated in the target ROS 2/Linux
hardware environment before performance or safety claims are published.

## Run

```bash
PYTHONPATH=src python3 -m rosplus.cli serve --root /tmp/rosplus-workspaces
```

Open `http://127.0.0.1:8080`. The development API token is `dev-token`.

Exercise the safety rail:

```bash
PYTHONPATH=src python3 -m rosplus.cli safety-demo --timeout-ms 50
```

Migrate the included ROS 1 talker fixture:

```bash
PYTHONPATH=src python3 -m rosplus.cli migrate \
  tests/fixtures/ros1_workspace --output /tmp/rosplus-migrated
```

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Security posture

The API defaults to loopback only. All workspace endpoints require a bearer
token. File paths are resolved and checked against the workspace root before
read or write. Subprocess environments are allow-listed. The token and
workspace root must be replaced with managed production configuration.

## Project website

The public ROSPlus website lives in [`website/`](website/). It is kept in this
repository so the product narrative, implementation status, and source remain
versioned together under the Carter Warrens GitHub organization.

## Specification issues found during implementation

- The supplied OpenAPI `NotFound` response contains a duplicate `schema:` key.
- The design documents describe WebSocket logs, while this reference service
  intentionally exposes a polling fallback until the Go/WebSocket adapter is
  built.
- The TODO requests a runtime `--simulate` option, while the design says the
  GPIO simulator is a compile-time feature. Production implementation must
  resolve that conflict in favor of a deliberate safety build profile.
