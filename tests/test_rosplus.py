from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from rosplus.migration import migrate_tree
from rosplus.process import ProcessManager
from rosplus.safety import GpioSimulator, SafetyMonitor
from rosplus.workspace import WorkspaceError, WorkspaceManager


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name); self.manager = WorkspaceManager(self.root)
    def tearDown(self): self.temp.cleanup()
    def test_workspace_boundary_and_template(self):
        ws = self.manager.create("robot", "talker_listener")
        self.assertTrue((ws.path / "src/talker.py").exists())
        with self.assertRaises(WorkspaceError): self.manager.read_file(ws.id, "../../etc/passwd")
    def test_duplicate_name_rejected(self):
        self.manager.create("robot")
        with self.assertRaises(WorkspaceError): self.manager.create("robot")
    def test_build_and_legacy_supervision(self):
        ws = self.manager.create("robot", "talker_listener"); proc = ProcessManager(self.manager)
        self.assertTrue(proc.build(ws.id)["success"])
        run = proc.run(ws.id, "src/talker.py")
        self.assertEqual(run["mode"], "legacy")
        deadline = time.monotonic() + 2
        while ws.nodes["talker"].status == "running" and time.monotonic() < deadline: time.sleep(.02)
        self.assertIn(ws.nodes["talker"].status, {"stopped", "error"})


class SafetyTests(unittest.TestCase):
    def test_estop_after_heartbeat_loss(self):
        with tempfile.TemporaryDirectory() as d:
            gpio = GpioSimulator(Path(d) / "gpio.jsonl"); monitor = SafetyMonitor(30, gpio); monitor.start()
            for _ in range(5): monitor.heartbeat(); time.sleep(.005)
            stopped_at = time.monotonic()
            deadline = time.monotonic() + .2
            while not monitor.estop_triggered and time.monotonic() < deadline: time.sleep(.002)
            self.assertTrue(monitor.estop_triggered)
            self.assertLess(time.monotonic() - stopped_at, .1)
            events = [json.loads(x) for x in gpio.log_path.read_text().splitlines()]
            self.assertEqual(events[-1]["reason"], "E_STOP")


class MigrationTests(unittest.TestCase):
    def test_simple_talker_migration(self):
        fixture = Path(__file__).parent / "fixtures/ros1_workspace"
        with tempfile.TemporaryDirectory() as d:
            output = Path(d); result = migrate_tree(fixture, output)
            self.assertEqual(result.status, "success")
            generated = (output / "talker.py").read_text()
            self.assertIn("import rclpy", generated)
            self.assertIn("create_publisher", generated)
            self.assertTrue((output / "migration_result.json").exists())


if __name__ == "__main__": unittest.main()
