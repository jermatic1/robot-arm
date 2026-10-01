import json
import subprocess
import time
from pathlib import Path

import pytest

from robot.config import Arm, Camera, Config, Record, Trainer
from robot.hardware.fake import FakeBackend
from robot.library import Library
from robot.modes.session import Session
from robot.training import TrainerClient


def wait_for(predicate, timeout: float = 3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out")


class FakeRemote:
    """Stands in for ssh/rsync: records commands and answers status queries."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.statuses: list[dict] = []
        self.fail = False

    def __call__(self, args, input=None, **kwargs):
        self.calls.append(args)
        if self.fail:
            return subprocess.CompletedProcess(args, 255, "", "ssh: connect: No route to host")
        stdout = ""
        if args[0] == "ssh" and "status.json" in args[-1]:
            stdout = "".join(json.dumps(s) + "\n" for s in self.statuses) + "garbage\n"
        if args[0] == "rsync" and "/policy/" in args[-2]:
            dest = Path(args[-1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "config.json").write_text("{}")
        return subprocess.CompletedProcess(args, 0, stdout, "")


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(
        follower=Arm("/dev/null", "follower"),
        leader=Arm("/dev/null", "leader"),
        cameras={"front": Camera("/dev/null"), "wrist": Camera("/dev/null")},
        data=tmp_path / "data",
        record=Record(countdown_seconds=0.05, episode_seconds=0.3, reset_seconds=0.3),
        trainer=Trainer(host="trainer.local"),
    )


@pytest.fixture
def remote() -> FakeRemote:
    return FakeRemote()


@pytest.fixture
def trainer(cfg, remote) -> TrainerClient:
    return TrainerClient(cfg.trainer, run=remote)


@pytest.fixture
def library(cfg) -> Library:
    return Library(cfg)


@pytest.fixture
def session(cfg):
    session = Session(FakeBackend(list(cfg.cameras)))
    session.connect()
    yield session
    session.shutdown()
