"""Play: the follower arm copies the leader arm."""

from robot.hardware import Backend


class Play:
    name = "play"

    def __init__(self, backend: Backend):
        self.backend = backend

    def run(self, events: dict) -> None:
        while not events["stop_recording"]:
            self.backend.teleop(float("inf"), events)

    def press(self, action: str) -> None:
        pass

    def status(self) -> dict:
        return {}
