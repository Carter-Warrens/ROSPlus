#!/usr/bin/env python3
import rospy
from std_srvs.srv import Trigger

rospy.init_node("trigger_service")
label = rospy.get_param("~label", "ready")


def handle_trigger(request):
    return True, label


service = rospy.Service("/migration/trigger", Trigger, handle_trigger)
rospy.spin()
