#!/usr/bin/env python3
"""Exercise one migration fixture and write its externally observed behavior."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


TIMEOUT = 15.0


def wait_until(predicate, description, child=None):
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if predicate():
            return
        if child is not None and child.poll() is not None:
            raise RuntimeError("node exited early: " + child.stderr.read().decode(errors="replace"))
        time.sleep(0.02)
    raise RuntimeError("timed out waiting for " + description)


def launch_node(ros, path, parameter):
    command = ["python3", path]
    if parameter:
        name, value = parameter
        if ros == "1":
            command.append("_{}:={}".format(name, value))
        else:
            command.extend(["--ros-args", "-p", "{}:={}".format(name, value)])
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def validate_ros1(scenario, node_path, processes):
    import xmlrpc.client

    master = subprocess.Popen(
        ["roscore"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    processes.append(master)

    def master_ready():
        try:
            xmlrpc.client.ServerProxy("http://localhost:11311").getPid("/rosplus_validation")
            return True
        except (OSError, xmlrpc.client.Error):
            return False

    wait_until(master_ready, "ROS 1 master", master)
    import rospy
    from std_msgs.msg import String

    rospy.init_node("rosplus_migration_validation", disable_signals=True)
    if scenario == "timer_parameter":
        values = []
        subscription = rospy.Subscriber("/migration/timer", String, lambda message: values.append(message.data))
        child = launch_node("1", node_path, ("prefix", "validated"))
        processes.append(child)
        wait_until(lambda: len(values) >= 5, "five timer messages", child)
        return {"messages": values[:5]}
    if scenario == "subscriber_callback":
        values = []
        subscription = rospy.Subscriber("/migration/output", String, lambda message: values.append(message.data))
        publisher = rospy.Publisher("/migration/input", String, queue_size=10)
        child = launch_node("1", node_path, None)
        processes.append(child)
        wait_until(
            lambda: publisher.get_num_connections() > 0 and subscription.get_num_connections() > 0,
            "subscriber and publisher connections",
            child,
        )
        for value in ["alpha", "Beta 2", "gamma"]:
            publisher.publish(String(data=value))
            wait_until(lambda: len(values) >= ["alpha", "Beta 2", "gamma"].index(value) + 1,
                       "callback output", child)
        return {"messages": values[:3]}
    if scenario == "trigger_service":
        from std_srvs.srv import Trigger
        child = launch_node("1", node_path, ("label", "validated"))
        processes.append(child)
        rospy.wait_for_service("/migration/trigger", timeout=TIMEOUT)
        response = rospy.ServiceProxy("/migration/trigger", Trigger)()
        return {"success": response.success, "message": response.message}
    raise ValueError(scenario)


def validate_ros2(scenario, node_path, processes):
    import rclpy
    from std_msgs.msg import String

    rclpy.init()
    observer = rclpy.create_node("rosplus_migration_validation")
    try:
        if scenario == "timer_parameter":
            values = []
            subscription = observer.create_subscription(
                String, "/migration/timer", lambda message: values.append(message.data), 10
            )
            child = launch_node("2", node_path, ("prefix", "validated"))
            processes.append(child)
            deadline = time.monotonic() + TIMEOUT
            while len(values) < 5 and time.monotonic() < deadline:
                rclpy.spin_once(observer, timeout_sec=0.1)
                if child.poll() is not None:
                    raise RuntimeError("node exited early: " + child.stderr.read().decode(errors="replace"))
            if len(values) < 5:
                raise RuntimeError("timed out waiting for five timer messages")
            return {"messages": values[:5]}
        if scenario == "subscriber_callback":
            values = []
            subscription = observer.create_subscription(
                String, "/migration/output", lambda message: values.append(message.data), 10
            )
            publisher = observer.create_publisher(String, "/migration/input", 10)
            child = launch_node("2", node_path, None)
            processes.append(child)
            deadline = time.monotonic() + TIMEOUT
            while publisher.get_subscription_count() == 0 and time.monotonic() < deadline:
                rclpy.spin_once(observer, timeout_sec=0.1)
                if child.poll() is not None:
                    raise RuntimeError("node exited early: " + child.stderr.read().decode(errors="replace"))
            if publisher.get_subscription_count() == 0:
                raise RuntimeError("timed out waiting for subscriber discovery")
            for index, value in enumerate(["alpha", "Beta 2", "gamma"], 1):
                publisher.publish(String(data=value))
                deadline = time.monotonic() + TIMEOUT
                while len(values) < index and time.monotonic() < deadline:
                    rclpy.spin_once(observer, timeout_sec=0.1)
                    if child.poll() is not None:
                        raise RuntimeError("node exited early: " + child.stderr.read().decode(errors="replace"))
                if len(values) < index:
                    raise RuntimeError("timed out waiting for callback output")
            return {"messages": values[:3]}
        if scenario == "trigger_service":
            from std_srvs.srv import Trigger
            child = launch_node("2", node_path, ("label", "validated"))
            processes.append(child)
            client = observer.create_client(Trigger, "/migration/trigger")
            if not client.wait_for_service(timeout_sec=TIMEOUT):
                raise RuntimeError("timed out waiting for Trigger service")
            future = client.call_async(Trigger.Request())
            rclpy.spin_until_future_complete(observer, future, timeout_sec=TIMEOUT)
            response = future.result()
            if response is None:
                raise RuntimeError("Trigger request did not complete")
            return {"success": response.success, "message": response.message}
        raise ValueError(scenario)
    finally:
        observer.destroy_node()
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ros", choices=["1", "2"], required=True)
    parser.add_argument("--scenario", choices=["timer_parameter", "subscriber_callback", "trigger_service"], required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    processes = []
    with tempfile.TemporaryDirectory() as temp:
        os.environ["ROS_HOME"] = temp
        os.environ["ROS_LOG_DIR"] = temp
        try:
            if args.ros == "1":
                behavior = validate_ros1(args.scenario, args.node, processes)
                import rospy
                rospy.signal_shutdown("validation complete")
            else:
                behavior = validate_ros2(args.scenario, args.node, processes)
            Path(args.output).write_text(json.dumps({
                "ros": int(args.ros), "scenario": args.scenario, "behavior": behavior
            }, indent=2) + "\n")
        finally:
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for process in reversed(processes):
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                if process.stderr:
                    process.stderr.close()


if __name__ == "__main__":
    main()
