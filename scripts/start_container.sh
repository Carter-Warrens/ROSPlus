#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/dev-env.sh
if [[ ! -x build/turbo || ! -x crates/target/debug/rosplus-safety || ! -f frontend/dist/index.html ]]; then make deps build; fi
if [[ ! -x crates/target/release/rosplus-runtime ]]; then cargo build --release --manifest-path crates/Cargo.toml; fi
docker build -t rosplus-dev:jazzy docker
mkdir -p .rosplus-workspaces
export ROSPLUS_API_TOKEN="${ROSPLUS_API_TOKEN:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')}"
printf '\nOpen http://127.0.0.1:8080\nLocal session token: %s\nStop with Ctrl+C.\n\n' "$ROSPLUS_API_TOKEN"
# Host networking keeps the API bound to 127.0.0.1 while allowing local DDS.
# No host device access, Docker socket mount, or privileged mode is used.
exec docker run --rm --init --network host --user "$(id -u):$(id -g)" \
  -e ROSPLUS_API_TOKEN -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-173}" -e ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST -e ROS_LOG_DIR=/tmp/rosplus-logs -e ROS_HOME=/tmp/rosplus-home \
  -v "$PWD:/workspace:ro" -v "$PWD/build:/workspace/build" \
  -v "$PWD/.rosplus-workspaces:/workspace/.rosplus-workspaces" -w /workspace \
  rosplus-dev:jazzy bash -c 'source /opt/ros/jazzy/setup.bash && bash scripts/build_rcl_adapter.sh && exec ./build/turbo serve --root .rosplus-workspaces'
