"""The only module that talks to LeRobot."""

import logging
import time
from pathlib import Path

import numpy as np
import torch
from lerobot.cameras.opencv import OpenCVCameraConfig
from lerobot.common.control_utils import sanity_check_dataset_robot_compatibility
from lerobot.configs import PreTrainedConfig, RGBEncoderConfig
from lerobot.datasets import LeRobotDataset
from lerobot.datasets.pipeline_features import (
    aggregate_pipeline_dataset_features,
    create_initial_features,
)
from lerobot.datasets.video_utils import VideoEncodingManager
from lerobot.policies import make_pre_post_processors, make_robot_action
from lerobot.policies.factory import get_policy_class
from lerobot.policies.utils import build_inference_frame
from lerobot.processor import make_default_processors
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.scripts.lerobot_record import record_loop
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig
from lerobot.utils.feature_utils import combine_feature_dicts
from lerobot.utils.robot_utils import precise_sleep

from robot.config import Config

log = logging.getLogger(__name__)


def _quietly(label: str, close) -> None:
    try:
        close()
    except Exception:  # noqa: BLE001 - keep closing the rest
        log.exception("could not close the %s", label)


def make_follower(cfg: Config) -> SO101Follower:
    cameras = {
        name: OpenCVCameraConfig(
            index_or_path=Path(cam.path),
            width=cam.width,
            height=cam.height,
            fps=cam.fps,
            fourcc=cam.fourcc or None,
            warmup_s=cam.warmup_seconds,
        )
        for name, cam in cfg.cameras.items()
    }
    return SO101Follower(
        SO101FollowerConfig(port=cfg.follower.port, id=cfg.follower.id, cameras=cameras)
    )


def make_leader(cfg: Config) -> SO101Leader:
    return SO101Leader(SO101LeaderConfig(port=cfg.leader.port, id=cfg.leader.id))


def calibrate(device: SO101Follower | SO101Leader) -> None:
    device.connect(calibrate=False)
    try:
        device.calibrate()
    finally:
        device.disconnect()


class RealDataset:
    """A LeRobot dataset kept open while recording, with video encoding managed."""

    def __init__(self, dataset: LeRobotDataset):
        self.inner = dataset
        self._encoding = VideoEncodingManager(dataset)
        self._encoding.__enter__()

    @property
    def num_episodes(self) -> int:
        return self.inner.num_episodes

    def save_episode(self) -> None:
        self.inner.save_episode()

    def clear_episode_buffer(self) -> None:
        self.inner.clear_episode_buffer()

    def finalize(self, error: BaseException | None = None) -> None:
        # Finalizes the dataset; with an error, also cleans up the interrupted episode.
        tb = error.__traceback__ if error else None
        self._encoding.__exit__(type(error) if error else None, error, tb)


class RealPolicy:
    def __init__(self, path: Path, features: dict):
        cfg = PreTrainedConfig.from_pretrained(path)
        cfg.pretrained_path = path
        self.device = torch.device("cpu")
        cfg.device = "cpu"
        self.policy = get_policy_class(cfg.type).from_pretrained(path, config=cfg)
        self.policy.to(self.device).eval()
        self.pre, self.post = make_pre_post_processors(
            cfg,
            pretrained_path=str(path),
            preprocessor_overrides={"device_processor": {"device": "cpu"}},
        )
        self.features = features

    def reset(self) -> None:
        self.policy.reset()
        self.pre.reset()
        self.post.reset()

    def act(self, observation: dict, task: str, robot_type: str) -> dict:
        with torch.inference_mode():
            batch = build_inference_frame(observation, self.device, self.features, task, robot_type)
            action = self.post(self.policy.select_action(self.pre(batch)))
        return make_robot_action(action.squeeze(0).cpu(), self.features)


class RealBackend:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.fps = cfg.record.fps
        self.follower = make_follower(cfg)
        self.leader = make_leader(cfg)
        self.processors = make_default_processors()

    def connect(self) -> None:
        try:
            for device in (self.leader, self.follower):
                if not device.is_connected:
                    device.connect(calibrate=False)
                if not device.is_calibrated:
                    raise RuntimeError(f"{device.id} is not calibrated; run `robot calibrate`")
        except Exception as exc:
            # The follower opens its cameras one by one after its motors; name the one that failed.
            if self.follower.bus.is_connected:
                for name, cam in self.follower.cameras.items():
                    if not cam.is_connected:
                        path = self.cfg.cameras[name].path
                        raise RuntimeError(f"{name} camera ({path}) didn't open: {exc}") from exc
            raise

    def disconnect(self) -> None:
        """Close everything that's open, including after a connect that failed partway."""
        follower, leader = self.follower, self.leader
        if follower.bus.is_connected:
            disable_torque = follower.config.disable_torque_on_disconnect
            _quietly("follower arm", lambda: follower.bus.disconnect(disable_torque))
        for name, cam in follower.cameras.items():
            if cam.is_connected:
                _quietly(f"{name} camera", cam.disconnect)
        if leader.is_connected:
            _quietly("leader arm", leader.disconnect)

    def frame(self, camera: str) -> np.ndarray | None:
        cam = self.follower.cameras.get(camera)
        if cam is None or not cam.is_connected:
            return None
        try:
            return cam.read_latest(max_age_ms=1000)
        except Exception:  # noqa: BLE001 - a missing frame just shows as blank
            return None

    def features(self) -> dict:
        teleop_proc, _, obs_proc = self.processors
        return combine_feature_dicts(
            aggregate_pipeline_dataset_features(
                pipeline=teleop_proc,
                initial_features=create_initial_features(action=self.follower.action_features),
                use_videos=True,
            ),
            aggregate_pipeline_dataset_features(
                pipeline=obs_proc,
                initial_features=create_initial_features(
                    observation=self.follower.observation_features
                ),
                use_videos=True,
            ),
        )

    def _loop(self, seconds: float, events: dict, dataset=None, task=None) -> None:
        teleop_proc, robot_proc, obs_proc = self.processors
        record_loop(
            robot=self.follower,
            events=events,
            fps=self.fps,
            teleop_action_processor=teleop_proc,
            robot_action_processor=robot_proc,
            robot_observation_processor=obs_proc,
            dataset=dataset,
            teleop=self.leader,
            control_time_s=seconds,
            single_task=task,
        )

    def teleop(self, seconds: float, events: dict) -> None:
        self._loop(seconds, events)

    def record(self, dataset: RealDataset, seconds: float, events: dict, task: str) -> None:
        self._loop(seconds, events, dataset.inner, task)

    def open_dataset(self, root: Path, task: str) -> RealDataset:
        repo_id = f"local/{root.name}"
        encoder = RGBEncoderConfig(vcodec=self.cfg.record.vcodec)
        if (root / "meta" / "info.json").is_file():
            dataset = LeRobotDataset.resume(repo_id, root=root, rgb_encoder=encoder)
            sanity_check_dataset_robot_compatibility(
                dataset, self.follower, self.fps, self.features()
            )
        else:
            dataset = LeRobotDataset.create(
                repo_id,
                fps=self.fps,
                features=self.features(),
                root=root,
                robot_type=self.follower.name,
                use_videos=True,
                image_writer_threads=4 * len(self.cfg.cameras),
                rgb_encoder=encoder,
            )
        return RealDataset(dataset)

    def load_policy(self, path: Path) -> RealPolicy:
        return RealPolicy(path, self.features())

    def drive(self, policy: RealPolicy, events: dict, task: str) -> None:
        policy.reset()
        interval = 1 / self.fps
        while not events["exit_early"]:
            start = time.perf_counter()
            action = policy.act(self.follower.get_observation(), task, self.follower.name)
            self.follower.send_action(action)
            precise_sleep(max(0.0, interval - (time.perf_counter() - start)))
        events["exit_early"] = False
