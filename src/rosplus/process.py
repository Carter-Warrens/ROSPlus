from __future__ import annotations

import os
import py_compile
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .models import NodeRecord
from .workspace import WorkspaceError, WorkspaceManager


class ProcessManager:
    def __init__(self, workspaces: WorkspaceManager):
        self.workspaces = workspaces
        self.processes: dict[tuple[str, str], subprocess.Popen[str]] = {}
        self._lock = threading.RLock()

    def build(self, ident: str, release: bool = False) -> dict:
        ws = self.workspaces.get(ident)
        if ws.build_lock:
            raise WorkspaceError("build already in progress")
        ws.build_lock = True
        ws.status = "building"
        start = time.monotonic()
        errors: list[str] = []
        warnings: list[str] = []
        built = 0
        try:
            for path in ws.path.rglob("*.py"):
                try:
                    py_compile.compile(str(path), doraise=True)
                    built += 1
                except py_compile.PyCompileError as exc:
                    errors.append(str(exc))
            rust = list(ws.path.rglob("*.rs"))
            if rust:
                warnings.append("Rust sources detected; native compilation requires the ROSPlus Rust toolchain adapter")
            success = not errors
            ws.status = "idle" if success else "error"
            ws.log("info" if success else "error", f"build {'passed' if success else 'failed'}: {built} Python file(s) validated")
            return {"success": success, "log": "\n".join(errors + warnings) or "validation complete", "errors": errors, "warnings": warnings, "duration_seconds": round(time.monotonic() - start, 4), "packages_built": built}
        finally:
            ws.build_lock = False

    def run(self, ident: str, target: str, mode: str = "auto", args: list[str] | None = None, background: bool = True, priority: str = "normal") -> dict:
        ws = self.workspaces.get(ident)
        path = self.workspaces.safe_path(ws, target)
        if not path.is_file():
            raise WorkspaceError("target not found")
        detected = "native" if path.suffix == ".rs" else "legacy"
        mode = detected if mode == "auto" else mode
        if mode == "native":
            raise WorkspaceError("native Rust execution requires the ROSPlus executor adapter and ROS 2 runtime")
        if path.suffix != ".py":
            raise WorkspaceError("reference supervisor currently executes Python legacy nodes only")
        name = path.stem
        key = (ident, name)
        with self._lock:
            existing = self.processes.get(key)
            if existing and existing.poll() is None:
                raise WorkspaceError("node is already running")
            env = {k: v for k, v in os.environ.items() if k in {"PATH", "PYTHONPATH", "ROS_DOMAIN_ID", "RMW_IMPLEMENTATION", "HOME", "LANG"}}
            proc = subprocess.Popen([sys.executable, "-u", str(path), *(args or [])], cwd=ws.path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            record = NodeRecord(name=name, target=target, mode=mode, status="running", pid=proc.pid, started_monotonic=time.monotonic())
            ws.nodes[name] = record
            ws.status = "running"
            self.processes[key] = proc
            ws.log("info", f"started {name} pid={proc.pid} mode={mode}", name)
            threading.Thread(target=self._capture, args=(ident, name, proc), daemon=True).start()
        return {"success": True, "node_name": name, "pid": proc.pid, "mode": mode, "log_url": f"/api/v1/workspace/{ident}/logs"}

    def _capture(self, ident: str, name: str, proc: subprocess.Popen[str]) -> None:
        ws = self.workspaces.get(ident)
        assert proc.stdout
        for line in proc.stdout:
            ws.log("info", line.rstrip(), name)
        proc.stdout.close()
        code = proc.wait()
        if name in ws.nodes:
            ws.nodes[name].status = "stopped" if code == 0 else "error"
        if not any(n.status == "running" for n in ws.nodes.values()):
            ws.status = "idle" if code == 0 else "error"
        ws.log("info" if code == 0 else "error", f"process exited with code {code}", name)

    def stop(self, ident: str, node_name: str = "") -> list[str]:
        ws = self.workspaces.get(ident)
        names = [node_name] if node_name else list(ws.nodes)
        stopped = []
        for name in names:
            proc = self.processes.get((ident, name))
            if not proc or proc.poll() is not None:
                continue
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=1)
            ws.nodes[name].status = "stopped"
            stopped.append(name)
            ws.log("info", "node stopped", name)
        if not any(n.status == "running" for n in ws.nodes.values()):
            ws.status = "idle"
        return stopped
