"""Trainer settings loaded from config.toml."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    inbox: Path
    outputs: Path
    policy: str = "act"
    steps: int = 100_000
    batch_size: int = 8
    poll_seconds: float = 10


def load(path: Path) -> Config:
    raw = tomllib.loads(path.read_text())
    return Config(
        inbox=Path(raw["inbox"]).expanduser(),
        outputs=Path(raw["outputs"]).expanduser(),
        policy=raw.get("policy", "act"),
        steps=int(raw.get("steps", 100_000)),
        batch_size=int(raw.get("batch_size", 8)),
        poll_seconds=float(raw.get("poll_seconds", 10)),
    )
