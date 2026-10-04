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

### Signing and releases

Every push to `main` that changes `tv/` builds an APK signed with the repository's key and attaches
it to the workflow run. Pushing a tag like `tv-v1.1` also publishes it as a GitHub release. Builds
signed with the same key install over each other, so create the key once and keep a backup:

```sh
keytool -genkeypair -keystore robot-tv.jks -alias robot-tv -keyalg RSA -keysize 4096 \
  -validity 10000 -dname "CN=Robot Arm"
base64 -w0 robot-tv.jks    # value for TV_KEYSTORE_BASE64
```

Add these repository secrets: `TV_KEYSTORE_BASE64`, `TV_KEYSTORE_PASSWORD`, and `TV_KEY_ALIAS`
(`robot-tv`). If the key or its password is lost, create a new one, update the secrets, and run
`adb uninstall robot.tv` before installing the next build.
