from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .migration import migrate_tree
from .safety import GpioSimulator, SafetyMonitor
from .server import serve


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="turbo", description="ROSPlus reference control-plane CLI")
    root.add_argument("--version", action="version", version="ROSPlus control plane 0.1.0")
    sub = root.add_subparsers(dest="command", required=True)
    server = sub.add_parser("serve", help="Run the Web-IDE API reference service")
    server.add_argument("--host", default="127.0.0.1"); server.add_argument("--port", type=int, default=8080); server.add_argument("--root", type=Path, default=Path(".rosplus-workspaces")); server.add_argument("--token", default="dev-token")
    migrate = sub.add_parser("migrate", help="Migrate supported ROS 1 Python patterns to ROS 2")
    migrate.add_argument("source", type=Path); migrate.add_argument("--output", type=Path, required=True); migrate.add_argument("--dry-run", action="store_true"); migrate.add_argument("--no-tests", action="store_true")
    safety = sub.add_parser("safety-demo", help="Exercise the simulated dead-man switch")
    safety.add_argument("--timeout-ms", type=int, default=50); safety.add_argument("--heartbeat-ms", type=int, default=10); safety.add_argument("--duration", type=float, default=0.2); safety.add_argument("--log", type=Path, default=Path("safety-gpio.jsonl"))
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "serve":
        serve(args.host, args.port, args.root, args.token); return 0
    if args.command == "migrate":
        result = migrate_tree(args.source, args.output, not args.no_tests, args.dry_run)
        print(json.dumps(result.public(), indent=2)); return 2 if result.status == "partial" else 0
    if args.command == "safety-demo":
        gpio = GpioSimulator(args.log); monitor = SafetyMonitor(args.timeout_ms, gpio); monitor.start()
        end = time.monotonic() + args.duration
        while time.monotonic() < end:
            monitor.heartbeat(); time.sleep(args.heartbeat_ms / 1000)
        print("heartbeats stopped; waiting for fail-safe...")
        deadline = time.monotonic() + args.timeout_ms / 1000 + 0.2
        while not monitor.estop_triggered and time.monotonic() < deadline: time.sleep(0.001)
        print(json.dumps(monitor.status(), indent=2)); monitor.stop(); return 0 if monitor.estop_triggered else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

