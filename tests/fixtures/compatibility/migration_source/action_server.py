#!/usr/bin/env python3
import actionlib
import rospy
from actionlib_tutorials.msg import FibonacciAction, FibonacciFeedback, FibonacciResult


def execute(goal):
    sequence = [0, 1]
    for _ in range(2, goal.order):
        sequence.append(sequence[-1] + sequence[-2])
        server.publish_feedback(FibonacciFeedback(sequence=sequence))
    server.set_succeeded(FibonacciResult(sequence=sequence))


rospy.init_node("compat_action_server")
server = actionlib.SimpleActionServer("/compat/fibonacci", FibonacciAction, execute_cb=execute, auto_start=False)
server.start()
rospy.spin()
