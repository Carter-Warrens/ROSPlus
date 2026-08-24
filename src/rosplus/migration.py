from __future__ import annotations

import ast
import json
import re
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
    def status(self) -> str:
        return "partial" if self.files_manual else "success"

    def public(self) -> dict:
        return {**self.__dict__, "status": self.status}


UNSUPPORTED = {"actionlib": "ROS 1 actionlib requires manual ROS 2 action migration", "dynamic_reconfigure": "dynamic_reconfigure requires parameter callback design", "nodelet": "nodelets require ROS 2 component design"}


def migrate_tree(source: Path, output: Path, generate_tests: bool = True, dry_run: bool = False) -> MigrationResult:
    result = MigrationResult()
    source = source.resolve(); output = output.resolve()
    for path in source.rglob("*.py"):
        result.files_scanned += 1
        text = path.read_text()
        try:
            ast.parse(text)
        except SyntaxError as exc:
            result.files_manual += 1; result.warnings.append(f"{path.name}: syntax error: {exc}"); continue
        if "rospy" not in text:
            continue
        migrated, warnings = migrate_python(text, path.stem)
        relative = path.relative_to(source)
        target = output / relative
        result.outputs.append(str(target))
        result.warnings.extend(f"{path.name}: {w}" for w in warnings)
        if warnings: result.files_manual += 1
        else: result.files_migrated += 1
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(migrated)
            if generate_tests:
                test = output / "tests" / f"test_{path.stem}_migration.py"
                test.parent.mkdir(parents=True, exist_ok=True)
                test.write_text(validation_test(relative))
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)
        (output / "migration_result.json").write_text(json.dumps(result.public(), indent=2))
    return result


def migrate_python(source: str, node_name: str) -> tuple[str, list[str]]:
    warnings = [message for token, message in UNSUPPORTED.items() if token in source]
    imports = sorted(set(re.findall(r"from\s+([\w.]+\.msg)\s+import\s+([\w, ]+)", source)))
    msg_imports = "\n".join(f"from {module} import {names}" for module, names in imports)
    pub = re.search(r"rospy\.Publisher\(\s*['\"]([^'\"]+)['\"]\s*,\s*([\w.]+)", source)
    sub = re.search(r"rospy\.Subscriber\(\s*['\"]([^'\"]+)['\"]\s*,\s*([\w.]+)\s*,\s*(\w+)", source)
    rate = re.search(r"rospy\.Rate\((\d+(?:\.\d+)?)\)", source)
    hz = float(rate.group(1)) if rate else 10.0
    lines = ["import rclpy", "from rclpy.node import Node"]
    if msg_imports: lines.append(msg_imports)
    lines += ["", "", f"class {camel(node_name)}Node(Node):", "    def __init__(self):", f"        super().__init__('{node_name}')"]
    if pub:
        topic, msg = pub.group(1), pub.group(2).split(".")[-1]
        lines += [f"        self.publisher = self.create_publisher({msg}, '{topic}', 10)", f"        self.timer = self.create_timer({1/hz:.6f}, self.publish_once)", "        self.counter = 0", "", "    def publish_once(self):", f"        msg = {msg}()", "        if hasattr(msg, 'data'):", "            msg.data = f'rosplus migrated {self.counter}'", "        self.publisher.publish(msg)", "        self.counter += 1"]
    if sub:
        topic, msg, callback = sub.group(1), sub.group(2).split(".")[-1], sub.group(3)
        lines += [f"        self.subscription = self.create_subscription({msg}, '{topic}', self.{callback}, 10)", "", f"    def {callback}(self, msg):", "        self.get_logger().info(str(msg))"]
    if not pub and not sub:
        warnings.append("no supported publisher/subscriber pattern found")
        lines += ["        # TODO: MANUAL MIGRATION REQUIRED — no supported ROS 1 pub/sub pattern found"]
    for warning in warnings:
        lines += [f"        # TODO: MANUAL MIGRATION REQUIRED — {warning}"]
    lines += ["", "", "def main(args=None):", "    rclpy.init(args=args)", f"    node = {camel(node_name)}Node()", "    try:", "        rclpy.spin(node)", "    finally:", "        node.destroy_node()", "        rclpy.shutdown()", "", "", "if __name__ == '__main__':", "    main()", ""]
    return "\n".join(lines), warnings


def camel(value: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[_-]+", value))


def validation_test(relative: Path) -> str:
    return f'''"""Generated migration validation scaffold.

Run original and migrated nodes against the same recorded bag before marking
the migration complete. This file deliberately does not claim equivalence.
"""
from pathlib import Path

def test_migrated_file_exists():
    assert (Path(__file__).parents[1] / {str(relative)!r}).exists()
'''

