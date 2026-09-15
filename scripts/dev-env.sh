# Source this file. Prefer workspace-local toolchains when present.
ROSPLUS_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROSPLUS_TOOLS="${ROSPLUS_TOOLCHAIN_DIR:-$ROSPLUS_REPO/../toolchains}"
if [ ! -d "$ROSPLUS_TOOLS/cargo" ]; then
 ROSPLUS_TOOLS="$ROSPLUS_REPO/../../work/toolchains"
fi
if [ -d "$ROSPLUS_TOOLS/cargo" ]; then
 export CARGO_HOME="$ROSPLUS_TOOLS/cargo" RUSTUP_HOME="$ROSPLUS_TOOLS/rustup"
 export PATH="$CARGO_HOME/bin:$ROSPLUS_TOOLS/go/bin:$PATH"
fi
ROSPLUS_CACHE_BASE="$ROSPLUS_REPO/.cache"
if [ -d "$ROSPLUS_TOOLS" ]; then ROSPLUS_CACHE_BASE="$(dirname "$ROSPLUS_TOOLS")"; fi
export GOPATH="${ROSPLUS_GO_CACHE:-$ROSPLUS_CACHE_BASE/go-cache}"
export GOCACHE="$GOPATH/build"
export npm_config_cache="${ROSPLUS_NPM_CACHE:-$ROSPLUS_CACHE_BASE/npm-cache}"
