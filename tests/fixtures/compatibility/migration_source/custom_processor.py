#!/usr/bin/env python3
import rospy
from rosplus_validation_msgs.msg import Sample

rospy.init_node("custom_processor")
publisher = rospy.Publisher("/compat/custom_output", Sample, queue_size=10)


def process(message):
    publisher.publish(Sample(
        sequence=message.sequence + 1,
        label=message.label.upper(),
        samples=[value * 2.0 for value in message.samples],
    ))


subscriber = rospy.Subscriber("/compat/custom_input", Sample, process)
rospy.spin()
