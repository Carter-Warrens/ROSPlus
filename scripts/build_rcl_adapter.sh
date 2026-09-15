#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rosplus_prefix="${ROSPLUS_ROS_PREFIX:-/opt/ros/${ROS_DISTRO:-jazzy}}"
args=()
for include in "$rosplus_prefix"/include/*; do [[ -d "$include" ]] && args+=("-I$include"); done
mkdir -p build
cc -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Werror -fPIC -shared "${args[@]}" native/rcl_adapter.c -L"$rosplus_prefix/lib" -Wl,-rpath,"$rosplus_prefix/lib" -lrcl -lrcutils -lrosidl_runtime_c -lstd_msgs__rosidl_generator_c -lstd_msgs__rosidl_typesupport_c -o build/librosplus_rcl.so
