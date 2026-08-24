from __future__ import annotations

import json
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__
from .process import ProcessManager
from .safety import GpioSimulator, SafetyMonitor
from .workspace import WorkspaceError, WorkspaceManager


class Application:
    def __init__(self, root: Path, token: str = "dev-token"):
        self.workspaces = WorkspaceManager(root)
        self.processes = ProcessManager(self.workspaces)
        self.token = token
        self.gpio = GpioSimulator(root / "safety-gpio.jsonl")
        self.safety = SafetyMonitor(250, self.gpio)
        self.safety.start()
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while self._heartbeat_running:
            self.safety.heartbeat()
            time.sleep(0.05)

    def close(self) -> None:
        self._heartbeat_running = False
        self._heartbeat_thread.join(timeout=1)
        self.safety.stop()

    def metrics(self) -> str:
        workspaces = list(self.workspaces._items.values())
        running = sum(1 for w in workspaces for n in w.nodes.values() if n.status == "running")
        return "\n".join([
            "# HELP rosplus_workspaces_total Managed workspaces",
            "# TYPE rosplus_workspaces_total gauge",
            f"rosplus_workspaces_total {len(workspaces)}",
            "# HELP rosplus_nodes_running Supervised running nodes",
            "# TYPE rosplus_nodes_running gauge",
            f"rosplus_nodes_running {running}",
            "# HELP rosplus_safety_estop Safety E-Stop state",
            "# TYPE rosplus_safety_estop gauge",
            f"rosplus_safety_estop {1 if self.safety.estop_triggered else 0}",
            "",
        ])


def handler_for(app: Application):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ROSPlus/0.1"

        def do_GET(self): self.dispatch("GET")
        def do_POST(self): self.dispatch("POST")
        def do_PUT(self): self.dispatch("PUT")
        def do_DELETE(self): self.dispatch("DELETE")

        def dispatch(self, method: str):
            parsed = urlparse(self.path); path = parsed.path
            try:
                if path == "/health":
                    return self.send_json(200, {"status": "ok", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": __version__, "executor_connected": False, "safety_monitor_connected": app.safety.running})
                if path == "/metrics": return self.send_text(200, app.metrics())
                if path == "/": return self.send_file(Path(__file__).parents[2] / "web" / "index.html", "text/html; charset=utf-8")
                self.authorize()
                parts = [unquote(x) for x in path.strip("/").split("/")]
                if parts == ["api", "v1", "workspace", "create"] and method == "POST":
                    body = self.body(); ws = app.workspaces.create(body.get("name", ""), body.get("template", "empty")); return self.send_json(201, ws.public())
                if len(parts) >= 4 and parts[:3] == ["api", "v1", "workspace"]:
                    ident = parts[3]; ws = app.workspaces.get(ident); tail = parts[4:]
                    if not tail and method == "GET": return self.send_json(200, ws.public())
                    if not tail and method == "DELETE":
                        app.processes.stop(ident); app.workspaces.delete(ident); return self.send_json(200, {"message": "Workspace deleted", "id": ident})
                    if tail == ["status"]:
                        nodes = [n.public(time.monotonic()) for n in ws.nodes.values()]; return self.send_json(200, {"id": ident, "status": ws.status, "nodes": nodes, "last_activity": ws.last_activity, "executor_mode": "soft_rt"})
                    if tail == ["files"]:
                        relative = parse_qs(parsed.query).get("path", ["."])[0]; return self.send_json(200, {"files": app.workspaces.list_files(ident, relative)})
                    if tail and tail[0] == "file":
                        relative = "/".join(tail[1:])
                        if method == "GET": return self.send_json(200, app.workspaces.read_file(ident, relative))
                        if method == "PUT": return self.send_json(200, app.workspaces.write_file(ident, relative, self.body().get("content", "")))
                    if tail == ["build"] and method == "POST":
                        body = self.body(); return self.send_json(200, app.processes.build(ident, body.get("release", False)))
                    if tail == ["run"] and method == "POST":
                        body = self.body(); return self.send_json(200, app.processes.run(ident, body.get("target", ""), body.get("mode", "auto"), body.get("args", []), body.get("background", True), body.get("priority", "normal")))
                    if tail == ["stop"] and method == "POST":
                        stopped = app.processes.stop(ident, self.body().get("node_name", "")); return self.send_json(200, {"success": True, "stopped": stopped, "message": "Node(s) stopped"})
                    if tail == ["logs"]:
                        return self.send_json(200, {"logs": ws.logs[-200:], "note": "Polling fallback; WebSocket adapter is a native-service boundary"})
                    if tail == ["graph"]:
                        graph = {"nodes": [], "edges": []}; gp = ws.path / "rosplus.graph.json"
                        if gp.exists(): graph = json.loads(gp.read_text())
                        for node in graph.get("nodes", []): node["status"] = "healthy" if ws.nodes.get(node["id"], None) and ws.nodes[node["id"]].status == "running" else "stopped"; node["color"] = "green" if node["status"] == "healthy" else "gray"
                        return self.send_json(200, graph)
                    if tail == ["metrics"]:
                        nodes = list(ws.nodes.values()); safety = app.safety.status(); return self.send_json(200, {"total_nodes": len(nodes), "native_nodes": sum(n.mode == "native" for n in nodes), "legacy_nodes": sum(n.mode == "legacy" for n in nodes), "running_nodes": sum(n.status == "running" for n in nodes), "avg_latency_us": 0, "p99_latency_us": 0, "total_messages": 0, "messages_per_second": 0, "missed_deadlines": 0, "shm_pool": {"total_chunks": 0, "used_chunks": 0, "chunk_size_bytes": 0, "spill_events": 0}, "safety_monitor": safety, "executor_mode": "soft_rt"})
                self.send_json(404, {"error": "Not found", "code": 404})
            except WorkspaceError as exc: self.send_json(404 if "not found" in str(exc) else 400, {"error": str(exc), "code": 400})
            except PermissionError as exc: self.send_json(401, {"error": str(exc), "code": 401})
            except (ValueError, json.JSONDecodeError) as exc: self.send_json(400, {"error": str(exc), "code": 400})

        def authorize(self):
            if self.headers.get("Authorization") != f"Bearer {app.token}": raise PermissionError("authentication required")
        def body(self):
            length = int(self.headers.get("Content-Length", "0")); return json.loads(self.rfile.read(length) or b"{}")
        def send_json(self, status, value): self.send_text(status, json.dumps(value), "application/json")
        def send_text(self, status, value, kind="text/plain; charset=utf-8"):
            data = value.encode(); self.send_response(status); self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        def send_file(self, path, kind):
            if not path.exists(): return self.send_json(404, {"error": "web client not found"})
            self.send_text(200, path.read_text(), kind)
        def log_message(self, fmt, *args): pass
    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080, root: Path | None = None, token: str | None = None):
    app = Application(root or Path(os.environ.get("ROSPLUS_WORKSPACE_ROOT", ".rosplus-workspaces")), token or os.environ.get("ROSPLUS_API_TOKEN", "dev-token"))
    server = ThreadingHTTPServer((host, port), handler_for(app))
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: app.close(); server.server_close()
