"""Hand tasks to the training computer and bring trained policies back, over ssh and rsync.

The file layout on the trainer is documented in the trainer project (trainer/src/trainer/inbox.py).
"""

import json
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from robot.config import Trainer

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
STATUS_TTL = 10

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class Status:
    state: str  # queued | training | done | failed
    submitted_at: str
    step: int = 0
    steps: int = 0
    finished_at: str | None = None
    error: str | None = None


class TrainerError(RuntimeError):
    pass


class TrainerClient:
    def __init__(self, cfg: Trainer, run: Runner = subprocess.run):
        self.cfg = cfg
        self._run = run
        self._cache: tuple[float, dict[str, Status], TrainerError | None] = (0.0, {}, None)
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.host)

    def _call(self, args: Sequence[str], **kwargs) -> subprocess.CompletedProcess:
        result = self._run(list(args), capture_output=True, text=True, **kwargs)
        if result.returncode != 0:
            detail = result.stderr.strip() or f"{args[0]} exited with {result.returncode}"
            raise TrainerError(detail)
        return result

    def submit(self, slug: str, dataset: Path, episodes: int) -> str:
        """Copy the dataset to a new folder, then write the marker that says it's complete."""
        host, inbox = self.cfg.host, self.cfg.inbox
        now = datetime.now(UTC).replace(microsecond=0)
        name = f"{inbox}/{slug}@{now:%Y%m%dT%H%M%SZ}"
        self._call([*SSH, host, f"mkdir -p {inbox} && rm -rf {inbox}/{slug}@*.partial"])
        self._call(["rsync", "-a", f"{dataset}/", f"{host}:{name}.partial/"])
        submitted_at = now.isoformat()
        marker = json.dumps({"submitted_at": submitted_at, "episodes": episodes})
        finish = f"mv {name}.partial {name} && cat > {name}.tmp && mv {name}.tmp {name}.ready"
        self._call([*SSH, host, finish], input=marker)
        self._cache = (0.0, {}, None)
        return submitted_at

    def statuses(self) -> dict[str, Status]:
        """Latest status per task. Results and failures are cached briefly so the TV can poll."""
        with self._lock:
            fetched, cached, error = self._cache
            if time.monotonic() - fetched < STATUS_TTL:
                if error:
                    raise error
                return cached
            try:
                result = self._call(
                    [*SSH, self.cfg.host, f"cat {self.cfg.outputs}/*/status.json 2>/dev/null; true"]
                )
            except TrainerError as exc:
                self._cache = (time.monotonic(), {}, exc)
                raise
            statuses = {}
            for line in result.stdout.splitlines():
                try:
                    raw = json.loads(line)
                    statuses[raw["task"]] = Status(
                        state=raw["state"],
                        submitted_at=raw["submitted_at"],
                        step=raw.get("step", 0),
                        steps=raw.get("steps", 0),
                        finished_at=raw.get("finished_at"),
                        error=raw.get("error"),
                    )
                except (ValueError, KeyError):
                    continue
            self._cache = (time.monotonic(), statuses, None)
            return statuses

    def fetch(self, slug: str, dest: Path) -> None:
        src = f"{self.cfg.host}:{self.cfg.outputs}/{slug}/policy/"
        dest.mkdir(parents=True, exist_ok=True)
        self._call(["rsync", "-a", "--copy-links", "--delete", src, f"{dest}/"])
