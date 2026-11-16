# IRONBOUND telemetry probe

Small independently signed Android 6/API 23 diagnostic. Runs as a background service without replacing the trainer screen. Not the production IRONBOUND app or workout controller.

The only vendor Binder transactions implemented are getState (2), named listener registration (7), and listener removal (5). There is no command-send, rack, reservation, root, network, firmware or feature-toggle API. Vendor listener registration itself attempts a device-information request. The manifest requests no permissions and no shared UID.

Captures stay in the app's private files directory. This debug-only APK permits `adb run-as` export. Raw records may include hardware serials; keep them in the ignored `.tools/` directory. `summarize.py` uses an allowlist for shareable evidence. Do not ship this exported debug service as the production application.

## Build and install

Requires Java 17 and Android SDK platform/build tools 34 by default. Override `ANDROID_SDK_ROOT`, `IRONBOUND_BUILD_TOOLS` and `IRONBOUND_ANDROID_JAR` if needed. The build has no Gradle or third-party package downloads.

From the repository root:

```sh
bash tools/ironbound-probe/build.sh
adb -P 5038 -s DEVICE_SERIAL install -r .tools/ironbound-probe-build/ironbound-probe.apk
python3 tools/ironbound-probe/capture.py --serial DEVICE_SERIAL --seconds 20
python3 -m unittest discover -s tools/ironbound-probe -p 'test_*.py'
```

Use the existing Tonal Freedom ADB server on port 5038. `adb -P 5038 devices -l` shows its devices. Do not restart the server or replace keys to use this probe.

Each capture records monotonic and epoch arrival timestamps, service state, JSON callback messages and cleanup markers. It requests a duration of 5–60 seconds, bounded to 8 MiB; Android scheduling or synchronous Binder delays can extend wall-clock duration. The capture helper checks for a completion marker and retains partial evidence if its deadline expires. The first idle/offline capture exceeded its requested 20 seconds; the active five-second capture completed in 5.04 seconds. This is not a real-time safety mechanism.

`capture.py` requires the APK to be installed. Do not run multiple captures concurrently. A repeated start while the service is already running is ignored, and the helper will report a missing completion rather than guessing which run belongs to it.

To re-summarize a private capture:

```sh
python3 tools/ironbound-probe/summarize.py PATH_TO_CAPTURE.jsonl --output PATH_TO_SUMMARY.json
```

To remove the diagnostic and its device-local captures after validation:

```sh
adb -P 5038 -s DEVICE_SERIAL uninstall app.ironbound.probe
```

The APK has been installed and left available for subsequent validation. Both initial captures stopped and unbound. No persistent receiver or restart behavior is installed.

## Interpretation

Binding and callbacks demonstrate observation access, not control ownership. Transport statistics are not rep telemetry. State 0 without motor samples is not sufficient to declare failed hardware; wake/app lifecycle can affect readiness. Normal active samples must be measured separately from idle/racked samples, and mode commands require a separate supervised validation process.

The summary's sample-gap metric measures local callback arrival, not calibrated sensor acquisition latency. Do not assume all devices or all operating modes run at the observed cadence. It combines motor message types if both are present; use per-stream analysis before evaluating dual-motor timing.
