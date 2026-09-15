#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/dev-env.sh
if [[ -f /opt/ros/jazzy/setup.bash ]]; then
 set +u
 source /opt/ros/jazzy/setup.bash
 set -u
fi
if [[ ! -x build/turbo || ! -x crates/target/debug/rosplus-safety || ! -f frontend/dist/index.html ]]; then
 make deps build
fi
export ROSPLUS_API_TOKEN="${ROSPLUS_API_TOKEN:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')}"
printf '\nOpen http://127.0.0.1:8080\nUse this local session token: %s\n\n' "$ROSPLUS_API_TOKEN"
exec ./build/turbo serve --root .rosplus-workspaces "$@"
