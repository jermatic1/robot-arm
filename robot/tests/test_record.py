import time

from conftest import wait_for

from robot.modes.play import Play
from robot.modes.record import Record


def start_record(session, library, cfg, name="Pick up the red block") -> Record:
    slug = library.add(name)
    session.start(lambda: Record(session.backend, library, cfg.record, slug))
    return session.mode


def phase_is(mode, phase):
    return lambda: mode.phase == phase


def test_next_saves_episode_after_reset(session, library, cfg):
    rec = start_record(session, library, cfg)
    wait_for(phase_is(rec, "recording"))
    session.press("next")
    wait_for(phase_is(rec, "reset"))
    session.press("next")
    wait_for(lambda: rec.episodes == 1)
    assert library.episodes(rec.slug) == 1


def test_redo_discards_episode(session, library, cfg):
    rec = start_record(session, library, cfg)
    wait_for(phase_is(rec, "recording"))
    session.press("redo")
    wait_for(phase_is(rec, "reset"))
    wait_for(phase_is(rec, "recording"))
    assert rec.episodes == 0
    assert session.backend.dataset.discarded == 1


def test_stop_while_recording_discards_and_returns_to_play(session, library, cfg):
    rec = start_record(session, library, cfg)
    wait_for(phase_is(rec, "recording"))
    session.press("stop")
    wait_for(lambda: isinstance(session.mode, Play))
    assert library.episodes(rec.slug) == 0
    assert session.backend.dataset.discarded == 1


def test_stop_during_reset_keeps_episode(session, library, cfg):
    rec = start_record(session, library, cfg)
    wait_for(phase_is(rec, "reset"))
    session.press("stop")
    wait_for(lambda: isinstance(session.mode, Play))
    assert library.episodes(rec.slug) == 1


def test_task_continues_from_saved_episodes(session, library, cfg):
    first = start_record(session, library, cfg)
    wait_for(phase_is(first, "reset"))
    session.press("stop")
    wait_for(lambda: isinstance(session.mode, Play))

    second = start_record(session, library, cfg)
    wait_for(phase_is(second, "countdown"))
    assert second.episodes == 1


def test_choosing_another_mode_replaces_recording_without_extra_restarts(session, library, cfg):
    start_record(session, library, cfg)
    session.start(lambda: Play(session.backend))
    play = session.mode
    time.sleep(0.2)
    assert session.mode is play
