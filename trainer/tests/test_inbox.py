from conftest import submit

from trainer import inbox


def test_pending_is_oldest_first_and_skips_incomplete_or_bad(cfg):
    submit(cfg, "stack-cups", "20261002T100000Z")
    submit(cfg, "red-block", "20261001T100000Z")
    (cfg.inbox / "no-dataset@20261001T100000Z.ready").write_text(
        '{"submitted_at": "x", "episodes": 1}'
    )
    (cfg.inbox / "Bad_Name@20261001T100000Z").mkdir()
    (cfg.inbox / "Bad_Name@20261001T100000Z.ready").write_text(
        '{"submitted_at": "x", "episodes": 1}'
    )
    submit(cfg, "garbled", "20261001T100000Z").write_text("not json")
    (cfg.inbox / "copying@20261003T100000Z").mkdir()  # no marker yet

    assert [s.task for s in inbox.pending(cfg.inbox)] == ["red-block", "stack-cups"]


def test_newer_submission_replaces_older_one(cfg):
    old = submit(cfg, "red-block", "20261001T100000Z")
    new = submit(cfg, "red-block", "20261001T110000Z")

    [sub] = inbox.pending(cfg.inbox)

    assert sub.marker == new
    assert not old.exists() and not old.with_suffix("").exists()
