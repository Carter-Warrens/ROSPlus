package migration

const runtimeHelpers = `
import rclpy as _rclpy
from rclpy.node import Node as _Node
from rclpy.parameter import Parameter as _Parameter
from rclpy.executors import ExternalShutdownException as _ExternalShutdownException
import time as _time
_rosplus_node = None
_ROSPLUS_MISSING = object()

def _rosplus_init(name, **kwargs):
    global _rosplus_node
    _rclpy.init()
    _rosplus_node = _Node(name, allow_undeclared_parameters=True,
                          automatically_declare_parameters_from_overrides=True)

def _rosplus_publisher(topic, message_type, queue_size=10):
    return _rosplus_node.create_publisher(message_type, topic, queue_size)

def _rosplus_subscriber(topic, message_type, callback, queue_size=10):
    return _rosplus_node.create_subscription(message_type, topic, callback, queue_size)

def _rosplus_parameter_name(name):
    if name.startswith('~'):
        return name[1:]
    if name.startswith('/'):
        return name[1:].replace('/', '.')
    return name

def _rosplus_get_param(name, default=_ROSPLUS_MISSING):
    name = _rosplus_parameter_name(name)
    if not _rosplus_node.has_parameter(name):
        if default is _ROSPLUS_MISSING:
            raise KeyError(name)
        _rosplus_node.declare_parameter(name, default)
    return _rosplus_node.get_parameter(name).value

def _rosplus_has_param(name):
    return _rosplus_node.has_parameter(_rosplus_parameter_name(name))

def _rosplus_set_param(name, value):
    name = _rosplus_parameter_name(name)
    if not _rosplus_node.has_parameter(name):
        _rosplus_node.declare_parameter(name, value)
    else:
        _rosplus_node.set_parameters([_Parameter(name=name, value=value)])

def _RosPlusDuration(seconds=0, nsecs=0):
    return float(seconds) + float(nsecs) / 1000000000.0

def _rosplus_timer(period, callback, oneshot=False, reset=False):
    if oneshot or reset:
        raise NotImplementedError('oneshot/reset ROS 1 timers require manual migration')
    return _rosplus_node.create_timer(float(period), lambda: callback(None))

def _rosplus_service(name, service_type, callback):
    def invoke(request, response):
        result = callback(request)
        fields = list(response.get_fields_and_field_types())
        if isinstance(result, dict):
            for field, value in result.items():
                if field in fields:
                    setattr(response, field, value)
        elif isinstance(result, (tuple, list)):
            for field, value in zip(fields, result):
                setattr(response, field, value)
        elif result is not None:
            for field in fields:
                if hasattr(result, field):
                    setattr(response, field, getattr(result, field))
        return response
    return _rosplus_node.create_service(service_type, name, invoke)

def _rosplus_sleep(duration):
    deadline = _time.monotonic() + float(duration)
    while _rclpy.ok() and _time.monotonic() < deadline:
        _rclpy.spin_once(_rosplus_node,
                         timeout_sec=min(0.05, deadline - _time.monotonic()))

class _RosPlusRate:
    def __init__(self, hz):
        if hz <= 0:
            raise ValueError('rate must be positive')
        self.period = 1.0 / hz
        self.next = _time.monotonic() + self.period
    def sleep(self):
        while _rclpy.ok():
            remaining = self.next - _time.monotonic()
            if remaining <= 0:
                break
            _rclpy.spin_once(_rosplus_node, timeout_sec=remaining)
        self.next += self.period

def _rosplus_spin():
    try:
        _rclpy.spin(_rosplus_node)
    except _ExternalShutdownException:
        pass

def _rosplus_log(level, message, *args):
    getattr(_rosplus_node.get_logger(), level)(str(message) % args if args else str(message))
`
