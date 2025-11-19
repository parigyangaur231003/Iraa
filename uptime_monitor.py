"""Simple uptime helpers to keep Iraa alive for multi-day sessions."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

try:
    from apscheduler.schedulers.base import STATE_RUNNING
except Exception:  # pragma: no cover - APScheduler optional at runtime
    STATE_RUNNING = 1  # type: ignore


_HERE = Path(__file__).resolve().parent
_DEFAULT_HEARTBEAT_DIR = Path(os.getenv("IRAA_HEARTBEAT_DIR", _HERE / "tmp"))


class Watchdog:
    """Periodic heartbeat writer plus stall detector."""

    def __init__(
        self,
        name: str,
        *,
        timeout: float = 90.0,
        heartbeat_interval: float = 30.0,
        heartbeat_dir: str | os.PathLike[str] | None = None,
        on_stall: Callable[[float], None] | None = None,
    ) -> None:
        self.name = name
        self.timeout = max(10.0, timeout)
        self._interval = max(5.0, heartbeat_interval)
        self._lock = threading.Lock()
        self._last = time.monotonic()
        self._last_alert = 0.0
        self._on_stall = on_stall
        self._stop = threading.Event()

        beat_dir = Path(heartbeat_dir) if heartbeat_dir else _DEFAULT_HEARTBEAT_DIR
        beat_dir.mkdir(parents=True, exist_ok=True)
        self._beat_file = beat_dir / f"{self.name}_heartbeat.json"

        self._writer = threading.Thread(target=self._writer_loop, name=f"{self.name}_hb_writer", daemon=True)
        self._monitor = threading.Thread(target=self._monitor_loop, name=f"{self.name}_hb_monitor", daemon=True)
        self._writer.start()
        self._monitor.start()

    def beat(self) -> None:
        with self._lock:
            self._last = time.monotonic()

    def age(self) -> float:
        with self._lock:
            return time.monotonic() - self._last

    def stop(self) -> None:
        self._stop.set()

    def _writer_loop(self) -> None:
        while not self._stop.wait(self._interval):
            payload = {"name": self.name, "ts": time.time()}
            try:
                with self._beat_file.open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh)
            except Exception as exc:
                print(f"[watchdog:{self.name}] Could not write heartbeat: {exc}")

    def _monitor_loop(self) -> None:
        while not self._stop.wait(self._interval):
            age = self.age()
            now = time.monotonic()
            if age <= self.timeout:
                continue
            if now - self._last_alert < self.timeout * 0.5:
                continue
            self._last_alert = now
            message = f"[watchdog:{self.name}] heartbeat stalled ({age:.1f}s)."
            if self._on_stall:
                try:
                    self._on_stall(age)
                except Exception as exc:
                    print(f"{message} Recovery callback failed: {exc}")
            else:
                print(message)


def start_scheduler_guard(
    get_scheduler: Callable[[], Any],
    restart_callback: Callable[[], Any],
    *,
    check_interval: float = 90.0,
) -> threading.Thread:
    """Start a daemon thread that keeps a BackgroundScheduler running."""

    def _is_running(sched: Any) -> bool:
        if sched is None:
            return False
        state = getattr(sched, "state", None)
        if state is not None:
            return state == STATE_RUNNING
        running = getattr(sched, "running", None)
        if isinstance(running, bool):
            return running
        return True  # Assume active if we cannot introspect state

    def _guard_loop() -> None:
        while True:
            try:
                sched = get_scheduler()
                if not _is_running(sched):
                    print("[scheduler_guard] Scheduler not running. Attempting restart...")
                    restart_callback()
            except Exception as exc:
                print(f"[scheduler_guard] Error while guarding scheduler: {exc}")
            time.sleep(max(15.0, check_interval))

    thread = threading.Thread(target=_guard_loop, name="scheduler_guard", daemon=True)
    thread.start()
    return thread


__all__ = ["Watchdog", "start_scheduler_guard"]
