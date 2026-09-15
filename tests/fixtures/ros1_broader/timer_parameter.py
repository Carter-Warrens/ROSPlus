#!/usr/bin/env python3
import rospy
from std_msgs.msg import String

rospy.init_node("timer_parameter")
prefix = rospy.get_param("~prefix", "default")
publisher = rospy.Publisher("/migration/timer", String, queue_size=10)
count = 0


def publish_tick(event):
    global count
    publisher.publish(String(data="{}:{}".format(prefix, count)))
    count += 1


timer = rospy.Timer(rospy.Duration(0.05), publish_tick)
rospy.spin()
