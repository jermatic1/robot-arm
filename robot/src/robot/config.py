"""Robot settings loaded from config.toml (see config.example.toml)."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Arm:
    port: str
    id: str


@dataclass(frozen=True)
class Camera:
    path: str
    width: int = 640
    height: int = 480
    fps: int = 30
    # Compressed video, so two cameras fit on one USB hub. "" lets OpenCV choose.
    fourcc: str = "MJPG"
    # How long to wait for the first frames when connecting; some cameras are slow to start.
    warmup_seconds: int = 3
    # v4l2-ctl controls applied at startup, e.g. {"focus_automatic_continuous": 0}
    controls: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Record:
    target_episodes: int = 50
    countdown_seconds: float = 3
    episode_seconds: float = 20
    reset_seconds: float = 10
    fps: int = 30
    vcodec: str = "h264"


@dataclass(frozen=True)
class Pedal:
    device: str = ""  # device name as listed by `robot find-pedal`; empty disables the pedal
    next: str = "KEY_RIGHT"
    redo: str = "KEY_LEFT"
    stop: str = "KEY_ESC"


@dataclass(frozen=True)
class Trainer:
    host: str = ""  # ssh destination, e.g. "me@trainer.local"; empty disables training
    inbox: str = "~/robot-trainer/inbox"
    outputs: str = "~/robot-trainer/outputs"


@dataclass(frozen=True)
class Config:
    follower: Arm
    leader: Arm
    cameras: dict[str, Camera]
    data: Path
    record: Record = Record()
    pedal: Pedal = Pedal()
    trainer: Trainer = Trainer()
    warn_below_gb: float = 10
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def datasets(self) -> Path:
        return self.data / "datasets"

    @property
    def policies(self) -> Path:
        return self.data / "policies"


def load(path: Path) -> Config:
    raw = tomllib.loads(path.read_text())
    return Config(
        follower=Arm(**raw["follower"]),
        leader=Arm(**raw["leader"]),
        cameras={name: Camera(**cam) for name, cam in raw.get("cameras", {}).items()},
        data=Path(raw.get("data", "~/robot-data")).expanduser(),
        record=Record(**raw.get("record", {})),
        pedal=Pedal(**raw.get("pedal", {})),
        trainer=Trainer(**raw.get("trainer", {})),
        warn_below_gb=float(raw.get("warn_below_gb", 10)),
        host=raw.get("host", "0.0.0.0"),
        port=int(raw.get("port", 8000)),
    )
