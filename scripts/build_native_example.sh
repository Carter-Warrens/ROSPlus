#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
cc -std=c11 -Wall -Wextra -Werror -fPIC -shared -Inative \
  native/example_native_publisher.c -o build/librosplus_example_native.so
