# Robot Arm

Record episodes of a task with an SO-101 leader and follower arm, train an ACT policy on them with
LeRobot, and run the policy on the follower arm. Controlled from a Google TV app and a USB foot
pedal.

| Part | Runs on | Purpose |
|---|---|---|
| [`robot/`](robot/README.md) | Computer connected to the arms (Jetson Orin Nano) | Teleoperation, recording, running policies, web UI |
| [`trainer/`](trainer/README.md) | Linux computer with an NVIDIA or AMD GPU (the training computer) | Trains policies on the recorded episodes |
| [`tv/`](tv/README.md) | Google TV | Shows the web UI full screen, controlled with the remote |

Set them up in that order.

## Hardware

- SO-101 leader and follower arms.
- Two 32×32 mm USB camera modules, 720p/30 fps or better (TheRobotStudio recommends an Innomaker
  module). Plug them directly into the robot computer, not through a hub, and always into the same
  ports; identical cameras are told apart by port.
- Camera mounts from [SO-ARM100 `Optional/`](https://github.com/TheRobotStudio/SO-ARM100/tree/main/Optional):
  - Wrist: *SO101 Wrist Cam Hex-Nut Mount* (4× M2 screws, 2× M3×8 mm screws, 2× M3 hex nuts).
  - Overhead: *Overhead Cam Mount 32x32 UVC Module* (16× M2 screws).
- Route the wrist camera cable along the arm with a slack loop at each joint, and check the full
  range of motion before fastening it.
- USB foot pedal with three pedals that send keyboard keys.

## Usage

**Play:** the follower arm copies the leader arm. This is the default mode.

**Record:**

1. Choose **Record**, then pick a task or enter a new one, e.g. *pick up the red block*.
2. Each episode runs a countdown, then records while you perform the task with the leader arm,
   then gives you time to reset the scene.
3. Pedals (or the on-screen buttons): **next** ends the current step early, **redo** discards
   the episode, **stop** ends recording. Stopping during an episode discards it.
4. Record about 50 episodes per task. Keep the cameras fixed and vary the object's position.

**Train and run:**

1. Choose **Train and run**, then **Send to training computer** for the task. Progress is shown
   on the screen.
2. When training is done, choose **Run**. The follower arm performs the task until you press
   **Stop** or the stop pedal.

**Delete recordings** removes a task's episodes from the robot once the training computer has
trained on them.
