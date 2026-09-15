#!/usr/bin/env python3
import rospy
import tf

rospy.init_node("compat_tf_broadcaster")
broadcaster = tf.TransformBroadcaster()
rate = rospy.Rate(20)
while not rospy.is_shutdown():
    broadcaster.sendTransform((1.25, -2.5, 0.75), (0.0, 0.0, 0.0, 1.0), rospy.Time.now(), "tool", "world")
    rate.sleep()
