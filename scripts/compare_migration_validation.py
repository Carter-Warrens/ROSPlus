#!/usr/bin/env python3
"""Compare ROS 1 fixture observations with generated ROS 2 observations."""
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timer_behavior_matches(ros1, ros2):
    def parse(behavior):
        parsed = []
        for message in behavior.get("messages", []):
            prefix, separator, counter = message.rpartition(":")
            if not separator:
                return None
            try:
                parsed.append((prefix, int(counter)))
            except ValueError:
                return None
        if len(parsed) != 5 or any(prefix != "validated" for prefix, _ in parsed):
            return None
        start = parsed[0][1]
        return [counter - start for _, counter in parsed]

    return parse(ros1) == [0, 1, 2, 3, 4] and parse(ros2) == [0, 1, 2, 3, 4]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--generated", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result_dir = Path(args.results)
    scenarios = []
    passed = True
    for name in ["timer_parameter", "subscriber_callback", "trigger_service"]:
        ros1 = json.loads((result_dir / (name + "-ros1.json")).read_text())
        ros2 = json.loads((result_dir / (name + "-ros2.json")).read_text())
        if name == "timer_parameter":
            matches = timer_behavior_matches(ros1["behavior"], ros2["behavior"])
            comparison = "same validated parameter and five consecutive timer counters; startup counters may differ during graph discovery"
        else:
            matches = ros1["behavior"] == ros2["behavior"]
            comparison = "exact behavior equality"
        passed = passed and matches
        scenarios.append({
            "scenario": name,
            "passed": matches,
            "comparison": comparison,
            "ros1_behavior": ros1["behavior"],
            "generated_ros2_behavior": ros2["behavior"],
            "source_sha256": sha256(Path(args.source) / (name + ".py")),
            "generated_sha256": sha256(Path(args.generated) / (name + ".py")),
        })
    report = {
        "passed": passed,
        "scope": "Live behavior comparison for three bounded Python rospy migration fixtures",
        "scenarios": scenarios,
        "limitations": [
            "This does not validate arbitrary Python, C++, custom interfaces, actionlib, tf, or nodelets.",
            "TimerEvent contents, simulated time, timing jitter, and global ROS 1 parameter-server semantics are not equivalent.",
            "The service adapter was exercised only with std_srvs/Trigger and a tuple response.",
            "Recorded-bag and custom-message corpus validation remain open.",
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
