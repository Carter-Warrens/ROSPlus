#!/usr/bin/env python3
"""Replay canonical String inputs through a node and inspect recorded outputs."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


INPUTS = ["alpha", "Beta 2", "gamma"]
EXPECTED = ["ALPHA:seen", "BETA 2:seen", "GAMMA:seen"]
TIMEOUT = 20


def process(command, stderr=subprocess.PIPE):
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=stderr, start_new_session=True)


def terminate(item, interrupt=False):
    if item.poll() is None:
        os.killpg(item.pid, signal.SIGINT if interrupt else signal.SIGTERM)
    try:
        item.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(item.pid, signal.SIGKILL)
        item.wait()


def wait_master(master):
    import xmlrpc.client
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if master.poll() is not None:
            raise RuntimeError("roscore exited")
        try:
            xmlrpc.client.ServerProxy("http://localhost:11311").getPid("/bag_validation")
            return
        except (OSError, xmlrpc.client.Error):
            time.sleep(0.05)
    raise RuntimeError("ROS 1 master timeout")


def ros1(node_path, directory, processes):
    import rosbag
    import rospy
    from std_msgs.msg import String
    master = process(["roscore"], stderr=subprocess.DEVNULL)
    processes.append(master)
    wait_master(master)
    rospy.init_node("bag_validation", disable_signals=True)
    input_path = str(directory / "input.bag")
    output_base = str(directory / "output")
    output_path = output_base + ".bag"
    with rosbag.Bag(input_path, "w") as bag:
        for index, value in enumerate(INPUTS):
            bag.write("/migration/input", String(data=value), rospy.Time.from_sec(1.0 + index * 0.1))
    node = process(["python3", node_path])
    recorder = process(["rosbag", "record", "-O", output_base, "/migration/output"])
    processes.extend([node, recorder])
    time.sleep(1.5)
    player = process(["rosbag", "play", "--delay=1", input_path])
    processes.append(player)
    if player.wait(timeout=TIMEOUT) != 0:
        raise RuntimeError("ROS 1 bag play failed")
    time.sleep(0.5)
    terminate(recorder, interrupt=True)
    outputs = []
    with rosbag.Bag(output_path, "r") as bag:
        for _, message, _ in bag.read_messages(topics=["/migration/output"]):
            outputs.append(message.data)
    rospy.signal_shutdown("validation complete")
    return {"input_messages": INPUTS, "recorded_output_messages": outputs, "expected": EXPECTED, "passed": outputs == EXPECTED}


def ros2(node_path, directory, processes):
    import rosbag2_py
    import rclpy
    from rclpy.serialization import deserialize_message, serialize_message
    from std_msgs.msg import String
    input_path = str(directory / "input")
    output_path = str(directory / "output")
    writer = rosbag2_py.SequentialWriter()
    writer.open(rosbag2_py.StorageOptions(uri=input_path, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    writer.create_topic(rosbag2_py.TopicMetadata(id=0, name="/migration/input", type="std_msgs/msg/String", serialization_format="cdr"))
    for index, value in enumerate(INPUTS):
        writer.write("/migration/input", serialize_message(String(data=value)), 1_000_000_000 + index * 100_000_000)
    del writer
    rclpy.init()
    node = process(["python3", node_path])
    recorder = process(["ros2", "bag", "record", "--storage", "sqlite3", "-o", output_path, "/migration/output"])
    processes.extend([node, recorder])
    time.sleep(2.0)
    player = process(["ros2", "bag", "play", input_path, "--delay", "1"])
    processes.append(player)
    if player.wait(timeout=TIMEOUT) != 0:
        raise RuntimeError("ROS 2 bag play failed")
    time.sleep(0.5)
    terminate(recorder, interrupt=True)
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=output_path, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
    outputs = []
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic == "/migration/output":
            outputs.append(deserialize_message(data, String).data)
    rclpy.shutdown()
    return {"input_messages": INPUTS, "recorded_output_messages": outputs, "expected": EXPECTED, "passed": outputs == EXPECTED}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ros", choices=["1", "2"], required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    processes = []
    with tempfile.TemporaryDirectory() as temp:
        os.environ["ROS_HOME"] = temp
        os.environ["ROS_LOG_DIR"] = temp
        try:
            behavior = ros1(args.node, Path(temp), processes) if args.ros == "1" else ros2(args.node, Path(temp), processes)
            Path(args.output).write_text(json.dumps({"ros": int(args.ros), "scenario": "recorded_bag", "behavior": behavior}, indent=2) + "\n")
            if not behavior["passed"]:
                raise SystemExit(1)
        finally:
            for item in processes:
                terminate(item)
            for item in processes:
                if item.stderr:
                    item.stderr.close()


if __name__ == "__main__":
    main()
