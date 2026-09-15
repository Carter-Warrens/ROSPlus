#!/usr/bin/env python3
import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


class Broadcaster(Node):
    def __init__(self):
        super().__init__("compat_tf_broadcaster")
        self.broadcaster = TransformBroadcaster(self)
        self.timer = self.create_timer(0.05, self.publish_transform)

    def publish_transform(self):
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = "world"
        transform.child_frame_id = "tool"
        transform.transform.translation.x = 1.25
        transform.transform.translation.y = -2.5
        transform.transform.translation.z = 0.75
        transform.transform.rotation.w = 1.0
        self.broadcaster.sendTransform(transform)


rclpy.init()
node = Broadcaster()
rclpy.spin(node)
node.destroy_node()
rclpy.shutdown()
