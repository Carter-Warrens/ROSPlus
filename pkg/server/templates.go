package server

import "strings"

func rosTemplate(name string) map[string]string {
	pkg := "rosplus_" + strings.ToLower(strings.ReplaceAll(name, "-", "_"))
	return map[string]string{
		"src/talker.py": `#!/usr/bin/env python3
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

class Talker(Node):
    def __init__(self):
        super().__init__('talker')
        self.publisher = self.create_publisher(String, '/chatter', 10)
        self.counter = 0
        self.timer = self.create_timer(0.1, self.publish)
    def publish(self):
        msg = String(data=f'hello {self.counter}')
        self.publisher.publish(msg)
        self.get_logger().info(msg.data)
        self.counter += 1

def main():
    rclpy.init()
    node = Talker()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
if __name__ == '__main__':
    main()
`,
		"src/listener.py": `#!/usr/bin/env python3
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

def main():
    rclpy.init()
    node = Node('listener')
    subscription = node.create_subscription(String, '/chatter', lambda msg: node.get_logger().info('received: ' + msg.data), 10)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
if __name__ == '__main__':
    main()
`,
		"rosplus.graph.json": `{"nodes":[{"id":"talker","label":"Talker","type":"publisher","mode":"legacy","managed_topic":true},{"id":"listener","label":"Listener","type":"subscriber","mode":"legacy","managed_topic":true}],"edges":[{"source":"talker","target":"listener","topic":"/chatter","message_type":"std_msgs/msg/String"}]}`,
		"package.xml":        "<?xml version=\"1.0\"?><package format=\"3\"><name>" + pkg + "</name><version>0.1.0</version><description>ROSPlus generated workspace</description><maintainer email=\"developer@example.invalid\">Workspace developer</maintainer><license>Apache-2.0</license><buildtool_depend>ament_cmake</buildtool_depend><exec_depend>rclpy</exec_depend><exec_depend>std_msgs</exec_depend><export><build_type>ament_cmake</build_type></export></package>\n",
		"CMakeLists.txt":     "cmake_minimum_required(VERSION 3.8)\nproject(" + pkg + ")\nfind_package(ament_cmake REQUIRED)\ninstall(DIRECTORY src/ DESTINATION lib/${PROJECT_NAME} FILE_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE FILES_MATCHING PATTERN \"*.py\")\nament_package()\n",
		"README.md":          "# " + name + "\nSource a ROS 2 installation before starting turbo serve. These nodes use real DDS through rclpy.\n",
	}
}
