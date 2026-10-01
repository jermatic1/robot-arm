"""Run a trained policy on the arm until stopped."""

import logging

from robot.hardware import Backend
from robot.library import Library
from robot.training import TrainerClient, TrainerError

log = logging.getLogger(__name__)


class Run:
    name = "run"

    def __init__(self, backend: Backend, library: Library, trainer: TrainerClient, slug: str):
        self.backend = backend
        self.library = library
        self.trainer = trainer
        self.slug = slug
        self.task_name = library.get(slug).name
        self.events: dict | None = None
        self.phase = "loading"

    def _latest_policy(self) -> None:
        """Download the policy if the trainer has a newer one than the robot."""
        if not self.trainer.enabled:
            return
        status = self.trainer.statuses().get(self.slug)
        task = self.library.get(self.slug)
        if status and status.state == "done" and status.finished_at != task.policy_finished_at:
            self.trainer.fetch(self.slug, self.library.policy_dir(self.slug))
            self.library.mark_policy(self.slug, status.finished_at)

    def run(self, events: dict) -> None:
        self.events = events
        try:
            self._latest_policy()
        except TrainerError as exc:
            if not self.library.policy_dir(self.slug).is_dir():
                raise
            log.warning("using the policy already on the robot: %s", exc)
        policy = self.backend.load_policy(self.library.policy_dir(self.slug))
        if events["stop_recording"]:
            return
        self.phase = "running"
        self.backend.drive(policy, events, self.task_name)

    def press(self, action: str) -> None:
        if action == "stop" and self.events is not None:
            self.events["stop_recording"] = True
            self.events["exit_early"] = True

    def status(self) -> dict:
        return {"task": {"slug": self.slug, "name": self.task_name}, "phase": self.phase}
