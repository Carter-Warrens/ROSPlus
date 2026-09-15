#include "rosplus_native_node.h"
#include <stdio.h>
#include <stdlib.h>

typedef struct { unsigned count; } state;

static void *create(int argc, const char *const *argv, char *error,
                    size_t error_capacity) {
  (void)argc; (void)argv; (void)error; (void)error_capacity;
  return calloc(1, sizeof(state));
}
static int tick(void *opaque, const uint8_t *input, size_t input_length,
                uint8_t *output, size_t capacity, size_t *length, char *error,
                size_t error_capacity) {
  (void)input; (void)input_length;
  state *value = opaque;
  int written = snprintf((char *)output, capacity, "ROSPlus plugin %u", value->count++);
  if (written < 0 || (size_t)written >= capacity) {
    snprintf(error, error_capacity, "output buffer too small");
    return -1;
  }
  *length = (size_t)written;
  return 1;
}
static void shutdown_node(void *opaque) {
  (void)opaque;
  fputs("{\"event\":\"plugin_shutdown\"}\n", stdout);
  fflush(stdout);
}
static void destroy(void *opaque) { free(opaque); }

static const rosplus_native_node_v1_descriptor descriptor = {
  .abi_version = ROSPLUS_NATIVE_ABI_VERSION,
  .struct_size = sizeof(descriptor),
  .name = "example_native_publisher",
  .name_length = sizeof("example_native_publisher") - 1,
  .topic = "/chatter",
  .topic_length = sizeof("/chatter") - 1,
  .direction = ROSPLUS_NATIVE_PUBLISHER,
  .period_us = 100000,
  .create = create,
  .tick = tick,
  .shutdown = shutdown_node,
  .destroy = destroy
};
const rosplus_native_node_v1_descriptor *rosplus_native_node_v1(void) {
  return &descriptor;
}
