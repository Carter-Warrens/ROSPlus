// Narrow ABI around stock ROS 2 rcl and generated std_msgs type support.
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <std_msgs/msg/string.h>
#include <rosidl_runtime_c/string_functions.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef struct {
  rcl_context_t context;
  rcl_node_t node;
  rcl_publisher_t publisher;
  rcl_subscription_t subscription;
  rcl_wait_set_t waitset;
  int waitset_ready;
  std_msgs__msg__String *message;
  int context_ready, node_ready, endpoint_ready, publish;
  char error[1024];
} rosplus_rcl;

void rosplus_rcl_free(rosplus_rcl *h) {
  if (!h) return;
  rcl_ret_t ret;
  if(h->waitset_ready) { ret=rcl_wait_set_fini(&h->waitset); (void)ret; }
  if (h->endpoint_ready) {
    if (h->publish) ret = rcl_publisher_fini(&h->publisher, &h->node);
    else ret = rcl_subscription_fini(&h->subscription, &h->node);
    (void)ret;
  }
  if (h->message) std_msgs__msg__String__destroy(h->message);
  if (h->node_ready) { ret = rcl_node_fini(&h->node); (void)ret; }
  if (h->context_ready) {
    ret = rcl_shutdown(&h->context); (void)ret;
    ret = rcl_context_fini(&h->context); (void)ret;
  }
  free(h);
}

static void copy_error(char *out, size_t capacity) {
  if (out && capacity) snprintf(out, capacity, "%s", rcl_get_error_string().str);
  rcl_reset_error();
}

rosplus_rcl *rosplus_rcl_new(const char *name, const char *topic, int publish, char *error, size_t capacity) {
  rosplus_rcl *h = calloc(1, sizeof(*h));
  if (!h) { if (error && capacity) snprintf(error,capacity,"allocation failed"); return NULL; }
  h->publish = publish;
  h->context = rcl_get_zero_initialized_context();
  h->node = rcl_get_zero_initialized_node();
  h->publisher = rcl_get_zero_initialized_publisher();
  h->subscription = rcl_get_zero_initialized_subscription();
  h->waitset = rcl_get_zero_initialized_wait_set();
  rcl_init_options_t options = rcl_get_zero_initialized_init_options();
  rcl_allocator_t allocator = rcl_get_default_allocator();
  if (rcl_init_options_init(&options,allocator) != RCL_RET_OK) goto fail;
  rcl_ret_t result = rcl_init(0,NULL,&options,&h->context);
  rcl_ret_t fini_result = rcl_init_options_fini(&options); (void)fini_result;
  if (result != RCL_RET_OK) goto fail;
  h->context_ready = 1;
  rcl_node_options_t node_options = rcl_node_get_default_options();
  if (rcl_node_init(&h->node,name,"",&h->context,&node_options) != RCL_RET_OK) goto fail;
  h->node_ready = 1;
  const rosidl_message_type_support_t *type = ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs,msg,String);
  if (publish) {
    rcl_publisher_options_t p = rcl_publisher_get_default_options();
    if (rcl_publisher_init(&h->publisher,&h->node,type,topic,&p) != RCL_RET_OK) goto fail;
  } else {
    rcl_subscription_options_t p = rcl_subscription_get_default_options();
    if (rcl_subscription_init(&h->subscription,&h->node,type,topic,&p) != RCL_RET_OK) goto fail;
  }
  h->endpoint_ready = 1;
  if(!publish) {
    if(rcl_wait_set_init(&h->waitset,1,0,0,0,0,0,&h->context,allocator)!=RCL_RET_OK) goto fail;
    h->waitset_ready=1;
  }
  h->message = std_msgs__msg__String__create();
  if (!h->message) goto fail;
  return h;
fail:
  copy_error(error,capacity);
  rosplus_rcl_free(h);
  return NULL;
}

int rosplus_rcl_publish(rosplus_rcl *h, const char *text) {
  if (!h || !h->publish) return -1;
  if (!rosidl_runtime_c__String__assign(&h->message->data,text)) return -1;
  if (rcl_publish(&h->publisher,h->message,NULL) != RCL_RET_OK) { copy_error(h->error,sizeof(h->error)); return -1; }
  return 0;
}

// 1 = message, 0 = empty, -1 = error. Caller provides a bounded destination.
int rosplus_rcl_take(rosplus_rcl *h, char *out, size_t capacity) {
  if (!h || h->publish || !out || !capacity) return -1;
  if(rcl_wait_set_clear(&h->waitset)!=RCL_RET_OK || rcl_wait_set_add_subscription(&h->waitset,&h->subscription,NULL)!=RCL_RET_OK) {copy_error(h->error,sizeof(h->error));return -1;}
  rcl_ret_t ready=rcl_wait(&h->waitset,5000000);
  if(ready==RCL_RET_TIMEOUT) return 0;
  if(ready!=RCL_RET_OK) {copy_error(h->error,sizeof(h->error));return -1;}
  rcl_ret_t result = rcl_take(&h->subscription,h->message,NULL,NULL);
  if (result == RCL_RET_SUBSCRIPTION_TAKE_FAILED) return 0;
  if (result != RCL_RET_OK) { copy_error(h->error,sizeof(h->error)); return -1; }
  if (memchr(h->message->data.data,0,h->message->data.size)) { snprintf(h->error,sizeof(h->error),"embedded NUL in ROS String is unsupported"); return -1; }
  if (h->message->data.size >= capacity) { snprintf(h->error,sizeof(h->error),"message exceeds receive buffer"); return -1; }
  memcpy(out,h->message->data.data,h->message->data.size);
  out[h->message->data.size] = 0;
  return 1;
}
const char *rosplus_rcl_error(rosplus_rcl *h) { return h ? h->error : "invalid handle"; }
