"""Find cameras by USB port and apply v4l2 controls."""

import logging
import subprocess
from pathlib import Path

from robot.config import Camera

log = logging.getLogger(__name__)
BY_PATH = Path("/dev/v4l/by-path")


def find() -> list[Path]:
    """Capture nodes, one per camera. Identical camera models are told apart by port."""
    if not BY_PATH.is_dir():
        return []
    return sorted(p for p in BY_PATH.iterdir() if p.name.endswith("video-index0"))


def apply_controls(camera: Camera) -> None:
    if not camera.controls:
        return
    settings = ",".join(f"{name}={value}" for name, value in camera.controls.items())
    result = subprocess.run(
        ["v4l2-ctl", "-d", camera.path, "-c", settings], capture_output=True, text=True
    )
    if result.returncode != 0:
        log.warning("could not set %s on %s: %s", settings, camera.path, result.stderr.strip())
