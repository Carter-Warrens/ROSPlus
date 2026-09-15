# ROSPlus

A Linux development workbench and runtime foundation for the ROSPlus ROS 2 add-on. Version 0.2 adds a Go service/CLI, React editor and independent Rust watchdog to the recovered Python reference implementation.

**Development is in progress.** Native String DDS transport and supervised ROS 2 nodes work in the Linux container. Three bounded Python migration scenarios pass live ROS 1/ROS 2 behavior checks. Hard real-time guarantees, physical motor protection and general migration compatibility remain open. See [development checklist](todo.md) and [design decisions](docs/DESIGN_DECISIONS.md).

## Build and test

Prerequisites: Linux, Rust 1.98.1, Go 1.24+, Node.js 22.12+ and Python 3.10+. Real ROS nodes use ROS 2 Jazzy, either through Docker or a host installation.

```bash
# Optional: use the toolchains installed beside this checkout during development.
source scripts/dev-env.sh
make deps
make test
```

## Start the workbench

The container launcher includes ROS 2 and avoids requiring a host installation:

```bash
bash scripts/start_container.sh
```

It prints the local URL and session token. To use a host ROS installation instead:

```bash
# Required for ROS execution on the host.
source /opt/ros/jazzy/setup.bash
export ROSPLUS_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
./build/turbo serve --root .rosplus-workspaces
```

Open `http://127.0.0.1:8080` and enter that token. Create a workspace, inspect its files in Expert mode, build it, then run the listener and talker separately. The service binds only to loopback and executes trusted local code. It is not a multi-user sandbox.

The default server starts `crates/target/debug/rosplus-safety` as a separate simulated watchdog. Each native runtime reports actual loop progress over a private inherited pipe; stale progress or monitor failure latches E-Stop and stops supervised nodes. Set `--safety-binary` to the installed Rust binary path when packaging. Real GPIO is not implemented.

## CLI

The Go CLI uses `ROSPLUS_URL` (default `http://127.0.0.1:8080`) and `ROSPLUS_API_TOKEN`.

```bash
./build/turbo doctor
./build/turbo create my_robot talker_listener
./build/turbo list
./build/turbo build WORKSPACE_ID
./build/turbo run WORKSPACE_ID src/listener.py
./build/turbo run WORKSPACE_ID src/talker.py
./build/turbo stop WORKSPACE_ID
./build/turbo test --junit-xml build/test-results.xml
```

`run` also accepts `ros2:demo_nodes_cpp:talker` and executable paths inside the workspace. Built-in `native:talker` and `native:listener` targets use Rust String DDS endpoints. Workspace shared libraries use `native:plugin:relative/path.so`; see the [native plugin SDK](docs/NATIVE_PLUGIN_SDK.md).

Migration uses a Go-native bounded Python call parser, preserving application statements. The older Python transformer remains as a reference. Run from the repository root:

```bash
./build/turbo migrate tests/fixtures/ros1_workspace --output /tmp/rosplus-migration
```

It deliberately exits nonzero until behavioral equivalence is validated. Do not interpret generated code or syntax success as proof of equivalence.

With the `ros:noetic-ros-core` and `rosplus-dev:jazzy` images available, run the repeatable migration comparison:

```bash
bash scripts/test_migration_validation.sh
```

It executes original ROS 1 and generated ROS 2 versions of timer/parameter, subscriber-callback, and `std_srvs/Trigger` fixtures. The result is saved in `reports/migration-validation-broader.json`.

The extended compatibility corpus builds matching custom interfaces and C++ nodes, records and replays native ROS 1/ROS 2 bags, and compares manual actionlib-to-action and TF-to-TF2 ports:

```bash
bash scripts/test_migration_compatibility.sh
```

The extended report is saved in `reports/migration-compatibility.json`. C++, actionlib and TF inputs remain explicitly classified as manual migrations; their paired ports demonstrate behavior coverage without claiming automatic conversion.

## Rust experiment

```bash
cargo build --release --manifest-path crates/Cargo.toml
./build/turbo benchmark --messages 1000 --size 1024 --frequency 1000
```

This measures in-process ownership handoff only. It does not measure the promised ROS executor or DDS latency. The SDK is under `crates/rosplus_core`; safety is `crates/rosplus_safety`.

For real DDS integration tests with Docker, run `bash scripts/test_container.sh`. For transport comparison in a sourced ROS environment, run `./build/turbo benchmark --compare --help`. Results and measurement limits are in [implementation status](docs/IMPLEMENTATION_STATUS.md).

## Optional host ROS installation and verification

Run `bash scripts/setup_ros2.sh` in a normal host terminal with sudo. It configures the official ROS apt repository and installs Jazzy base, demo nodes and development packages on Ubuntu 24.04. It does not install a PREEMPT_RT kernel or change device permissions.

```bash
source /opt/ros/jazzy/setup.bash
python3 scripts/check_ros2.py
```

The script tests C++ to Python DDS communication. It fails when dependencies or message delivery are missing.

## API and documentation

- [Active OpenAPI contract](openapi.yaml)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Design decisions and limitations](docs/DESIGN_DECISIONS.md)
- [Original source integration map](docs/UPSTREAM_ROS2.md)
- [Original requirements and plans](docs/specifications/)

Validate the API with `node tooling/validate.mjs`. With a running authenticated service, run `node tooling/contract-test.mjs`. CI runs the local test suites and contract checks; the release workflow produces candidates only and does not publish a release.

The product website remains in `website/`. The new development Web-IDE is `frontend/`.
