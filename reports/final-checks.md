# Follow-up validation

2026-09-14: after the full local suite in local-verification.log:

- Go race tests passed after generated-node shutdown handling changed.
- Frontend TypeScript and production build passed after palette templates changed.
- 15 live responses validated against the active OpenAPI contract.
- Container integration passed colcon build, native-to-Python, Python-to-native and stock-C++-to-native delivery (five observed messages each).
- The container integration also checked that normal stop did not log ExternalShutdownException.
- Browser verified workspace creation, colcon build, live CPU/RSS, and delivery of all ten native messages to the Python listener.
- Temporary preview service was stopped after testing.
- Native ABI v1 integration loaded both the C-header and Rust-API examples from
  workspace-local `.so` files, delivered messages over ROS 2, and observed the
  C plugin shutdown callback after supervised SIGTERM.
- Executor-linked safety remained healthy across built-in, C-plugin, and
  Rust-plugin DDS runs. A deliberately non-returning native callback stopped
  the private progress pipe, latched simulated E-Stop, and recorded the GPIO
  simulator's `E_STOP` event in 66.55 ms (100 ms acceptance threshold).

The frontend build reports a large Monaco-containing bundle. Performance optimization remains useful before distribution.
