# Trainer

Trains an ACT policy with `lerobot-train` for each task the robot sends, one at a time. Runs on any
Linux computer with an NVIDIA or AMD GPU.

## Setup

1. Install [uv](https://docs.astral.sh/uv/) and rsync, and make sure the robot can reach this
   computer over ssh (see [robot setup](../robot/README.md#connecting-to-the-trainer)).

2. Get the code and install the PyTorch build for your GPU:

   ```sh
   git clone <this repo> ~/robot-arm
   cd ~/robot-arm/trainer
   uv sync --no-dev --extra cuda    # NVIDIA
   uv sync --no-dev --extra rocm    # AMD
   cp config.example.toml config.toml
   ```

3. Start on boot. In `deploy/trainer.service`, replace `CHANGE_ME` with your user name (and
   `--extra cuda` with `--extra rocm` on AMD):

   ```sh
   sudo cp deploy/trainer.service /etc/systemd/system/
   sudo systemctl enable --now trainer
   ```

Logs: `journalctl -u trainer -f`. Each task's training log is in
`~/robot-trainer/outputs/<task>/train.log`; its trained policy is in
`~/robot-trainer/outputs/<task>/runs/`.
