"""Foot pedal input. Most USB pedals are keyboards; each pedal sends one key."""

import logging
import threading
import time
from collections.abc import Callable

from robot.config import Pedal

log = logging.getLogger(__name__)


def key_actions(pedal: Pedal) -> dict[str, str]:
    """Key name (e.g. "KEY_RIGHT") → action ("next", "redo", "stop")."""
    return {pedal.next: "next", pedal.redo: "redo", pedal.stop: "stop"}


def find() -> list[str]:
    import evdev

    return sorted({evdev.InputDevice(path).name for path in evdev.list_devices()})


def listen(pedal: Pedal, on_action: Callable[[str], None]) -> threading.Thread | None:
    """Read the pedal on a daemon thread. It's grabbed so its keys don't reach the console."""
    if not pedal.device:
        return None
    import evdev

    actions = key_actions(pedal)

    def read(device) -> None:
        device.grab()
        for event in device.read_loop():
            if event.type != evdev.ecodes.EV_KEY or event.value != 1:  # key down only
                continue
            names = evdev.ecodes.KEY.get(event.code, [])
            for name in names if isinstance(names, list) else [names]:
                if name in actions:
                    on_action(actions[name])

    def run() -> None:
        # Keep looking for the pedal so it can be unplugged and plugged back in.
        warned = False
        while True:
            match = None
            for path in evdev.list_devices():
                try:
                    device = evdev.InputDevice(path)
                except OSError:
                    continue
                if device.name == pedal.device and match is None:
                    match = device
                else:
                    device.close()
            if match is None:
                if not warned:
                    log.warning("foot pedal %r not found", pedal.device)
                    warned = True
            else:
                warned = False
                try:
                    read(match)
                except OSError:
                    log.warning("foot pedal disconnected")
                finally:
                    match.close()
            time.sleep(2)

    thread = threading.Thread(target=run, name="pedal", daemon=True)
    thread.start()
    return thread
