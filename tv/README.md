# TV app

Google TV app that shows the robot's web UI full screen. Use the remote's arrows, OK, and Back.

## Install

1. Download `robot-tv.apk` from the repository's **Latest build** release (Releases → `latest`),
   which is rebuilt on every push to `main`.
2. On the TV, turn on developer options: Settings → System → About → press **Android TV OS build**
   7 times. Then, in Settings → System → Developer options, turn on **Wireless debugging** (on
   older TVs: **USB debugging**).
3. From a computer with `adb` ([Android platform tools](https://developer.android.com/tools/releases/platform-tools)):

   ```sh
   adb pair <tv-ip>:<pairing-port>     # Wireless debugging only: use "Pair device with pairing code"
   adb connect <tv-ip>:<port>          # port shown under Wireless debugging; 5555 with USB debugging
   adb install -r robot-tv.apk
   ```
4. Open **Robot Arm** from the TV's apps and enter the robot's address, e.g. `192.168.1.50:8000`.
   Hold **Back** to change it later.

Install newer versions the same way; `-r` keeps the saved address.
