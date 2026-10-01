"""Run lerobot-train for one submission and report progress."""

import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from trainer.config import Config
from trainer.inbox import Submission

# lerobot logs whole steps abbreviated, e.g. "step:200", "step:12K", "step:1M",
# so progress is approximate.
STEP = re.compile(r"\bstep:(\d+)([KMB]?)\b")
SCALE = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_step(line: str) -> int | None:
    match = STEP.search(line)
    if not match:
        return None
    return int(match.group(1)) * SCALE[match.group(2)]


def command(cfg: Config, task: str, dataset: Path, output_dir: Path) -> list[str]:
    lerobot_train = Path(sys.executable).with_name("lerobot-train")
    return [
        str(lerobot_train),
        f"--dataset.repo_id=local/{task}",
        f"--dataset.root={dataset}",
        f"--policy.type={cfg.policy}",
        "--policy.push_to_hub=false",
        f"--output_dir={output_dir}",
        f"--job_name={task}",
        f"--steps={cfg.steps}",
        f"--batch_size={cfg.batch_size}",
    ]


def run(cfg: Config, sub: Submission, on_step: Callable[[int], None]) -> Path:
    """Train on the submitted dataset and point outputs/<task>/policy at the result.

    Raises RuntimeError if training fails; the log is kept at outputs/<task>/train.log.
    """
    task_dir = cfg.outputs / sub.task
    runs = task_dir / "runs"
    run_dir = runs / sub.dataset.name.split("@", 1)[1]
    shutil.rmtree(run_dir, ignore_errors=True)  # left over from an interrupted attempt
    runs.mkdir(parents=True, exist_ok=True)

    log_path = task_dir / "train.log"
    last_report = 0.0
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            command(cfg, sub.task, sub.dataset, run_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                step = parse_step(line)
                if step is not None and time.monotonic() - last_report > 5:
                    on_step(step)
                    last_report = time.monotonic()
            code = proc.wait()
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait()

    model = run_dir / "checkpoints" / "last" / "pretrained_model"
    if code != 0 or not model.is_dir():
        shutil.rmtree(run_dir, ignore_errors=True)
        raise RuntimeError(f"lerobot-train exited with {code}; see {log_path}")

    link = task_dir / "policy"
    previous = link.resolve() if link.is_symlink() else None
    tmp = task_dir / "policy.tmp"
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(model.resolve())
    tmp.replace(link)
    # Keep the previous run too, in case the robot is still copying it.
    for old in runs.iterdir():
        if old != run_dir and (previous is None or not previous.is_relative_to(old)):
            shutil.rmtree(old, ignore_errors=True)
    return model
