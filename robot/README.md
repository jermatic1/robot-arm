# Robot

Runs on the computer connected to the arms. Handles teleoperation, recording, running trained
policies, and the web UI the TV app shows.

## Setup

1. Install tools, then log out and back in so the groups apply:

   ```sh
   sudo apt install git rsync openssh-client v4l-utils build-essential
   curl -LsSf https://astral.sh/uv/install.sh | sh
   sudo usermod -aG dialout,input,video $USER
   ```

2. Get the code and install (this takes a while the first time):

   ```sh
   git clone <this repo> ~/robot-arm
   cd ~/robot-arm/robot
   uv sync --no-dev
   cp config.example.toml config.toml
   ```

3. Fill in `config.toml`:
   - Arm ports: `ls /dev/serial/by-id/`
   - Camera paths: `uv run robot find-cameras` (unplug one camera to see which is which)
   - Foot pedal: `uv run robot find-pedal`, then `uv run robot find-pedal "<name>"` and press each
     pedal to see its key.
   - Training computer: the ssh destination, once the [trainer](../trainer/README.md) is set up.

4. Calibrate the arms (skip if already calibrated):

   ```sh
   uv run robot calibrate follower
   uv run robot calibrate leader
   ```

   LeRobot 0.6 reads calibrations from `~/.cache/huggingface/lerobot/calibration/robots/so_follower/`
   and `.../teleoperators/so_leader/`. Calibrations made with older versions are in `so101_follower/`
   and `so101_leader/`; copy them over to reuse them.

5. Start on boot. Stop anything else that uses the arms first (only one program can open the
   serial ports). Replace `CHANGE_ME` in `deploy/robot.service` with your user name, then:

   ```sh
   sudo cp deploy/robot.service /etc/systemd/system/
   sudo systemctl enable --now robot
   ```

6. Give the robot a fixed address in your router's DHCP settings. Open `http://<address>:8000`
   in a browser to check it works, then set up the [TV app](../tv/README.md).

## Connecting to the trainer

The robot copies datasets to the trainer over ssh and needs a key the trainer accepts:

```sh
ssh-keygen -t ed25519           # press Enter at each prompt
ssh-copy-id <user>@<trainer>
ssh <user>@<trainer> true       # must work without a password
```

Then set `host = "<user>@<trainer>"` under `[trainer]` in `config.toml` and restart:
`sudo systemctl restart robot`.

## Notes

- Policies run on the CPU. GPU PyTorch for JetPack 6 is only built for Python 3.10, and LeRobot
  needs 3.12.
- Running a policy the first time downloads the ResNet-18 backbone weights, so the robot needs
  internet access once.
- Logs: `journalctl -u robot -f`
