"""Tasks (recorded datasets) and trained policies stored on the robot."""

import json
import re
import shutil
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from robot.config import Config

# Must match the trainer's task name rule.
TASK_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:64].strip("-")
    if not TASK_NAME.match(slug):
        raise ValueError(f"can't make a task name from {name!r}")
    return slug


@dataclass
class Task:
    slug: str
    name: str
    episodes: int
    submitted_at: str | None
    submitted_episodes: int
    has_data: bool
    policy_finished_at: str | None


class Library:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state_path = cfg.data / "state.json"
        self._lock = threading.Lock()

    def dataset_dir(self, slug: str) -> Path:
        return self.cfg.datasets / slug

    def policy_dir(self, slug: str) -> Path:
        return self.cfg.policies / slug / "pretrained_model"

    def _read(self) -> dict:
        # A damaged file raises instead of being treated as empty and overwritten.
        if not self.state_path.exists():
            return {"tasks": {}}
        return json.loads(self.state_path.read_text())

    def _write(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(self.state_path)

    def _update(self, slug: str, **fields) -> None:
        with self._lock:
            state = self._read()
            state["tasks"].setdefault(slug, {}).update(fields)
            self._write(state)

    def add(self, name: str) -> str:
        slug = slugify(name)
        with self._lock:
            state = self._read()
            state["tasks"].setdefault(slug, {"name": name.strip()})
            self._write(state)
        return slug

    def episodes(self, slug: str) -> int:
        try:
            info = json.loads((self.dataset_dir(slug) / "meta" / "info.json").read_text())
            return int(info["total_episodes"])
        except (OSError, ValueError, KeyError):
            return 0

    def get(self, slug: str) -> Task:
        entry = self._read()["tasks"].get(slug)
        if entry is None:
            raise KeyError(slug)
        return self._task(slug, entry)

    def tasks(self) -> list[Task]:
        entries = self._read()["tasks"]
        return sorted((self._task(s, e) for s, e in entries.items()), key=lambda x: x.name)

    def _task(self, slug: str, entry: dict) -> Task:
        return Task(
            slug=slug,
            name=entry.get("name", slug),
            episodes=self.episodes(slug),
            submitted_at=entry.get("submitted_at"),
            submitted_episodes=entry.get("submitted_episodes", 0),
            has_data=self.dataset_dir(slug).is_dir(),
            policy_finished_at=entry.get("policy_finished_at"),
        )

    def mark_submitted(self, slug: str, submitted_at: str, episodes: int) -> None:
        self._update(slug, submitted_at=submitted_at, submitted_episodes=episodes)

    def mark_policy(self, slug: str, finished_at: str) -> None:
        self._update(slug, policy_finished_at=finished_at)

    def free_gb(self) -> float:
        self.cfg.data.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(self.cfg.data).free / 1e9

    @staticmethod
    def can_delete_recordings(task: Task, trained_at: str | None) -> bool:
        """Only recordings the trainer already has in full, and has trained on, may be deleted."""
        return (
            task.has_data
            and task.submitted_at is not None
            and task.submitted_episodes == task.episodes
            and trained_at == task.submitted_at
        )

    def delete_recordings(self, slug: str) -> None:
        shutil.rmtree(self.dataset_dir(slug), ignore_errors=True)
