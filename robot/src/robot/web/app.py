"""HTTP API for the TV screens, plus camera streams and the static UI."""

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from robot.config import Config
from robot.library import TASK_NAME, Library
from robot.modes.play import Play
from robot.modes.record import Record
from robot.modes.run import Run
from robot.modes.session import NotConnected, Session
from robot.training import TrainerClient, TrainerError
from robot.web.stream import mjpeg

STATIC = Path(__file__).parent / "static"


class NewTask(BaseModel):
    name: str


class Press(BaseModel):
    action: str


def create_app(cfg: Config, session: Session, library: Library, trainer: TrainerClient) -> FastAPI:
    app = FastAPI(title="robot")
    sending: set[str] = set()
    send_errors: dict[str, str] = {}

    def task_or_404(slug: str):
        try:
            if not TASK_NAME.match(slug):
                raise KeyError(slug)
            return library.get(slug)
        except KeyError:
            raise HTTPException(404, "no such task") from None

    def remote_statuses() -> tuple[dict, str | None]:
        if not trainer.enabled:
            return {}, None
        try:
            return trainer.statuses(), None
        except TrainerError as exc:
            return {}, str(exc)

    def recording(slug: str) -> bool:
        mode = session.mode
        return isinstance(mode, Record) and mode.slug == slug

    def start(make_mode) -> None:
        try:
            session.start(make_mode)
        except NotConnected as exc:
            raise HTTPException(409, str(exc)) from None

    def check_not_sending(slug: str) -> None:
        if slug in sending:
            raise HTTPException(409, "wait until the task has been sent")

    @app.get("/api/status")
    def status() -> dict:
        free = library.free_gb()
        return {
            **session.status(),
            "cameras": list(cfg.cameras),
            "training_enabled": trainer.enabled,
            "storage": {"free_gb": round(free, 1), "low": free < cfg.warn_below_gb},
        }

    @app.post("/api/play")
    def play() -> None:
        start(lambda: Play(session.backend))

    @app.post("/api/press")
    def press(body: Press) -> None:
        if body.action not in ("next", "redo", "stop"):
            raise HTTPException(400, "unknown action")
        session.press(body.action)

    @app.post("/api/reconnect")
    def reconnect() -> None:
        session.clear_error()
        if not session.connected:
            threading.Thread(target=session.connect, daemon=True).start()

    @app.post("/api/error/clear")
    def clear_error() -> None:
        session.clear_error()

    @app.get("/api/tasks")
    def tasks() -> dict:
        remote, trainer_error = remote_statuses()
        result = []
        for task in library.tasks():
            status = remote.get(task.slug)
            training = None
            if task.slug in sending:
                training = {"state": "sending"}
            elif task.slug in send_errors:
                training = {"state": "failed", "error": send_errors[task.slug]}
            elif task.submitted_at:
                if status and status.submitted_at == task.submitted_at:
                    percent = round(100 * status.step / status.steps) if status.steps else 0
                    training = {"state": status.state, "percent": percent, "error": status.error}
                else:
                    training = {"state": "queued"}
            trained_at = status.submitted_at if status and status.state == "done" else None
            result.append(
                {
                    "slug": task.slug,
                    "name": task.name,
                    "episodes": task.episodes,
                    "target": cfg.record.target_episodes,
                    "has_data": task.has_data,
                    "submitted_episodes": task.submitted_episodes,
                    "training": training,
                    "has_policy": bool(task.policy_finished_at or trained_at),
                    "can_delete": library.can_delete_recordings(task, trained_at),
                }
            )
        return {"tasks": result, "trainer_error": trainer_error}

    @app.post("/api/tasks")
    def new_task(body: NewTask) -> dict:
        try:
            slug = library.add(body.name)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        check_not_sending(slug)
        start(lambda: Record(session.backend, library, cfg.record, slug))
        return {"slug": slug}

    @app.post("/api/tasks/{slug}/record")
    def record(slug: str) -> None:
        task_or_404(slug)
        check_not_sending(slug)
        start(lambda: Record(session.backend, library, cfg.record, slug))

    @app.post("/api/tasks/{slug}/submit")
    def submit(slug: str) -> None:
        task = task_or_404(slug)
        if not trainer.enabled:
            raise HTTPException(409, "no training computer is set up")
        if recording(slug) or slug in sending:
            raise HTTPException(409, "finish recording first")
        if task.episodes == 0:
            raise HTTPException(409, "nothing recorded yet")

        def send() -> None:
            try:
                at = trainer.submit(slug, library.dataset_dir(slug), task.episodes)
                library.mark_submitted(slug, at, task.episodes)
            except TrainerError as exc:
                send_errors[slug] = str(exc)
            finally:
                sending.discard(slug)

        send_errors.pop(slug, None)
        sending.add(slug)
        threading.Thread(target=send, daemon=True).start()

    @app.post("/api/tasks/{slug}/run")
    def run_policy(slug: str) -> None:
        task_or_404(slug)
        start(lambda: Run(session.backend, library, trainer, slug))

    @app.post("/api/tasks/{slug}/delete-recordings")
    def delete_recordings(slug: str) -> None:
        task = task_or_404(slug)
        remote, _ = remote_statuses()
        status = remote.get(slug)
        trained_at = status.submitted_at if status and status.state == "done" else None
        check_not_sending(slug)
        if recording(slug) or not library.can_delete_recordings(task, trained_at):
            raise HTTPException(409, "the training computer doesn't have this task yet")
        library.delete_recordings(slug)

    @app.get("/stream/{camera}.mjpg")
    def stream(camera: str, request: Request) -> StreamingResponse:
        if camera not in cfg.cameras:
            raise HTTPException(404, "no such camera")
        return StreamingResponse(
            mjpeg(lambda: session.frame(camera), request.is_disconnected),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
