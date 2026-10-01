import json
from pathlib import Path

import pytest

from trainer.config import Config


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(inbox=tmp_path / "inbox", outputs=tmp_path / "outputs", steps=1000)


def submit(cfg: Config, task: str, stamp: str, episodes: int = 3) -> Path:
    """Lay out a complete submission the way the robot does. `stamp` is like 20261001T100000Z."""
    dataset = cfg.inbox / f"{task}@{stamp}"
    (dataset / "meta").mkdir(parents=True)
    (dataset / "meta" / "info.json").write_text("{}")
    marker = dataset.with_name(f"{dataset.name}.ready")
    submitted_at = (
        f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}"
    )
    marker.write_text(json.dumps({"submitted_at": submitted_at, "episodes": episodes}))
    return marker
