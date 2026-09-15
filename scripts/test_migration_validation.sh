#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/dev-env.sh

validation_dir="$PWD/build/migration-validation"
generated_dir="$validation_dir/generated"
results_dir="$validation_dir/results"
rm -rf "$validation_dir"
mkdir -p "$results_dir"

cd pkg
go build -o ../build/turbo ./cmd/turbo
cd ..
set +e
./build/turbo migrate tests/fixtures/ros1_broader --output "$generated_dir" >"$validation_dir/migrate.log" 2>&1
migrate_status=$?
set -e
if [[ $migrate_status -ne 1 ]]; then
  echo "expected conservative migrate exit status 1, got $migrate_status" >&2
  cat "$validation_dir/migrate.log" >&2
  exit 1
fi

for scenario in timer_parameter subscriber_callback trigger_service; do
  docker run --rm --init --network host --user "$(id -u):$(id -g)" \
    -v "$PWD:/workspace:ro" -v "$validation_dir:/validation" -w /workspace \
    ros:noetic-ros-core bash -c "source /opt/ros/noetic/setup.bash && python3 scripts/validate_migration_scenario.py --ros 1 --scenario $scenario --node /workspace/tests/fixtures/ros1_broader/$scenario.py --output /validation/results/$scenario-ros1.json"
  docker run --rm --init --network host --user "$(id -u):$(id -g)" \
    -v "$PWD:/workspace:ro" -v "$validation_dir:/validation" -w /workspace \
    rosplus-dev:jazzy bash -c "source /opt/ros/jazzy/setup.bash && python3 scripts/validate_migration_scenario.py --ros 2 --scenario $scenario --node /validation/generated/$scenario.py --output /validation/results/$scenario-ros2.json"
done

python3 scripts/compare_migration_validation.py \
  --results "$results_dir" \
  --source tests/fixtures/ros1_broader \
  --generated "$generated_dir" \
  --output "$validation_dir/migration-validation-broader.json"
cp "$validation_dir/migration-validation-broader.json" reports/migration-validation-broader.json
echo "migration validation passed: reports/migration-validation-broader.json"
