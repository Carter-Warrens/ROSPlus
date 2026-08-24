from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from pathlib import Path

from .models import Workspace, utc_now

NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

TEMPLATES = {
    "empty": {"README.md": "# ROSPlus workspace\n"},
    "talker_listener": {
        "src/talker.py": "import time\nfor i in range(5):\n    print(f'chatter: {i}', flush=True)\n    time.sleep(0.1)\n",
        "src/listener.py": "print('listener ready', flush=True)\n",
        "rosplus.graph.json": json.dumps({
            "nodes": [
                {"id": "talker", "label": "Talker", "type": "publisher", "mode": "legacy"},
                {"id": "listener", "label": "Listener", "type": "subscriber", "mode": "legacy"},
            ],
            "edges": [{"source": "talker", "target": "listener", "topic": "/chatter", "message_type": "std_msgs/String"}],
        }, indent=2),
    },
    "camera": {"README.md": "# Camera workspace\n\nHardware adapter pending device discovery.\n"},
}


class WorkspaceError(Exception):
    pass


class WorkspaceManager:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, Workspace] = {}
        self._lock = threading.RLock()

    def create(self, name: str, template: str = "empty") -> Workspace:
        if not NAME.fullmatch(name):
            raise WorkspaceError("name must match ^[A-Za-z0-9_-]{1,64}$")
        if template not in TEMPLATES:
            raise WorkspaceError(f"unknown template: {template}")
        with self._lock:
            if any(w.name == name for w in self._items.values()):
                raise WorkspaceError("workspace name already exists")
            ident = str(uuid.uuid4())
            path = self.root / ident
            path.mkdir(mode=0o700)
            for relative, content in TEMPLATES[template].items():
                target = path / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            ws = Workspace(id=ident, name=name, path=path, template=template)
            ws.log("info", f"workspace created from {template} template")
            self._items[ident] = ws
            return ws

    def get(self, ident: str) -> Workspace:
        try:
            return self._items[ident]
        except KeyError as exc:
            raise WorkspaceError("workspace not found") from exc

    def delete(self, ident: str) -> Workspace:
        with self._lock:
            ws = self.get(ident)
            if any(n.status == "running" for n in ws.nodes.values()):
                raise WorkspaceError("stop running nodes before deletion")
            shutil.rmtree(ws.path)
            del self._items[ident]
            return ws

    def safe_path(self, ws: Workspace, relative: str) -> Path:
        relative = relative or "."
        candidate = (ws.path / relative).resolve()
        if candidate != ws.path and ws.path not in candidate.parents:
            raise WorkspaceError("path escapes workspace boundary")
        return candidate

    def list_files(self, ident: str, relative: str = ".") -> list[dict]:
        ws = self.get(ident)
        base = self.safe_path(ws, relative)
        if not base.exists() or not base.is_dir():
            raise WorkspaceError("directory not found")
        result = []
        for item in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            stat = item.stat()
            result.append({
                "name": item.name,
                "path": str(item.relative_to(ws.path)),
                "is_directory": item.is_dir(),
                "size_bytes": stat.st_size,
                "last_modified": utc_now(),
            })
        return result

    def read_file(self, ident: str, relative: str) -> dict:
        ws = self.get(ident)
        path = self.safe_path(ws, relative)
        if not path.is_file():
            raise WorkspaceError("file not found")
        return {"path": relative, "content": path.read_text(), "language": language(path), "size_bytes": path.stat().st_size, "last_modified": utc_now()}

    def write_file(self, ident: str, relative: str, content: str) -> dict:
        ws = self.get(ident)
        path = self.safe_path(ws, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        ws.log("info", f"saved {relative}")
        return {"path": relative, "size_bytes": path.stat().st_size, "last_modified": utc_now()}


def language(path: Path) -> str:
    return {".py": "python", ".rs": "rust", ".cpp": "cpp", ".cc": "cpp", ".yaml": "yaml", ".yml": "yaml", ".xml": "xml", ".json": "json", ".toml": "toml", ".md": "markdown"}.get(path.suffix.lower(), "text")

