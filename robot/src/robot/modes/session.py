"""The session owns the robot and runs one mode at a time on a worker thread.

Modes end on their own (recording stopped from the pedal) or when another mode is chosen;
either way the robot falls back to Play.
"""

import logging
import threading
from collections.abc import Callable

import numpy as np

from robot.hardware import Backend
from robot.modes.play import Play

log = logging.getLogger(__name__)


def new_events() -> dict:
    return {"exit_early": False, "rerecord_episode": False, "stop_recording": False}


class NotConnected(RuntimeError):
    pass


class Session:
    def __init__(self, backend: Backend):
        self.backend = backend
        self.mode = None
        self.error: str | None = None
        self.connected = False
        self._events = new_events()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._closed = False

    def connect(self) -> None:
        with self._lock:
            if self.connected or self._closed:
                return
            try:
                self.backend.connect()
            except Exception as exc:  # noqa: BLE001 - shown on the TV
                log.exception("could not connect")
                self.error = str(exc)
                self.backend.disconnect()
                return
            self.connected, self.error = True, None
            self._start(lambda: Play(self.backend))

    def start(self, make_mode: Callable[[], object]) -> None:
        """Stop the current mode and start a new one."""
        with self._lock:
            if not self.connected:
                raise NotConnected("the robot isn't connected")
            self._start(make_mode)

    def _start(self, make_mode: Callable[[], object]) -> None:
        self._stop_current()
        try:
            mode = make_mode()
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            mode = Play(self.backend)
        events = self._events = new_events()
        self.mode = mode
        self._thread = threading.Thread(
            target=self._run, args=(mode, events), name=mode.name, daemon=True
        )
        self._thread.start()

    def _stop_current(self) -> None:
        if self._thread is None:
            return
        self._events["stop_recording"] = True
        self._events["exit_early"] = True
        self._thread.join()
        self._thread = None

    def _run(self, mode, events: dict) -> None:
        try:
            mode.run(events)
        except Exception as exc:  # noqa: BLE001
            log.exception("%s failed", mode.name)
            self.error = str(exc)
        if not isinstance(mode, Play):
            threading.Thread(target=self._back_to_play, args=(mode,), daemon=True).start()

    def _back_to_play(self, ended) -> None:
        with self._lock:
            # Only if nothing else was started meanwhile.
            if self.mode is ended and not self._closed:
                self._start(lambda: Play(self.backend))

    def press(self, action: str) -> None:
        if self.mode is not None:
            self.mode.press(action)

    def clear_error(self) -> None:
        self.error = None

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            self._stop_current()
            self.backend.disconnect()
            self.connected = False

    def frame(self, camera: str) -> np.ndarray | None:
        return self.backend.frame(camera) if self.connected else None

    def status(self) -> dict:
        mode = self.mode
        return {
            "mode": mode.name if mode else "starting",
            "connected": self.connected,
            "error": self.error,
            **(mode.status() if mode else {}),
        }
