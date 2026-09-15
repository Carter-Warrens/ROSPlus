# Native plugin SDK — ABI v1

ROSPlus can load workspace-local native nodes with the target
`native:plugin:PATH`, where `PATH` is a `.so` file inside that workspace. Each
plugin runs in its own supervised `rosplus-runtime` process. A crash terminates
that node process without corrupting the Go service.

Plugins include `native/rosplus_native_node.h` and export
`rosplus_native_node_v1`. The descriptor declares a node name, an absolute ROS
topic, publisher or subscriber direction, and a publisher period. ROSPlus calls
`create` once, serializes calls to `tick`, then calls `shutdown` and `destroy`.
The descriptor and its strings must remain valid until library unload.

For a publisher, `tick` writes one UTF-8 `std_msgs/String` payload and returns
`1`; returning `0` skips publication. For a subscriber, ROSPlus supplies the
received UTF-8 bytes as `input`, and `tick` returns `0` after processing them.
Returning a negative value reports the supplied error and stops the node. Output
is bounded to 1 MiB. Plugin arguments follow `--` and are passed to `create`.

Build and run the included example in a sourced ROS 2 environment:

```bash
bash scripts/build_rcl_adapter.sh
bash scripts/build_native_example.sh
cargo build --release --manifest-path crates/Cargo.toml
crates/target/release/rosplus-runtime plugin-run \
  --plugin build/librosplus_example_native.so \
  --adapter build/librosplus_rcl.so --messages 10 --timeout-seconds 15
```

From the workbench, compile the library into the workspace and run
`native:plugin:relative/path/to/plugin.so`. `critical` and `high` priority ask
Linux for FIFO scheduling; the runtime reports whether the request succeeded.
Workbench plugins run continuously until stopped. SIGINT and SIGTERM cause a
clean loop exit followed by the plugin's `shutdown` and `destroy` callbacks.
The declared publisher period is also the callback budget. The runtime records
WCET and deadline misses and disables a plugin after three consecutive calls
that exceed 110% of that budget. It cannot interrupt a callback that never
returns; the Go supervisor will ultimately kill that process on stop timeout.

Rust authors can depend on the dependency-free `rosplus_plugin_api` crate and
export the same symbol. A complete `cdylib` example is in
`crates/examples/native_rust_node`; normal workspace builds produce
`crates/target/release/librosplus_native_rust_example.so` in release mode.

ABI v1 is intentionally limited to `std_msgs/String`. It does not yet expose
services, actions, arbitrary message type support, zero-copy shared memory, or
multiple endpoints per plugin. Shared libraries are trusted native code and may
execute code during `dlopen`; only load plugins you trust. Rust plugins must use
the C ABI and must not unwind across it.
