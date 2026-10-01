"""The file protocol shared with the robot.

    inbox/<task>@<stamp>/         dataset copied from the robot (stamp is UTC, 20261001T100000Z)
    inbox/<task>@<stamp>.ready    JSON {"submitted_at", "episodes"}, written after the copy
    outputs/<task>/status.json    one-line JSON the robot reads over ssh
    outputs/<task>/policy         symlink to the latest trained pretrained_model/

A newer submission of the same task replaces any older one that hasn't started training.
"""

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

TASK_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SUBMISSION = re.compile(r"^(?P<task>[a-z0-9][a-z0-9-]{0,63})@(?P<stamp>\d{8}T\d{6}Z)$")


@dataclass
class Submission:
    task: str
    submitted_at: str
    episodes: int
    marker: Path

    @property
    def dataset(self) -> Path:
        return self.marker.with_suffix("")

    def remove(self) -> None:
        self.marker.unlink(missing_ok=True)
        shutil.rmtree(self.dataset, ignore_errors=True)


@dataclass
class Status:
    task: str
    state: str  # queued | training | done | failed
    submitted_at: str
    episodes: int = 0
    step: int = 0
    steps: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def pending(inbox: Path) -> list[Submission]:
    """The newest complete submission per task, oldest task first. Older ones are removed."""
    latest: dict[str, Submission] = {}
    for marker in sorted(inbox.glob("*.ready")):
        match = SUBMISSION.match(marker.stem)
        if not match or not marker.with_suffix("").is_dir():
            continue
        try:
            data = json.loads(marker.read_text())
            sub = Submission(match["task"], data["submitted_at"], int(data["episodes"]), marker)
        except (OSError, ValueError, KeyError):
            continue
        older = latest.get(sub.task)
        if older is not None:
            older.remove()
        latest[sub.task] = sub
    return sorted(latest.values(), key=lambda s: s.submitted_at)


def read_status(outputs: Path, task: str) -> Status | None:
    try:
        return Status(**json.loads((outputs / task / "status.json").read_text()))
    except (OSError, ValueError, TypeError):
        return None


def write_status(outputs: Path, status: Status) -> None:
    path = outputs / status.task / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(status)) + "\n")
    tmp.replace(path)
