"""Simulated arms and cameras for `robot serve --fake` and tests."""

import json
import time
from pathlib import Path

import numpy as np

TICK = 0.01


def _wait(seconds: float, events: dict) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if events["exit_early"]:
            events["exit_early"] = False
            return
        time.sleep(TICK)


class FakeDataset:
    """Counts episodes and keeps meta/info.json up to date like a LeRobot dataset."""

    def __init__(self, root: Path):
        self.root = root
        self.info = root / "meta" / "info.json"
        self.info.parent.mkdir(parents=True, exist_ok=True)
        saved = json.loads(self.info.read_text()) if self.info.is_file() else {}
        self.num_episodes = saved.get("total_episodes", 0)
        self.discarded = 0
        self._write()

    def _write(self) -> None:
        self.info.write_text(json.dumps({"total_episodes": self.num_episodes, "fps": 30}))

    def save_episode(self) -> None:
        self.num_episodes += 1
        self._write()

    def clear_episode_buffer(self) -> None:
        self.discarded += 1

    def finalize(self, error: BaseException | None = None) -> None:
        self._write()


class FakePolicy:
    def reset(self) -> None:
        pass


class FakeBackend:
    def __init__(self, cameras: list[str]):
        self.cameras = cameras
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def frame(self, camera: str) -> np.ndarray | None:
        if not self.connected or camera not in self.cameras:
            return None
        # A slowly moving bar so the stream visibly updates.
        img = np.full((480, 640, 3), 40, dtype=np.uint8)
        x = int(time.monotonic() * 120) % 600
        img[:, x : x + 40] = (255, 176, 32) if camera == self.cameras[0] else (80, 200, 255)
        return img

    def teleop(self, seconds: float, events: dict) -> None:
        _wait(seconds, events)

    def record(self, dataset: FakeDataset, seconds: float, events: dict, task: str) -> None:
        _wait(seconds, events)

    def open_dataset(self, root: Path, task: str) -> FakeDataset:
        self.dataset = FakeDataset(root)
        return self.dataset

    def load_policy(self, path: Path) -> FakePolicy:
        if not path.is_dir():
            raise FileNotFoundError(path)
        return FakePolicy()

    def drive(self, policy: FakePolicy, events: dict, task: str) -> None:
        policy.reset()
        _wait(float("inf"), events)
