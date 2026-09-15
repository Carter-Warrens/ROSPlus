"""Conservative AST migration; generated code always awaits behavioral validation."""
from __future__ import annotations
import ast
import json
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class MigrationResult:
    files_scanned: int = 0
    files_migrated: int = 0
    files_manual: int = 0
    warnings: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    @property
    def status(self): return 'partial' if self.files_manual else 'unvalidated'
    def public(self): return {**self.__dict__, 'status': self.status, 'validation': 'not_run'}

HELPERS = '''
import rclpy as _rclpy
from rclpy.node import Node as _Node
import time as _time
_rosplus_node = None

def _rosplus_init(name, **kwargs):
    global _rosplus_node
    _rclpy.init()
    _rosplus_node = _Node(name)

def _rosplus_publisher(topic, message_type, queue_size=10):
    return _rosplus_node.create_publisher(message_type, topic, queue_size)

def _rosplus_subscriber(topic, message_type, callback, queue_size=10):
    return _rosplus_node.create_subscription(message_type, topic, callback, queue_size)

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
    _rclpy.spin(_rosplus_node)

def _rosplus_log(level, message, *args):
    getattr(_rosplus_node.get_logger(), level)(str(message) % args if args else str(message))
'''

class Transform(ast.NodeTransformer):
    def __init__(self): self.warnings = []
    def visit_Import(self, node):
        names = [n for n in node.names if n.name != 'rospy']
        if any(n.name == 'rospy' and n.asname for n in node.names): self.warnings.append('aliased rospy import requires review')
        return ast.Import(names=names) if names else None
    def visit_ImportFrom(self, node):
        if node.module == 'rospy': self.warnings.append('from rospy import requires manual migration')
        return node
    def visit_Call(self, node):
        self.generic_visit(node)
        if not isinstance(node.func, ast.Attribute) or not isinstance(node.func.value, ast.Name) or node.func.value.id != 'rospy': return node
        name = node.func.attr
        mapping = {'init_node':'_rosplus_init', 'Publisher':'_rosplus_publisher', 'Subscriber':'_rosplus_subscriber', 'Rate':'_RosPlusRate', 'spin':'_rosplus_spin'}
        if name in mapping:
            if name == 'init_node' and (len(node.args) != 1 or node.keywords): self.warnings.append('non-default init_node options require review')
            if name in {'Publisher','Subscriber'} and any(k.arg != 'queue_size' for k in node.keywords): self.warnings.append('publisher/subscriber options require review')
            node.func = ast.Name(id=mapping[name],ctx=ast.Load()); return node
        if name == 'is_shutdown': return ast.UnaryOp(op=ast.Not(), operand=ast.Call(func=ast.Attribute(value=ast.Name(id='_rclpy',ctx=ast.Load()),attr='ok',ctx=ast.Load()),args=[],keywords=[]))
        if name in {'loginfo','logwarn','logerr','logdebug'}:
            level={'loginfo':'info','logwarn':'warning','logerr':'error','logdebug':'debug'}[name]
            return ast.Call(func=ast.Name(id='_rosplus_log',ctx=ast.Load()),args=[ast.Constant(level)]+node.args,keywords=node.keywords)
        self.warnings.append(f'rospy.{name} requires manual migration'); return node

def migrate_python(source: str, node_name: str):
    tree=ast.parse(source); transform=Transform();tree=transform.visit(tree);ast.fix_missing_locations(tree)
    for n in ast.walk(tree):
        if isinstance(n,ast.Name) and n.id=='rospy': transform.warnings.append('unconverted rospy reference remains')
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            modules=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module or '']
            if any(m.split('.')[0] in {'tf','actionlib','dynamic_reconfigure'} for m in modules): transform.warnings.append('unsupported ROS 1 dependency remains')
    # Keep future imports at the beginning of the module.
    futures=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module=='__future__']
    tree.body=[n for n in tree.body if n not in futures]
    prefix=ast.unparse(ast.Module(body=futures,type_ignores=[]))
    warnings=sorted(set(transform.warnings))
    notes='\n'.join('# TODO: MANUAL MIGRATION REQUIRED: '+w for w in warnings)
    return prefix+'\n'+HELPERS+'\n'+notes+'\n'+ast.unparse(tree)+'\n', warnings

def migrate_tree(source: Path, output: Path, generate_tests=True, dry_run=False):
    source=source.resolve();output=output.resolve()
    if not source.is_dir(): raise ValueError('source directory does not exist')
    if output==source or source in output.parents: raise ValueError('output must be outside source tree')
    if output.exists() and any(output.iterdir()): raise ValueError('output directory must be empty')
    result=MigrationResult()
    for path in sorted(source.rglob('*.py')):
        if path.is_symlink(): result.files_manual+=1;result.warnings.append(f'{path.name}: symlink skipped');continue
        result.files_scanned+=1;text=path.read_text()
        try:
            tree=ast.parse(text)
            imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
            if not any((isinstance(n,ast.Import) and any(a.name=='rospy' for a in n.names)) or (isinstance(n,ast.ImportFrom) and n.module=='rospy') for n in imports):continue
            migrated,warnings=migrate_python(text,path.stem)
        except SyntaxError as e: result.files_manual+=1;result.warnings.append(f'{path.name}: {e}');continue
        relative=path.relative_to(source);target=output/relative;result.outputs.append(str(target));result.warnings.extend(f'{relative}: {w}' for w in warnings)
        if warnings:result.files_manual+=1
        else:result.files_migrated+=1
        if not dry_run:
            target.parent.mkdir(parents=True,exist_ok=True);target.write_text(migrated)
            if generate_tests:
                test=output/'tests'/('test_'+str(relative.with_suffix('')).replace('/','_')+'_migration.py');test.parent.mkdir(parents=True,exist_ok=True)
                test.write_text('import unittest\n\nclass MigrationValidation(unittest.TestCase):\n    def test_behavioral_equivalence(self):\n        self.fail("ROS 1 / ROS 2 bag equivalence validation has not been implemented for this node")\n')
    if not dry_run:output.mkdir(parents=True,exist_ok=True);(output/'migration_result.json').write_text(json.dumps(result.public(),indent=2))
    return result
