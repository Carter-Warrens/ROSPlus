#!/usr/bin/env python3
import rospy
from std_msgs.msg import String

rospy.init_node("bag_processor")
publisher = rospy.Publisher("/migration/output", String, queue_size=10)


def callback(message):
    publisher.publish(String(data=message.data.upper() + ":seen"))


subscriber = rospy.Subscriber("/migration/input", String, callback)
rospy.spin()
