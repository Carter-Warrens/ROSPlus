from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable


class GpioSimulator:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = "LOW"
        self._write("INIT")

    def set(self, state: str, reason: str) -> None:
        if state != self.state or reason == "E_STOP":
            self.state = state
            self._write(reason)

    def _write(self, reason: str) -> None:
        with self.log_path.open("a") as handle:
            handle.write(json.dumps({"timestamp_ns": time.time_ns(), "state": self.state, "reason": reason}) + "\n")


class SafetyMonitor:
    """Independent heartbeat watchdog with a simulated hardware boundary."""

    def __init__(self, timeout_ms: int, gpio: GpioSimulator, on_estop: Callable[[], None] | None = None):
        if timeout_ms < 5:
            raise ValueError("timeout_ms must be >= 5")
        self.timeout = timeout_ms / 1000
        self.gpio = gpio
        self.on_estop = on_estop
        self.last_heartbeat = 0.0
        self.estop_triggered = False
        self.running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.running = True
        self.last_heartbeat = time.monotonic()
        self.gpio.set("HIGH", "ARMED")
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()

    def heartbeat(self) -> None:
        if not self.running or self.estop_triggered:
            return
        self.last_heartbeat = time.monotonic()

    def _watch(self) -> None:
        while self.running and not self.estop_triggered:
            if time.monotonic() - self.last_heartbeat > self.timeout:
                self.gpio.set("LOW", "E_STOP")
                # Publish the observable fail-safe action before exposing the
                # triggered flag. Callers that see True can then rely on the
                # GPIO transition and its audit record already being complete.
                self.estop_triggered = True
                if self.on_estop:
                    self.on_estop()
                break
            time.sleep(min(self.timeout / 10, 0.005))

    def stop(self) -> None:
        self.running = False
        self.gpio.set("LOW", "DISARMED")
        if self._thread:
            self._thread.join(timeout=1)

    def status(self) -> dict:
        age = (time.monotonic() - self.last_heartbeat) * 1_000_000 if self.last_heartbeat else 0
        return {"connected": self.running, "estop_triggered": self.estop_triggered, "heartbeat_latency_us": round(age, 1)}
