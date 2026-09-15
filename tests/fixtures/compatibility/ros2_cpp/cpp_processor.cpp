#include <memory>
#include <string>

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

class Processor : public rclcpp::Node {
public:
  Processor() : Node("cpp_processor") {
    output_ = create_publisher<std_msgs::msg::String>("/compat/cpp_output", 10);
    input_ = create_subscription<std_msgs::msg::String>(
        "/compat/cpp_input", 10, [this](std_msgs::msg::String::ConstSharedPtr input) {
          std_msgs::msg::String output;
          output.data = "cpp:" + input->data;
          output_->publish(output);
        });
  }

private:
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr output_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr input_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Processor>());
  rclcpp::shutdown();
  return 0;
}
