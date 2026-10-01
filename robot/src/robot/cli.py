"""`robot serve | calibrate | find-cameras | find-pedal`."""

import argparse
import dataclasses
import logging
from pathlib import Path

from robot import config


def serve(cfg: config.Config, fake: bool) -> None:
    import uvicorn

    from robot.hardware import cameras, pedal
    from robot.library import Library
    from robot.modes.session import Session
    from robot.training import TrainerClient
    from robot.web.app import create_app

    if fake:
        from robot.hardware.fake import FakeBackend

        backend = FakeBackend(list(cfg.cameras))
    else:
        from robot.hardware.real import RealBackend

        for camera in cfg.cameras.values():
            cameras.apply_controls(camera)
        backend = RealBackend(cfg)

    session = Session(backend)
    session.connect()
    if not fake:
        pedal.listen(cfg.pedal, session.press)
    app = create_app(cfg, session, Library(cfg), TrainerClient(cfg.trainer))
    try:
        uvicorn.run(app, host=cfg.host, port=cfg.port)
    finally:
        session.shutdown()


def calibrate(cfg: config.Config, which: str) -> None:
    from robot.hardware import real

    device = real.make_leader(cfg) if which == "leader" else real.make_follower(cfg)
    real.calibrate(device)


def find_cameras() -> None:
    from robot.hardware import cameras

    found = cameras.find()
    if not found:
        print("No cameras found under /dev/v4l/by-path.")
    for path in found:
        print(path)


def find_pedal(device: str | None) -> None:
    import evdev

    from robot.hardware import pedal

    if device is None:
        print("Input devices (run again with a name, then press each pedal):")
        for name in pedal.find():
            print(f"  {name}")
        return
    matches = [evdev.InputDevice(p) for p in evdev.list_devices()]
    dev = next((d for d in matches if d.name == device), None)
    if dev is None:
        raise SystemExit(f"no input device named {device!r}")
    print("Press each pedal (Ctrl+C to quit):")
    for event in dev.read_loop():
        if event.type == evdev.ecodes.EV_KEY and event.value == 1:
            print(f"  {evdev.ecodes.KEY.get(event.code)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="robot")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="command", required=True)
    serve_cmd = sub.add_parser("serve", help="run the robot and the TV app's web server")
    serve_cmd.add_argument("--fake", action="store_true", help="simulate the arms and cameras")
    cal = sub.add_parser("calibrate", help="calibrate an arm")
    cal.add_argument("arm", choices=["leader", "follower"])
    sub.add_parser("find-cameras", help="list camera paths for config.toml")
    ped = sub.add_parser("find-pedal", help="list input devices, or show a device's keys")
    ped.add_argument("device", nargs="?")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if args.command == "find-cameras":
        find_cameras()
    elif args.command == "find-pedal":
        find_pedal(args.device)
    else:
        cfg = config.load(args.config)
        if args.command == "serve" and args.fake:
            # Keep simulated tasks out of the real data folder.
            cfg = dataclasses.replace(cfg, data=Path(".fake-data").resolve())
        if args.command == "serve":
            serve(cfg, args.fake)
        else:
            calibrate(cfg, args.arm)
