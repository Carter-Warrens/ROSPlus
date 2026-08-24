# Official ROS 2 upstream integration map

ROSPlus is an add-on layer, not a ROS 2 fork. Its native and legacy paths must
integrate with the official [`ros2`](https://github.com/ros2) organization and
track a declared ROS 2 distribution rather than copying upstream internals.

## Primary upstream repositories

| ROSPlus concern | Official upstream | Integration role |
|---|---|---|
| Distribution manifest | [`ros2/ros2`](https://github.com/ros2/ros2) | Pin the supported ROS 2 distribution and source set |
| C client boundary | [`ros2/rcl`](https://github.com/ros2/rcl) | Preferred native integration boundary below language-specific executors |
| C++ legacy nodes | [`ros2/rclcpp`](https://github.com/ros2/rclcpp) | Run unmodified under stock ROS 2 supervision |
| Python legacy nodes | [`ros2/rclpy`](https://github.com/ros2/rclpy) | Run unmodified under stock ROS 2 supervision |
| Interface generation | [`ros2/rosidl`](https://github.com/ros2/rosidl) | Generate and consume canonical ROS message/service/action types |
| ROS 1 interoperability | [`ros2/ros1_bridge`](https://github.com/ros2/ros1_bridge) | Validate migration and mixed-system behavior |
| Compatibility fixtures | [`ros2/examples`](https://github.com/ros2/examples) | Canonical publisher/subscriber/service fixtures |
| Integration demos | [`ros2/demos`](https://github.com/ros2/demos) | End-to-end Legacy Mode and transport tests |
| Common C utilities | [`ros2/rcutils`](https://github.com/ros2/rcutils) | Logging, allocator, error, and portability conventions |

## Integration principles

1. **Pin a distribution.** Development may follow Rolling, but compatibility
   claims must name a released ROS 2 distribution and platform from REP-2000.
2. **Stay below the stock executors in Native Mode.** The Rust executor should
   integrate through `rcl`/RMW-facing contracts rather than wrapping `rclcpp`
   and inheriting its executor behavior.
3. **Do not patch upstream installs.** Legacy nodes launch from the user's stock
   ROS 2 environment with their original `rclpy` or `rclcpp` behavior.
4. **Generate, do not reinterpret, interfaces.** Use `rosidl` outputs and
   canonical type support at the Native/Legacy boundary.
5. **Use official fixtures first.** Compatibility gates begin with official
   examples and demos before expanding to the top-package corpus.
6. **Separate source availability from verified execution.** The public source
   is available, but latency, DDS interoperability, and safety claims require a
   compiled ROS 2 installation and target Linux hardware.

## Initial compatibility gate

The first upstream-backed test matrix should include:

- `examples_rclcpp_minimal_publisher` + `examples_rclcpp_minimal_subscriber`
- `examples_rclpy_minimal_publisher` + `examples_rclpy_minimal_subscriber`
- Native Rust publisher to stock C++ and Python subscribers
- Stock C++ and Python publishers to a Native Rust subscriber
- Service request/response across both execution modes
- Type-support coverage for primitives, bounded strings, arrays, and one custom
  interface package
- Shutdown, crash, and restart behavior under the ROSPlus supervisor

Passing this matrix proves basic add-on compatibility. It does not by itself
prove the broader 80% package-compatibility target.

