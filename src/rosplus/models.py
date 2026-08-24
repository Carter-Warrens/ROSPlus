from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NodeRecord:
    name: str
    target: str
    mode: str
    status: str = "starting"
    pid: int | None = None
    started_monotonic: float = 0.0
    restart_count: int = 0

    def public(self, now: float) -> dict[str, Any]:
        uptime = max(0.0, now - self.started_monotonic) if self.started_monotonic else 0.0
        return {
            "name": self.name,
            "status": self.status,
            "mode": self.mode,
            "pid": self.pid,
            "uptime_seconds": round(uptime, 3),
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "restart_count": self.restart_count,
        }


@dataclass
class Workspace:
    id: str
    name: str
    path: Path
    template: str = "empty"
    status: str = "idle"
    created: str = field(default_factory=utc_now)
    last_activity: str = field(default_factory=utc_now)
    nodes: dict[str, NodeRecord] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    build_lock: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": str(self.path),
            "status": self.status,
            "created": self.created,
            "last_activity": self.last_activity,
            "node_count": len(self.nodes),
        }

    def log(self, severity: str, message: str, node: str = "control-plane") -> None:
        self.last_activity = utc_now()
        self.logs.append({
            "type": "log",
            "workspace_id": self.id,
            "timestamp": self.last_activity,
            "severity": severity.lower(),
            "node": node,
            "message": message,
        })
        if len(self.logs) > 1000:
            del self.logs[:250]

