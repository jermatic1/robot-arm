import pytest
from conftest import wait_for
from fastapi.testclient import TestClient

from robot.web.app import create_app


@pytest.fixture
def client(cfg, session, library, trainer):
    return TestClient(create_app(cfg, session, library, trainer))


def test_new_task_starts_recording(client, session):
    slug = client.post("/api/tasks", json={"name": "Stack the cups"}).json()["slug"]
    assert slug == "stack-the-cups"
    assert client.get("/api/status").json()["mode"] == "record"


def test_cannot_send_while_recording_or_empty(client, session):
    slug = client.post("/api/tasks", json={"name": "cups"}).json()["slug"]
    assert client.post(f"/api/tasks/{slug}/submit").status_code == 409

    client.post("/api/play")
    assert client.post(f"/api/tasks/{slug}/submit").status_code == 409  # nothing recorded


def test_send_then_show_training_progress(client, library, trainer, remote):
    slug = library.add("cups")
    info = library.dataset_dir(slug) / "meta" / "info.json"
    info.parent.mkdir(parents=True)
    info.write_text('{"total_episodes": 30}')

    assert client.post(f"/api/tasks/{slug}/submit").status_code == 200
    wait_for(lambda: library.get(slug).submitted_at is not None)
    submitted_at = library.get(slug).submitted_at

    [task] = client.get("/api/tasks").json()["tasks"]
    assert task["training"]["state"] == "queued"
    assert client.post(f"/api/tasks/{slug}/delete-recordings").status_code == 409

    remote.statuses = [
        {"task": slug, "state": "done", "submitted_at": submitted_at, "step": 10, "steps": 10}
    ]
    trainer._cache = (0.0, {}, None)  # skip the status cache
    [task] = client.get("/api/tasks").json()["tasks"]
    assert task["training"] == {"state": "done", "percent": 100, "error": None}
    assert task["can_delete"]
    assert client.post(f"/api/tasks/{slug}/delete-recordings").status_code == 200


def test_unknown_task_is_404(client):
    assert client.post("/api/tasks/Bad_Name/submit").status_code == 404
    assert client.post("/api/tasks/nope/run").status_code == 404


def test_modes_are_refused_while_disconnected(client, session):
    session.shutdown()
    assert client.post("/api/play").status_code == 409


def test_failed_connect_is_reported_and_cleaned_up(cfg):
    from robot.hardware.fake import FakeBackend
    from robot.modes.session import Session

    class HalfConnects(FakeBackend):
        def connect(self):
            self.connected = True  # first camera opened
            raise RuntimeError("wrist camera (/dev/video2) didn't open")

    session = Session(HalfConnects(list(cfg.cameras)))
    session.connect()

    assert not session.connected
    assert "wrist camera" in session.status()["error"]
    assert session.frame("front") is None
    assert not session.backend.connected  # disconnect() ran
