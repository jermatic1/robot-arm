"""`trainer run`: train submissions from the inbox, one at a time."""

import argparse
import logging
import time
from pathlib import Path

from trainer import config, inbox, train
from trainer.inbox import Status, Submission

log = logging.getLogger("trainer")


def process(cfg: config.Config, sub: Submission) -> None:
    previous = inbox.read_status(cfg.outputs, sub.task)
    if (
        previous
        and previous.submitted_at == sub.submitted_at
        and previous.state in ("done", "failed")
    ):
        sub.remove()  # finished before a restart; only the cleanup was missed
        return

    status = Status(
        task=sub.task,
        state="training",
        submitted_at=sub.submitted_at,
        episodes=sub.episodes,
        steps=cfg.steps,
        started_at=inbox.now(),
    )
    inbox.write_status(cfg.outputs, status)

    def on_step(step: int) -> None:
        status.step = step
        inbox.write_status(cfg.outputs, status)

    log.info("training %s (%d episodes)", sub.task, sub.episodes)
    try:
        train.run(cfg, sub, on_step)
        status.state, status.step = "done", cfg.steps
        log.info("finished %s", sub.task)
    except Exception as exc:  # noqa: BLE001 - any failure is reported to the robot
        status.state, status.error = "failed", str(exc)
        log.error("failed %s: %s", sub.task, exc)
    status.finished_at = inbox.now()
    inbox.write_status(cfg.outputs, status)
    sub.remove()


def mark_queued(cfg: config.Config, subs: list[Submission]) -> None:
    for sub in subs:
        current = inbox.read_status(cfg.outputs, sub.task)
        if current is None or current.submitted_at != sub.submitted_at:
            queued = Status(sub.task, "queued", sub.submitted_at, sub.episodes, steps=cfg.steps)
            inbox.write_status(cfg.outputs, queued)


def main() -> None:
    parser = argparse.ArgumentParser(prog="trainer")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="train submissions from the inbox, one at a time")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = config.load(args.config)
    cfg.inbox.mkdir(parents=True, exist_ok=True)
    cfg.outputs.mkdir(parents=True, exist_ok=True)
    log.info("watching %s", cfg.inbox)
    while True:
        subs = inbox.pending(cfg.inbox)
        mark_queued(cfg, subs)
        if subs:
            process(cfg, subs[0])
        else:
            time.sleep(cfg.poll_seconds)
