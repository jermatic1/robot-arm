"""Record demonstrations, one episode at a time.

Each episode goes countdown → recording → reset (time to put things back) → saved.
"next" ends the current phase early, "redo" discards the episode after its reset, and "stop"
ends recording. Stopping during recording discards that episode; stopping during reset keeps it.
"""

import time

from robot.config import Record as RecordConfig
from robot.hardware import Backend
from robot.library import Library


class Record:
    name = "record"

    def __init__(self, backend: Backend, library: Library, cfg: RecordConfig, slug: str):
        self.backend = backend
        self.library = library
        self.cfg = cfg
        self.slug = slug
        self.task_name = library.get(slug).name
        self.events: dict | None = None
        self.phase = "starting"
        self.phase_ends = 0.0
        self.episodes = library.episodes(slug)

    def _phase(self, phase: str, seconds: float) -> None:
        self.phase = phase
        self.phase_ends = time.monotonic() + seconds
        # Ignore presses left over from the last phase, unless stopping.
        if self.events is not None and not self.events["stop_recording"]:
            self.events["exit_early"] = False

    def run(self, events: dict) -> None:
        self.events = events
        dataset = self.backend.open_dataset(self.library.dataset_dir(self.slug), self.task_name)
        self.episodes = dataset.num_episodes
        error = None
        try:
            while not events["stop_recording"]:
                self._phase("countdown", self.cfg.countdown_seconds)
                self.backend.teleop(self.cfg.countdown_seconds, events)
                if events["stop_recording"]:
                    break
                events["rerecord_episode"] = False

                self._phase("recording", self.cfg.episode_seconds)
                self.backend.record(dataset, self.cfg.episode_seconds, events, self.task_name)
                if events["stop_recording"]:
                    dataset.clear_episode_buffer()
                    break

                self._phase("reset", self.cfg.reset_seconds)
                self.backend.teleop(self.cfg.reset_seconds, events)
                if events["rerecord_episode"]:
                    events["rerecord_episode"] = False
                    dataset.clear_episode_buffer()
                    continue

                self._phase("saving", 0)
                dataset.save_episode()
                self.episodes = dataset.num_episodes
        except BaseException as exc:
            error = exc
            raise
        finally:
            self._phase("saving", 0)
            dataset.finalize(error)

    def press(self, action: str) -> None:
        if self.events is None:
            return
        if action == "redo" and self.phase in ("recording", "reset"):
            self.events["rerecord_episode"] = True
        elif action == "stop":
            self.events["stop_recording"] = True
        elif action != "next":
            return
        self.events["exit_early"] = True

    def status(self) -> dict:
        return {
            "task": {"slug": self.slug, "name": self.task_name},
            "phase": self.phase,
            "seconds_left": max(0.0, round(self.phase_ends - time.monotonic(), 1)),
            "episodes": self.episodes,
            "target": self.cfg.target_episodes,
        }
