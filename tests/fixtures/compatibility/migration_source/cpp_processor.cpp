#include <ros/ros.h>
#include <std_msgs/String.h>

ros::Publisher output;

void process(const std_msgs::String::ConstPtr &input) {
  std_msgs::String message;
  message.data = "cpp:" + input->data;
  output.publish(message);
}

int main(int argc, char **argv) {
  ros::init(argc, argv, "cpp_processor");
  ros::NodeHandle node;
  output = node.advertise<std_msgs::String>("/compat/cpp_output", 10);
  auto input = node.subscribe("/compat/cpp_input", 10, process);
  ros::spin();
  return 0;
}
