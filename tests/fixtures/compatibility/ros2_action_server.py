#!/usr/bin/env python3
import rclpy
from example_interfaces.action import Fibonacci
from rclpy.action import ActionServer
from rclpy.node import Node


class FibonacciServer(Node):
    def __init__(self):
        super().__init__("compat_action_server")
        self.server = ActionServer(self, Fibonacci, "/compat/fibonacci", self.execute)

    def execute(self, goal_handle):
        sequence = [0, 1]
        for _ in range(2, goal_handle.request.order):
            sequence.append(sequence[-1] + sequence[-2])
            goal_handle.publish_feedback(Fibonacci.Feedback(sequence=sequence))
        goal_handle.succeed()
        return Fibonacci.Result(sequence=sequence)


rclpy.init()
node = FibonacciServer()
rclpy.spin(node)
node.destroy_node()
rclpy.shutdown()
