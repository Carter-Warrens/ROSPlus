#include "rosplus_native_node.h"

static int state;
static void *create(int argc, const char *const *argv, char *error,
                    size_t error_capacity) {
  (void)argc; (void)argv; (void)error; (void)error_capacity;
  return &state;
}
static int tick(void *opaque, const uint8_t *input, size_t input_length,
                uint8_t *output, size_t output_capacity, size_t *output_length,
                char *error, size_t error_capacity) {
  (void)opaque; (void)input; (void)input_length; (void)output;
  (void)output_capacity; (void)output_length; (void)error;
  (void)error_capacity;
  for (;;) { }
  __builtin_unreachable();
}
static void destroy(void *opaque) { (void)opaque; }

static const rosplus_native_node_v1_descriptor descriptor = {
  .abi_version = ROSPLUS_NATIVE_ABI_VERSION,
  .struct_size = sizeof(descriptor),
  .name = "stalled_native_publisher",
  .name_length = sizeof("stalled_native_publisher") - 1,
  .topic = "/chatter",
  .topic_length = sizeof("/chatter") - 1,
  .direction = ROSPLUS_NATIVE_PUBLISHER,
  .period_us = 10000,
  .create = create,
  .tick = tick,
  .shutdown = 0,
  .destroy = destroy
};
const rosplus_native_node_v1_descriptor *rosplus_native_node_v1(void) {
  return &descriptor;
}
