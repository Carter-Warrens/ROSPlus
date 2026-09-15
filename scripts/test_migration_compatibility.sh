#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/dev-env.sh

validation_dir="$PWD/build/migration-compatibility"
results_dir="$validation_dir/results"
generated_dir="$validation_dir/generated"
rm -rf "$validation_dir"
mkdir -p "$results_dir"
cp -a tests/fixtures/compatibility/ros1_ws "$validation_dir/ros1_ws"
cp -a tests/fixtures/compatibility/ros2_ws "$validation_dir/ros2_ws"
cp -a tests/fixtures/compatibility/migration_source "$validation_dir/migration_source"
cp -a tests/fixtures/compatibility/ros2_cpp "$validation_dir/ros2_cpp"

docker build -f docker/Dockerfile.migration-noetic -t rosplus-migration:noetic docker >/dev/null
docker build -t rosplus-dev:jazzy docker >/dev/null

cd pkg
go build -o ../build/turbo ./cmd/turbo
cd ..
set +e
./build/turbo migrate tests/fixtures/compatibility/migration_source --output "$generated_dir" >"$validation_dir/migrate.log" 2>&1
migrate_status=$?
set -e
if [[ $migrate_status -ne 1 ]]; then
  echo "expected conservative migrate exit status 1, got $migrate_status" >&2
  cat "$validation_dir/migrate.log" >&2
  exit 1
fi

docker run --rm --user "$(id -u):$(id -g)" \
  -v "$validation_dir:/validation" -w /validation/ros1_ws \
  rosplus-migration:noetic bash -lc 'source /opt/ros/noetic/setup.bash && catkin_make -DCMAKE_BUILD_TYPE=Release'
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$validation_dir:/validation" -w /validation/ros2_ws \
  rosplus-dev:jazzy bash -lc 'source /opt/ros/jazzy/setup.bash && colcon build --merge-install --cmake-args -DCMAKE_BUILD_TYPE=Release'

run_ros1() {
  local scenario="$1" node="$2"
  docker run --rm --init --network host --user "$(id -u):$(id -g)" \
    -v "$PWD:/workspace:ro" -v "$validation_dir:/validation" -w /workspace \
    rosplus-migration:noetic bash -lc "source /opt/ros/noetic/setup.bash && source /validation/ros1_ws/devel/setup.bash && python3 scripts/validate_migration_compatibility.py --ros 1 --scenario $scenario --node $node --output /validation/results/$scenario-ros1.json"
}

run_ros2() {
  local scenario="$1" node="$2"
  docker run --rm --init --network host --user "$(id -u):$(id -g)" \
    -v "$PWD:/workspace:ro" -v "$validation_dir:/validation" -w /workspace \
    rosplus-dev:jazzy bash -lc "source /opt/ros/jazzy/setup.bash && source /validation/ros2_ws/install/setup.bash && python3 scripts/validate_migration_compatibility.py --ros 2 --scenario $scenario --node $node --output /validation/results/$scenario-ros2.json"
}

docker run --rm --init --network host --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace:ro" -v "$validation_dir:/validation" -w /workspace \
  rosplus-migration:noetic bash -lc 'source /opt/ros/noetic/setup.bash && python3 scripts/validate_recorded_bag.py --ros 1 --node /validation/migration_source/bag_processor.py --output /validation/results/recorded_bag-ros1.json'
docker run --rm --init --network host --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace:ro" -v "$validation_dir:/validation" -w /workspace \
  rosplus-dev:jazzy bash -lc 'source /opt/ros/jazzy/setup.bash && python3 scripts/validate_recorded_bag.py --ros 2 --node /validation/generated/bag_processor.py --output /validation/results/recorded_bag-ros2.json'

run_ros1 custom_interface /validation/migration_source/custom_processor.py
run_ros2 custom_interface /validation/generated/custom_processor.py
run_ros1 cpp /validation/ros1_ws/devel/lib/rosplus_cpp_validation/cpp_processor
run_ros2 cpp /validation/ros2_ws/install/lib/rosplus_cpp_validation/cpp_processor
run_ros1 action /validation/migration_source/action_server.py
run_ros2 action /workspace/tests/fixtures/compatibility/ros2_action_server.py
run_ros1 tf /validation/migration_source/tf_broadcaster.py
run_ros2 tf /workspace/tests/fixtures/compatibility/ros2_tf_broadcaster.py

python3 scripts/compare_migration_compatibility.py \
  --results "$results_dir" \
  --migration-result "$generated_dir/migration_result.json" \
  --output "$validation_dir/migration-compatibility.json"
cp "$validation_dir/migration-compatibility.json" reports/migration-compatibility.json
echo "migration compatibility passed: reports/migration-compatibility.json"
