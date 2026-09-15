# ROSPlus Linux implementation decisions

The supplied v1.0 requirements remain the product target. Original design and sprint plan are preserved under `docs/specifications/`. The active API contract is `../openapi.yaml` (v0.2.0).

## Execution boundaries

- The Go service owns workspace persistence, local builds, stock ROS process supervision and WebSocket streams. The CLI talks to it over HTTP and can run remotely from macOS or Windows.
- Rust provides a native SDK foundation: preallocated in-process pool, ownership leases, cooperative priority executor, budget accounting, and actual Linux scheduling calls. A dynamically loaded C adapter connects Rust String publishers/subscribers to stock rcl/RMW. Go supervises built-in endpoints and workspace-local ABI-v1 plugins in separate runtime processes.
- Go-to-Rust supervision uses process/socket boundaries rather than cgo. This keeps the CLI independent of the Linux runtime and isolates watchdog failure. The C adapter exposes the minimal String transport ABI.
- `normal` is an explicit scheduling state in the API. The Go supervisor does not acquire real-time scheduling. Merely detecting a PREEMPT_RT kernel will never establish a hard-real-time guarantee.

## Memory and scheduling limits

The current pool is an **in-process** pool. It does not provide inter-process shared memory, reservations per node, or lock-free operation. `Arc` leases can share payloads without copying. The benchmark measures only ownership handoff and is not an executor, DDS or robotics performance certification.

Native callbacks execute cooperatively. After three completed calls exceeding 110% of budget, the executor disables that node. It cannot preempt a callback that never returns. Process isolation or a separately designed cancellation boundary is needed before promising termination of arbitrary native code. `#[no_alloc]` converts functions to `const fn` under pinned Rust 1.98.1. This conservatively supports pure computation over borrowed buffers and rejects allocating or non-const transitive calls; it does not accept all allocation-free I/O callbacks.

## Watchdog

The Rust watchdog is a separate Linux process with no ROS dependency. It accepts the 16-byte little-endian timestamp/count/flags protocol over a private Unix datagram socket. It rejects stale/replayed timestamps, requires both health flags, checks timeout before accepting a late packet, and latches simulated E-Stop. It begins disarmed until the first valid heartbeat.

Each supervised native runtime writes a monotonic progress counter every 10 ms to a private pipe inherited from Go. The runtime advances it from the DDS/plugin execution loop and during intentional executor waits, but not while a callback is running. Go requires every running native executor to have progress newer than 40 ms and conveys that health bit to the independent monitor every 10 ms. Stale progress, an unexpected native-process exit, monitor failure, or lost monitor replies latch simulated E-Stop, stop supervised process groups, and reject new runs until service restart. Intentional shutdown removes the node from the liveness set before SIGTERM.

The pipe measures runtime-loop progress, not semantic correctness of node output. A non-returning callback stops progress and trips the monitor; Go may still need SIGKILL after its two-second process shutdown grace period. The simulated GPIO response is tested separately from process termination.

GPIO transitions are simulated. The software timer is not a verified 1 kHz physical PWM generator. Tests prove process separation and timeout behavior in this development environment only. Hardware relay, PWM cessation, monitor crash and motor power loss require independent hardware validation.

## Migration

The initial regex implementation changed message contents while reporting success. The revised bounded call parser preserves supported application statements, including publication payloads and subscription callback bodies. Unsupported constructs produce explicit warnings. Every generated migration remains `unvalidated` or `partial`, with a nonzero CLI exit status; generated validation scaffolds fail until replaced by real ROS/bag equivalence tests.

The Go CLI now maps basic parameters, `Duration`, repeating `Timer`, and service servers in addition to publishers, subscribers, rates, spinning, sleeping and logging. Timer callbacks receive `None` instead of ROS 1 `TimerEvent`; one-shot/reset timers remain unsupported. Leading-slash parameter names become node-local dotted ROS 2 names, and the service response adapter has only been exercised with an `std_srvs/Trigger` tuple. Each of these conversions emits a review warning where semantics differ or coverage is narrow.

Live container validation executes original Noetic and generated Jazzy nodes for a parameterized timer, subscriber callback payload transformation, and Trigger service. All three supported behavior invariants pass and the report retains the raw observations and source hashes. This expands the earlier ten-message talker check but does not validate arbitrary migrations. Simulated time, timing jitter and global parameter-server behavior remain open.

The extended compatibility corpus adds native bag recording/replay and a generated custom interface on both distributions. It also compiles and executes paired roscpp/rclcpp processors and runs paired actionlib/action and TF/TF2 nodes. The latter three are manual migration references: ROSPlus preserves and flags ROS 1 C++ sources and flags actionlib/TF dependencies. Passing paired behavior does not imply those APIs are automatically converted. Package metadata generation, custom services/actions, nested types, direct bag-format conversion, nodelets, dynamic reconfigure, simulated time, and production workspace scale remain open.

## Local service scope

The service binds to loopback, requires a bearer token of at least 16 characters, validates request bodies, limits editor requests, rejects symlink paths, and preserves the ROS runtime environment while omitting unrelated secrets. Workspace directories separate files but are **not hostile-code sandboxes**. Native builds and Python nodes are trusted local programs. Multi-user/cloud hosting requires process/container isolation and resource limits before deployment.

Browser WebSockets use same-origin checks and authenticate in the first subscribe frame. Tokens do not appear in URLs or persistent browser storage. Saved graph edges determine ROS topic remaps for managed Python nodes on their next run. Disconnected managed nodes receive isolated topics; multiple distinct endpoint topics are rejected. Changes do not rewire running nodes. Unknown transport metrics use `null`. CPU metrics are lifetime averages from Linux /proc; RSS is sampled for live supervised processes.

## OpenAPI corrections

Version 0.2.0 removes the duplicate `schema` key, adds an SPDX license identifier, workspace listing and bounded restart settings, documents polling and browser WebSocket authentication, and permits `normal` scheduling and unavailable measurements. The supplied target contract and actual response tests are both retained for comparison.
