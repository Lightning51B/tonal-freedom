# IRONBOUND hardware validation

November 15, 2026, America/New_York. Phase 2 is in progress. Observation is validated on the original Tonal; independent motor control and loaded workouts are not validated.

## Subscription constraint

The user confirmed no paid Tonal subscription and cannot perform the proposed stock-app workouts. That earlier prerequisite is removed. The successful observation capture remains valid; it demonstrates local telemetry in the user-reported unsubscribed setup, not an entitlement check or validated independent load control. No subscription purchase is needed to continue investigation.

## Results

An independently signed diagnostic APK (`app.ironbound.probe`, UID 10061) bound to the existing motor service, registered a named callback, received motor telemetry and device information, then unregistered and unbound. It requested no Android permissions, used no root, and did not replace the stock trainer screen. Root was used separately for read-only host diagnostics and installed-APK hashing.

The probe implements only Binder transactions 2, 7 and 5. It cannot submit resistance/rack/firmware commands, reserve control, or change feature flags. Vendor listener registration attempts a device-information request internally.

| Check | Result | Evidence / scope |
| --- | --- | --- |
| ADB | Connected through dedicated server port 5038 | Existing wireless transport; no server/key changes |
| Android | Trainer / Hercules, Android 6.0, API 23 | Device properties |
| ABI | arm64-v8a, armeabi-v7a, armeabi | Device properties |
| Root | Available | `su -c id`; not required by probe |
| Active MCB app | 4.16.2-hercules-release | Package manager and device-side hash |
| Active trainer | 26.44.0-431-150839-RC-trainer-hercules-release | Package manager and device-side hash |
| Independent binding | Passed | Separate package/signature/UID; stock trainer remained bound |
| Listener callbacks | Passed | 266 messages in active capture |
| Motor sample stream | Passed while idle/racked | 250 type-4132 samples over approximately five seconds |
| Callback arrival interval | Median 20 ms, maximum 25 ms in active capture | Approximately 50 Hz; not an across-mode guarantee |
| Device information | Received | Seven type-4130 messages; serials excluded from committed summary |
| Profile feedback | Received | One type-4131 message; mode 10, base 5 lb, modifiers zero |
| Listener cleanup | Passed in both captures | Unregistered, unbound and capture-finished markers; service stopped |
| Independent motor control | Not tested | Signature-gated ownership remains unresolved |
| Physical calibration / mode behavior | Not tested | No loaded movement or mode commands issued |

Installed hashes match the backed-up APKs exactly:

- MCB: `294be601111520c3086c55303fe8a8f1d8f3606512279edb1078c68a4ae6ccc3`
- Trainer: `99f50bd5f83ac0a43326312fcdd335a801afaea1d37dda2f5796c43fc3137075`

Hashes were calculated on device with Magisk's BusyBox after the stock shell lacked `sha256sum`. A redundant trainer APK transfer was stopped once its device-side hash was obtained; any partial download under `.tools/` is not evidence.

## Wake and readiness behavior

The first capture requested 20 seconds and lasted 28.072 seconds. It read service state 0, received two transport-statistics messages (4147) with zero transmitted/received bytes, and received no motor samples or device information. A contemporaneous USB inspection found only host root hubs and no ttyACM nodes. The user initially reported an apparently normal idle trainer.

The user subsequently confirmed waking the machine and opening the stock app. The next capture read state 1, lasted 5.040 seconds, and received the active stream described above. Power/activity inspection showed the display on and the stock trainer ShellActivity resumed. Kernel history contained USB VBUS errors and later ttyACM0 enumeration, but this does not by itself establish a physical fault or the cause of recovery.

This sequence shows that an ADB-connected, running Android service is not sufficient evidence of motor readiness. Waking/opening the stock app preceded the successful run. We have not isolated whether display wake, app initialization, USB recovery, or their combination was necessary. IRONBOUND must explicitly wait for fresh board telemetry and handle unavailable service state, rather than assuming readiness after a successful bind.

Committed sanitized summaries:

- [First capture, unavailable motor link](evidence/ironbound-probe-2026-11-15.json)
- [Active idle/racked capture](evidence/ironbound-probe-2026-11-15-active.json)

Raw captures, device logs and private identifiers remain under ignored `.tools/`. The active capture filename uses UTC November 16; its local date was November 15.

## Observed component information

Component identifiers are interpreted using the APK protocol's component constants, not device serial numbers.

| Identifier | Component | Firmware | Hardware revision | Part number |
| --- | --- | --- | --- | --- |
| 1 | MCB | 5.2.18.0 | 001 | 500-0102 |
| 2 | Bobble | 2.18.0.0 | 001 | 500-1200 |
| 3 | Left canoe | 3.7.2.0 | 003 | 500-0200 |
| 4 | Right canoe | 3.7.2.0 | 003 | 500-0200 |
| 6 | Bar | 3.7.2.0 | 002 | 500-1100 |
| 5 | Handle report A | 3.7.2.0 | 003 | 500-0300 |
| 5 | Handle report B | 0.0.0.0 | 003 | 500-0300 |

The second handle's zero version is retained as observed, not interpreted as a validated firmware version or diagnosed fault. Accessory state needs a separate check.

## Idle telemetry interpretation

All 250 motor samples reported `is_racked=true`, `is_grounded=true`, rep count/phase 0, and zero left/right cable position. Mode 10 was reported, with base/total applied fields of 5 lb and zero eccentric load. The profile likewise reported base 5 lb, ROM mode 0 with zero ROM load, and Spotter off.

These are **idle/racked reported values**, not evidence that a user experienced a 5 lb load or that the probe commanded one. ROM mode 0 with zero ROM weight does not demonstrate active Chains behavior. No rep transitions, physical units/scaling, overload, speed control or assistance triggers were exercised.

## Capability gates

| Capability | Current evidence | Next gate |
| --- | --- | --- |
| Local observation without root | Verified on device | Longer captures, reconnect lifecycle and rate behavior |
| Standard weight | Idle mode/profile observed | Resolve independent control first, then supervised movement capture; verify units and transitions |
| Eccentric / Chains / Smart Flex | APK command/feedback definitions; cached allowed base mode | Trace parameters and simulate first; independently validate each profile after control gate |
| Spotter / Burnout / Drop Set | APK paths and schema discrepancy documented | Resolve schema from code and traces; validate assistance independently after control gate |
| Isokinetic / Flywheel / Pilates / Isometric | APK paths, cached policy entries | Establish firmware support and parameters without relying on paid stock UI |
| Assessment and calibration | Modes 11 and 16 defined | Recover/validate complete procedure and training rules |
| Independent prescription application | Not tested | Resolve ownership, confirmed bounds, configuration feedback and stop contract |
| Independent operation without stock UI | Not tested | Controlled wake/reconnect tests; determine service initialization dependency |

The catalog's `hardware_verified=false` values remain appropriate: observing an idle mode is not validating loaded behavior or independent control.

## Revised validation sequence without a subscription

1. Continue local analysis of command construction, native transport, profile feedback, limits and stop/rack paths. Do not treat a successful send or an enabled flag as proof of accepted configuration or safety behavior.
2. Exercise parsing, phase detection, workout state transitions, duplicate suppression and reconnect handling with recorded idle data and clearly labeled synthetic movement fixtures. Synthetic tests do not validate physical mechanics.
3. With no active load, establish wake/reconnect behavior and whether the installed motor service can initialize without the stock trainer UI. The earlier wake-and-open observation did not isolate that dependency.
4. Resolve ownership for a separately signed application. Compare a normal local client with a narrowly scoped privileged bridge if necessary; choose only after the actual service constraints are established. A root process does not automatically inherit the vendor signing identity, and unowned command submission is not adequate arbitration. Do not race two controllers or disable the ownership check as a shortcut.
5. Establish a concrete stop/rack contract, load units, firmware bounds and a supervised test procedure before implementing a restricted control harness. Keep command capability out of the observation-only probe.
6. With the user present and ready, validate the smallest supported independent control case, configuration readback, stop and interruption behavior. Then validate standard reps and mode families incrementally. No generic guessed load or sweep of mode IDs is prescribed here.
7. Implement IRONBOUND's original calibration and exercise-familiarization flow using validated controls. Do not require completing Tonal's paid assessment or claim its proprietary algorithm has been reproduced.

A free manual/custom mode, if actually available on this device, may provide optional comparison data; its existence is not assumed and it is not a dependency. Full physical mode verification still requires supervised interaction, but it does not require paid stock workouts. Content, UI, progression and dashboards can proceed with the simulated adapter while the control gate is open.

## Verification performed

The probe built against Android SDK 34 with min/target API 23, passed APK signature verification including v1, installed and ran on the physical device. Three focused summary tests cover distinguishing transport from motor samples, preserving unknown message IDs without leaking payloads, and calculating observed arrival intervals. Both captures completed cleanup. No firmware, service package, feature flag, resistance setting or stock-app code was modified.
