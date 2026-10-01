# Agent notes

- Three independent projects: `robot/` (Python, uv), `trainer/` (Python, uv), `tv/` (Kotlin,
  Gradle). Run commands from inside the project folder. See CONTRIBUTING.md for checks.
- Before finishing Python changes, run the project's `pytest` and `ruff check` / `ruff format`.
- LeRobot is pinned (0.6.1). In `robot/`, only `src/robot/hardware/real.py` may import it; tests
  and `robot serve --fake` use `hardware/fake.py`.
- The robot ↔ trainer file protocol is documented in `trainer/src/trainer/inbox.py`; change both
  sides together.
- The TV UI (`robot/src/robot/web/static/`) must stay usable with only arrow keys, Enter, and Back.
