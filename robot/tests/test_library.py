import pytest

from robot.library import slugify


@pytest.mark.parametrize(
    ("name", "slug"),
    [("Pick up the red block!", "pick-up-the-red-block"), ("  Émile's cup  ", "emile-s-cup")],
)
def test_slugify(name, slug):
    assert slugify(name) == slug


def test_slugify_rejects_names_without_letters_or_digits():
    with pytest.raises(ValueError):
        slugify("!!!")


def record(library, slug, episodes):
    info = library.dataset_dir(slug) / "meta" / "info.json"
    info.parent.mkdir(parents=True, exist_ok=True)
    info.write_text(f'{{"total_episodes": {episodes}}}')


def test_can_delete_recordings_only_what_the_trainer_has_trained_on(library):
    slug = library.add("red block")
    record(library, slug, 20)
    assert not library.can_delete_recordings(library.get(slug), trained_at=None)

    library.mark_submitted(slug, "2026-10-01T10:00:00+00:00", 20)
    task = library.get(slug)
    assert not library.can_delete_recordings(task, trained_at=None)
    assert library.can_delete_recordings(task, trained_at="2026-10-01T10:00:00+00:00")

    record(library, slug, 25)  # more recorded since sending
    assert not library.can_delete_recordings(
        library.get(slug), trained_at="2026-10-01T10:00:00+00:00"
    )


def test_delete_recordings_removes_recordings_but_keeps_the_task(library):
    slug = library.add("red block")
    record(library, slug, 3)
    library.delete_recordings(slug)

    task = library.get(slug)
    assert not task.has_data and task.episodes == 0


def test_damaged_state_file_is_not_overwritten(library):
    library.add("red block")
    library.state_path.write_text("{not json")

    with pytest.raises(ValueError):
        library.add("cups")
    assert library.state_path.read_text() == "{not json"
