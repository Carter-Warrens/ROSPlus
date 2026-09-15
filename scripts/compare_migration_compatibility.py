#!/usr/bin/env python3
"""Create the consolidated migration compatibility report."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--migration-result", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result_dir = Path(args.results)
    migration = json.loads(Path(args.migration_result).read_text())
    scenarios = []
    passed = True
    for name in ["recorded_bag", "custom_interface", "cpp", "action", "tf"]:
        ros1 = json.loads((result_dir / (name + "-ros1.json")).read_text())
        ros2 = json.loads((result_dir / (name + "-ros2.json")).read_text())
        if name == "action":
            matches = (
                ros1["behavior"].get("sequence") == ros2["behavior"].get("sequence")
                and ros1["behavior"].get("feedback_count", 0) > 0
                and ros2["behavior"].get("feedback_count", 0) > 0
            )
            comparison = "exact durable result sequence and feedback observed on both transports"
        else:
            matches = ros1["behavior"] == ros2["behavior"]
            comparison = "exact behavior equality"
        passed = passed and matches
        scenarios.append({
            "scenario": name,
            "passed": matches,
            "comparison": comparison,
            "ros1_behavior": ros1["behavior"],
            "ros2_behavior": ros2["behavior"],
            "migration_mode": "automatic" if name in ("recorded_bag", "custom_interface") else "manual paired port",
        })
    warnings = migration.get("warnings", [])
    classification = {
        "cpp_manual": any("C++ source requires manual" in warning for warning in warnings),
        "actionlib_manual": any("actionlib" in warning for warning in warnings),
        "tf_manual": any("unsupported ROS 1 dependency" in warning and "tf_broadcaster.py" in warning for warning in warnings),
        "migration_status_partial": migration.get("status") == "partial",
    }
    passed = passed and all(classification.values())
    report = {
        "passed": passed,
        "scope": "Recorded bags, custom interfaces, C++, actionlib/actions, TF, and migration classification",
        "scenarios": scenarios,
        "classification_checks": classification,
        "migration_result": migration,
        "limitations": [
            "C++, actionlib, and TF were behavior-tested as explicit manual ROS 2 ports; the converter correctly classifies their ROS 1 sources as manual.",
            "Custom-interface automatic conversion covers one message with scalar, string, and variable-length array fields.",
            "Bag validation uses equivalent native ROS 1 and ROS 2 bag formats with the same canonical String dataset.",
            "Custom services/actions, nested interface packages, rosbag format conversion, nodelets, dynamic_reconfigure, simulated time, and large production workspaces remain outside this corpus.",
            "Physical GPIO, relay, PWM, motor-power cutoff, and target-hardware timing require connected hardware and are not exercised here.",
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
