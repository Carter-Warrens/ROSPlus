#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/dev-env.sh
make build
cargo build --release --manifest-path crates/Cargo.toml
docker build -t rosplus-dev:jazzy docker
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace:ro" -v "$PWD/build:/workspace/build" -w /workspace \
  -e ROS_LOG_DIR=/tmp/rosplus-logs -e ROSPLUS_DDS_REPORT=/workspace/build/dds-results.json \
  -e ROSPLUS_SUPERVISED_REPORT=/workspace/build/supervised-dds-results.json \
  rosplus-dev:jazzy bash -c 'source /opt/ros/jazzy/setup.bash && bash scripts/build_rcl_adapter.sh && python3 scripts/check_ros2.py && python3 scripts/test_dds.py && python3 scripts/test_supervised_ros.py'
