import json

import pytest

from robot.modes.run import Run
from robot.training import TrainerError


def test_submit_copies_to_new_folder_then_marks_it_complete(trainer, remote, tmp_path):
    sent = {}
    real = remote.__call__

    def capture(args, input=None, **kwargs):
        if input is not None:
            sent.update(json.loads(input))
        return real(args, **kwargs)

    trainer._run = capture
    submitted_at = trainer.submit("red-block", tmp_path / "red-block", 12)

    clean, rsync, finish = remote.calls
    assert "rm -rf ~/robot-trainer/inbox/red-block@*.partial" in clean[-1]
    dest = rsync[-1].removeprefix("trainer.local:")
    assert dest.startswith("~/robot-trainer/inbox/red-block@") and dest.endswith(".partial/")
    name = dest.removesuffix(".partial/")
    assert (
        finish[-1] == f"mv {name}.partial {name} && cat > {name}.tmp && mv {name}.tmp {name}.ready"
    )
    assert sent == {"submitted_at": submitted_at, "episodes": 12}


def test_statuses_skip_bad_lines(trainer, remote):
    remote.statuses = [{"task": "red-block", "state": "training", "submitted_at": "t", "step": 5}]
    assert trainer.statuses()["red-block"].step == 5


def test_unreachable_trainer_is_reported_and_not_retried_every_poll(trainer, remote):
    remote.fail = True
    for _ in range(2):
        with pytest.raises(TrainerError, match="No route"):
            trainer.statuses()
    assert len(remote.calls) == 1


def test_run_downloads_only_newer_policy(session, library, trainer, remote):
    slug = library.add("red block")
    remote.statuses = [{"task": slug, "state": "done", "submitted_at": "t", "finished_at": "f1"}]

    Run(session.backend, library, trainer, slug)._latest_policy()
    assert (library.policy_dir(slug) / "config.json").is_file()
    assert library.get(slug).policy_finished_at == "f1"

    remote.calls.clear()
    trainer._cache = (0.0, {}, None)
    Run(session.backend, library, trainer, slug)._latest_policy()
    assert not [c for c in remote.calls if c[0] == "rsync"]


def test_run_uses_local_policy_when_trainer_is_offline(session, library, trainer, remote):
    slug = library.add("red block")
    library.policy_dir(slug).mkdir(parents=True)
    remote.fail = True
    run = Run(session.backend, library, trainer, slug)
    events = {"exit_early": True, "rerecord_episode": False, "stop_recording": False}

    run.run(events)  # returns at once because exit_early is set

    assert run.phase == "running"
