# Contributing

Three independent projects share this repo. Each has its own dependencies and CI workflow.

## robot

```sh
cd robot
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

To work on the TV screens without hardware, run the server with simulated arms and cameras (data
goes to `robot/.fake-data/`) and open <http://localhost:8000>. Arrow keys, Enter, and Escape act
like the TV remote.

```sh
cp config.example.toml config.toml
uv run robot serve --fake
```

`src/robot/hardware/real.py` is the only module that imports LeRobot. Everything else works with
the `Backend` protocol in `hardware/__init__.py`, which `hardware/fake.py` also implements.

## trainer

The tests don't need LeRobot or a GPU:

```sh
cd trainer
uv sync --only-group dev
uv run --no-sync pytest
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
```

## Robot ↔ trainer protocol

The robot and trainer exchange files over ssh/rsync. The layout is documented in
`trainer/src/trainer/inbox.py`; the robot side is `robot/src/robot/training.py`. Change both
together.

## tv

Needs JDK 17+ and the Android SDK (set `sdk.dir` in `tv/local.properties`).

```sh
cd tv
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

### Releasing

Pushing a tag like `tv-v1.1` builds a signed APK and attaches it to a GitHub release. Every
release must use the same key, or the TV refuses to install the update over the old version.
Create the key once and keep a backup:

```sh
keytool -genkeypair -keystore robot-tv.jks -alias robot-tv -keyalg RSA -keysize 4096 -validity 10000
base64 -w0 robot-tv.jks    # value for TV_KEYSTORE_BASE64
```

Add these repository secrets: `TV_KEYSTORE_BASE64`, `TV_KEYSTORE_PASSWORD`, `TV_KEY_ALIAS`, and
`TV_KEY_PASSWORD`.
