#ifndef ROSPLUS_NATIVE_NODE_H
#define ROSPLUS_NATIVE_NODE_H
#include <stddef.h>
#include <stdint.h>

#define ROSPLUS_NATIVE_ABI_VERSION 1u
#define ROSPLUS_NATIVE_PUBLISHER 1u
#define ROSPLUS_NATIVE_SUBSCRIBER 2u

typedef void *(*rosplus_create_fn)(int argc, const char *const *argv,
                                   char *error, size_t error_capacity);
typedef int (*rosplus_tick_fn)(void *state, const uint8_t *input,
                               size_t input_length, uint8_t *output,
                               size_t output_capacity, size_t *output_length,
                               char *error, size_t error_capacity);
typedef void (*rosplus_lifecycle_fn)(void *state);

typedef struct rosplus_native_node_v1_descriptor {
  uint32_t abi_version;
  uint32_t struct_size;
  const char *name;
  size_t name_length;
  const char *topic;
  size_t topic_length;
  uint32_t direction;
  uint64_t period_us;
  rosplus_create_fn create;
  rosplus_tick_fn tick;
  rosplus_lifecycle_fn shutdown;
  rosplus_lifecycle_fn destroy;
} rosplus_native_node_v1_descriptor;

/* A plugin exports this symbol. The returned descriptor must remain valid until
 * the library is unloaded. Calls are serialized on one runtime thread. */
const rosplus_native_node_v1_descriptor *rosplus_native_node_v1(void);
#endif
