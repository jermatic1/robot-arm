import sys
import textwrap

import pytest
from conftest import submit

from trainer import cli, inbox, train

FAKE_TRAIN = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    args = dict(a.split("=", 1) for a in sys.argv[1:])
    assert Path(args["--dataset.root"], "meta", "info.json").is_file()
    for step in ("200", "1K"):
        print(f"INFO step:{step} smpl:1K loss:0.5", flush=True)
    model = Path(args["--output_dir"], "checkpoints", "last", "pretrained_model")
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}")
    sys.exit(int(args.get("--fail", "0")))
    """
)


@pytest.fixture
def fake_lerobot(monkeypatch, tmp_path):
    script = tmp_path / "fake_train.py"
    script.write_text(FAKE_TRAIN)
    extra = []
    monkeypatch.setattr(
        train,
        "command",
        lambda cfg, task, dataset, out: [
            sys.executable,
            str(script),
            f"--dataset.root={dataset}",
            f"--output_dir={out}",
            *extra,
        ],
    )
    return extra


@pytest.mark.parametrize(
    ("line", "step"),
    [("step:200 smpl:1K", 200), ("x step:12K y", 12_000), ("step:1M", 1_000_000), ("loss:1", None)],
)
def test_parse_step(line, step):
    assert train.parse_step(line) == step


def train_next(cfg):
    [sub] = inbox.pending(cfg.inbox)
    cli.process(cfg, sub)
    return sub


def test_success_links_policy_and_removes_submission(cfg, fake_lerobot):
    submit(cfg, "red-block", "20261001T100000Z")
    sub = train_next(cfg)

    status = inbox.read_status(cfg.outputs, "red-block")
    assert status.state == "done" and status.finished_at
    assert (cfg.outputs / "red-block" / "policy" / "config.json").is_file()
    assert not sub.marker.exists() and not sub.dataset.exists()


def test_retraining_keeps_current_and_previous_run(cfg, fake_lerobot):
    for stamp in ("20261001T100000Z", "20261001T110000Z", "20261001T120000Z"):
        submit(cfg, "red-block", stamp)
        train_next(cfg)

    runs = sorted(p.name for p in (cfg.outputs / "red-block" / "runs").iterdir())
    assert runs == ["20261001T110000Z", "20261001T120000Z"]
    policy = (cfg.outputs / "red-block" / "policy").resolve()
    assert policy.is_relative_to(cfg.outputs / "red-block" / "runs" / "20261001T120000Z")


def test_failure_is_reported_and_cleaned_up(cfg, fake_lerobot):
    fake_lerobot.append("--fail=1")
    submit(cfg, "red-block", "20261001T100000Z")
    train_next(cfg)

    status = inbox.read_status(cfg.outputs, "red-block")
    assert status.state == "failed" and "exited with 1" in status.error
    assert not (cfg.outputs / "red-block" / "policy").exists()
    assert list((cfg.outputs / "red-block" / "runs").iterdir()) == []


def test_finished_submission_is_not_retrained_after_restart(cfg, fake_lerobot, monkeypatch):
    submit(cfg, "red-block", "20261001T100000Z")
    [sub] = inbox.pending(cfg.inbox)
    done = inbox.Status("red-block", "done", sub.submitted_at, finished_at="x")
    inbox.write_status(cfg.outputs, done)
    monkeypatch.setattr(train, "run", lambda *a: pytest.fail("retrained"))

    cli.process(cfg, sub)

    assert not sub.marker.exists()


def test_new_submission_is_marked_queued(cfg, fake_lerobot):
    submit(cfg, "red-block", "20261001T100000Z")
    train_next(cfg)
    submit(cfg, "red-block", "20261001T110000Z")

    cli.mark_queued(cfg, inbox.pending(cfg.inbox))

    assert inbox.read_status(cfg.outputs, "red-block").state == "queued"
