#!/usr/bin/env python3
"""Capture behavior for custom-interface, C++, action, and TF migration pairs."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


TIMEOUT = 15.0


def launch(path):
    command = [path] if not path.endswith(".py") else ["python3", path]
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)


def child_error(child):
    if child.poll() is not None:
        raise RuntimeError("node exited early: " + child.stderr.read().decode(errors="replace"))


def start_ros1(processes):
    import xmlrpc.client
    master = subprocess.Popen(["roscore"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    processes.append(master)
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        child_error(master)
        try:
            xmlrpc.client.ServerProxy("http://localhost:11311").getPid("/rosplus_compatibility")
            return
        except (OSError, xmlrpc.client.Error):
            time.sleep(0.05)
    raise RuntimeError("timed out waiting for ROS 1 master")


def pubsub_ros1(scenario, child):
    import rospy
    if scenario == "custom_interface":
        from rosplus_validation_msgs.msg import Sample
        message_type = Sample
        input_topic, output_topic = "/compat/custom_input", "/compat/custom_output"
        inputs = [Sample(sequence=7, label="mixed Case", samples=[1.5, -2.0, 0.25])]
        encode = lambda message: {"sequence": message.sequence, "label": message.label, "samples": list(message.samples)}
    else:
        from std_msgs.msg import String
        message_type = String
        input_topic, output_topic = "/compat/cpp_input", "/compat/cpp_output"
        inputs = [String(data="alpha"), String(data="Beta 2")]
        encode = lambda message: message.data
    outputs = []
    subscription = rospy.Subscriber(output_topic, message_type, lambda message: outputs.append(encode(message)))
    publisher = rospy.Publisher(input_topic, message_type, queue_size=10)
    deadline = time.monotonic() + TIMEOUT
    while (publisher.get_num_connections() == 0 or subscription.get_num_connections() == 0) and time.monotonic() < deadline:
        child_error(child)
        time.sleep(0.05)
    if publisher.get_num_connections() == 0 or subscription.get_num_connections() == 0:
        raise RuntimeError("timed out waiting for pub/sub graph")
    for index, message in enumerate(inputs, 1):
        publisher.publish(message)
        deadline = time.monotonic() + TIMEOUT
        while len(outputs) < index and time.monotonic() < deadline:
            child_error(child)
            time.sleep(0.02)
        if len(outputs) < index:
            raise RuntimeError("timed out waiting for output")
    return {"messages": outputs}


def pubsub_ros2(observer, scenario, child):
    import rclpy
    if scenario == "custom_interface":
        from rosplus_validation_msgs.msg import Sample
        message_type = Sample
        input_topic, output_topic = "/compat/custom_input", "/compat/custom_output"
        inputs = [Sample(sequence=7, label="mixed Case", samples=[1.5, -2.0, 0.25])]
        encode = lambda message: {"sequence": message.sequence, "label": message.label, "samples": list(message.samples)}
    else:
        from std_msgs.msg import String
        message_type = String
        input_topic, output_topic = "/compat/cpp_input", "/compat/cpp_output"
        inputs = [String(data="alpha"), String(data="Beta 2")]
        encode = lambda message: message.data
    outputs = []
    subscription = observer.create_subscription(message_type, output_topic, lambda message: outputs.append(encode(message)), 10)
    publisher = observer.create_publisher(message_type, input_topic, 10)
    deadline = time.monotonic() + TIMEOUT
    while publisher.get_subscription_count() == 0 and time.monotonic() < deadline:
        child_error(child)
        rclpy.spin_once(observer, timeout_sec=0.1)
    if publisher.get_subscription_count() == 0:
        raise RuntimeError("timed out waiting for pub/sub discovery")
    for index, message in enumerate(inputs, 1):
        publisher.publish(message)
        deadline = time.monotonic() + TIMEOUT
        while len(outputs) < index and time.monotonic() < deadline:
            child_error(child)
            rclpy.spin_once(observer, timeout_sec=0.1)
        if len(outputs) < index:
            raise RuntimeError("timed out waiting for output")
    return {"messages": outputs}


def action_ros1(child):
    import actionlib
    import rospy
    from actionlib_tutorials.msg import FibonacciAction, FibonacciGoal
    feedback = []
    client = actionlib.SimpleActionClient("/compat/fibonacci", FibonacciAction)
    if not client.wait_for_server(rospy.Duration(TIMEOUT)):
        child_error(child)
        raise RuntimeError("action server unavailable")
    client.send_goal(FibonacciGoal(order=8), feedback_cb=lambda value: feedback.append(list(value.sequence)))
    if not client.wait_for_result(rospy.Duration(TIMEOUT)):
        raise RuntimeError("action result timed out")
    return {"sequence": list(client.get_result().sequence), "feedback_count": len(feedback)}


def action_ros2(observer, child):
    import rclpy
    from example_interfaces.action import Fibonacci
    from rclpy.action import ActionClient
    feedback = []
    client = ActionClient(observer, Fibonacci, "/compat/fibonacci")
    if not client.wait_for_server(timeout_sec=TIMEOUT):
        child_error(child)
        raise RuntimeError("action server unavailable")
    future = client.send_goal_async(Fibonacci.Goal(order=8), feedback_callback=lambda value: feedback.append(list(value.feedback.sequence)))
    rclpy.spin_until_future_complete(observer, future, timeout_sec=TIMEOUT)
    goal = future.result()
    if goal is None or not goal.accepted:
        raise RuntimeError("action goal rejected")
    result_future = goal.get_result_async()
    rclpy.spin_until_future_complete(observer, result_future, timeout_sec=TIMEOUT)
    wrapped = result_future.result()
    if wrapped is None:
        raise RuntimeError("action result timed out")
    return {"sequence": list(wrapped.result.sequence), "feedback_count": len(feedback)}


def tf_ros1(child):
    import rospy
    import tf
    listener = tf.TransformListener()
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        child_error(child)
        try:
            translation, rotation = listener.lookupTransform("world", "tool", rospy.Time(0))
            return {"translation": list(translation), "rotation": list(rotation)}
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
            time.sleep(0.05)
    raise RuntimeError("timed out waiting for transform")


def tf_ros2(observer, child):
    import rclpy
    from tf2_ros import Buffer, TransformListener
    buffer = Buffer()
    listener = TransformListener(buffer, observer)
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        child_error(child)
        rclpy.spin_once(observer, timeout_sec=0.1)
        try:
            value = buffer.lookup_transform("world", "tool", rclpy.time.Time())
            t, q = value.transform.translation, value.transform.rotation
            return {"translation": [t.x, t.y, t.z], "rotation": [q.x, q.y, q.z, q.w]}
        except Exception:
            pass
    raise RuntimeError("timed out waiting for transform")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ros", choices=["1", "2"], required=True)
    parser.add_argument("--scenario", choices=["custom_interface", "cpp", "action", "tf"], required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    processes = []
    with tempfile.TemporaryDirectory() as temp:
        os.environ["ROS_HOME"] = temp
        os.environ["ROS_LOG_DIR"] = temp
        try:
            if args.ros == "1":
                start_ros1(processes)
                import rospy
                rospy.init_node("rosplus_compatibility", disable_signals=True)
                child = launch(args.node)
                processes.append(child)
                if args.scenario in ("custom_interface", "cpp"):
                    behavior = pubsub_ros1(args.scenario, child)
                elif args.scenario == "action":
                    behavior = action_ros1(child)
                else:
                    behavior = tf_ros1(child)
                rospy.signal_shutdown("validation complete")
            else:
                import rclpy
                rclpy.init()
                observer = rclpy.create_node("rosplus_compatibility")
                child = launch(args.node)
                processes.append(child)
                try:
                    if args.scenario in ("custom_interface", "cpp"):
                        behavior = pubsub_ros2(observer, args.scenario, child)
                    elif args.scenario == "action":
                        behavior = action_ros2(observer, child)
                    else:
                        behavior = tf_ros2(observer, child)
                finally:
                    observer.destroy_node()
                    rclpy.shutdown()
            Path(args.output).write_text(json.dumps({"ros": int(args.ros), "scenario": args.scenario, "behavior": behavior}, indent=2) + "\n")
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
