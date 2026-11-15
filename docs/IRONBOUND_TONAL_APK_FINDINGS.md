# IRONBOUND Tonal APK evaluation

Evaluated November 15, 2026. IRONBOUND remains an independent Android application with its own campaign, progression, movement demonstrations, and workout interface.

The full product scope is all training modes supported by this original Tonal. See [the complete mode evaluation](IRONBOUND_TONAL_MODES.md) and [identifier catalog](IRONBOUND_TONAL_MODE_CATALOG.json). The backed-up software provides strong evidence for local workout telemetry and configurable resistance profiles. It does **not** establish that an independently signed app can safely control this particular machine. The recommended first integration is a telemetry observer, followed by separately validated motor control.

## Evidence and limits

All eight files in `backups/tonal-apks-2026-11-15/` passed their recorded SHA-256 checks. The principal inspected applications were:

| Package | Backed-up version | Role |
| --- | --- | --- |
| `com.riptlabs.mcb.service` | `4.16.2-hercules-release` | Local motor-control service, Binder interface, native transport |
| `com.tonal.apps.machineclient2.beta` | `26.44.0-431-150839-RC-trainer-hercules-release` | Actual workout client, telemetry parsing, resistance commands |
| `com.tonal.fieldservice` | `1.7.14-hercules-release` | Additional motor/profile consumers and diagnostic tests |

The backup also contains Reverb, firmware client, launcher, APK updater, and OS updater. Their presence and hashes were checked; they were not exhaustively decompiled in this evaluation.

Live ADB verification corrected the initial connection check: Tonal Freedom uses a separate server on port **5038**, while the default server on 5037 had no devices. The existing wireless connection reports model `Trainer`, device `Hercules`, Android **6.0 / API 23**, and `arm64-v8a,armeabi-v7a,armeabi` ABIs. `su -c id` confirms root. Package-manager output confirms that the active MCB and trainer versions match the versions listed above (older system-image copies also exist).

`dumpsys activity services com.riptlabs.mcb.service` confirms that the MCB service is running in the foreground as UID 1000 and the stock trainer is bound to it. This verifies the running Android service and client relationship, not communication with the motor board or receipt of sensor samples. A read-only logcat snapshot did not expose useful motor samples or firmware identification.

Installed motor firmware, exact board revision, active in-memory feature flags, event cadence, and independent-client access remain unverified. Persisted Classic mode flags were subsequently read; all 22 listed states/modes are enabled in that cache, as detailed in the full mode evaluation. Shared APK classes are not a hardware inventory. In particular, multi-motor and newer resistance-mode classes do not prove that this original Tonal supports those features.

[JADX](https://github.com/skylot/jadx) 1.5.6 produced local inspection output under `.tools/ironbound-analysis/`. Decompilation reported 101 errors for MCB, 528 for trainer, and 22 for field service. Findings below use recovered methods and manifests, with native strings as limited corroboration; generated Java is not buildable original source. Native firmware control loops were not reverse-engineered. APKs and decompiled output remain in already-ignored directories.

## Local connection and ownership

The exported service component is:

`com.riptlabs.mcb.service/com.riptlabs.common.mcb.RiptMcbService`

Its manifest declares no service-level permission. `onBind()` returns its Binder; the recovered listener-registration path has no caller-signature check. This is a credible route for an ordinary separately signed APK, pending an on-device binding test. Root may not be necessary for observation.

The Binder descriptor is `com.riptlabs.common.mcb.IRiptMcbService`. Relevant transaction IDs in this exact APK are:

| ID | Method | Meaning |
| --- | --- | --- |
| 2 | `getState` | Service connection state |
| 3 | `messageSend(String)` | JSON command submission; not a read operation |
| 4 / 7 | `addServiceListener` / `addServiceListenerWithName` | Register callback |
| 5 | `removeServiceListener` | Unregister callback |
| 9 / 10 | `reserveAccess` / `releaseAccess` | Exclusive ownership lease |

The listener descriptor is `com.riptlabs.common.mcb.IRiptMcbServiceListener`; callback 1 is `onStatusChanged(int)`, callback 2 is `onMessageRecv(String)`, both one-way. The trainer uses the named-listener transaction itself.

Listener registration is not completely passive: the service internally attempts message 4134 with `component_type: 9`, a device-information request. An observer can avoid resistance commands, but must disclose this registration side effect.

`reserveAccess()` checks the caller's signature against the service UID. A normal independently signed IRONBOUND app should expect that check to fail. `messageSend()` goes through `ExclusiveClientAccess.execute()`: it requires service readiness and rejects a caller that does not own an existing lease. With no owner, that Java gate permits submission, but this is **not** safe arbitration between two workout apps and does not prove native acceptance. Root access alone does not change an APK's signing identity.

Sources: `mcb/resources/AndroidManifest.xml`; `mcb/sources/com/riptlabs/common/mcb/{RiptMcbService,IRiptMcbService,IRiptMcbServiceListener,ExclusiveClientAccess}.java`; `trainer/sources/defpackage/{lad,zq9}.java`. Paths in this report are relative to `.tools/ironbound-analysis/` unless stated otherwise.

## Telemetry useful to IRONBOUND

The single-motor event `MotorSampleEvent` has message type **4132**. Its body includes these fields, serialized using snake_case by the trainer:

| Fields | IRONBOUND use | Qualification |
| --- | --- | --- |
| `rep_phase`, `rep_alg_phase`, `rep_count` | Pull/return cues and rep completion | Validate event timing and transitions before awarding XP |
| `position_cable_left_in`, `position_cable_right_in` | Cable travel and animation feedback | Cable position is not full-body pose or form assessment |
| `speed_cable_left_ips`, `speed_cable_right_ips`, `speed_motor_ips` | Actual tempo and direction | Verify sign convention and units with captured samples |
| `rep_range_of_motion_length_in`, `rep_range_of_motion_pct` | ROM progress and consistency | Confirm percent scale and movement-specific calibration |
| `rep_mean_concentric_speed_ips` | Rep-speed feedback | Device algorithm output, not a prescribed tempo |
| `base_weight_applied_lbs`, `ecc_weight_applied_lbs`, `total_weight_applied_lbs` | Applied-load display, eccentric confirmation | Reported values are not independent force measurements |
| `motor_tension_lbs`, `spotted_weight_applied_lbs`, `ramp_weight_applied_lbs` | Explain load changes during a rep | Do not assume simple addition equals total in every mode |
| `control_mode`, `is_racked`, `is_grounded`, `is_cart_unlocked` | Workout availability and interruption state | Must be combined with connection freshness and error events |

Phase constants are unknown=0, concentric=1, eccentric=2, waiting=3, mid-rep isometric=4. Rep-state constants use a different enumeration (concentric=3, eccentric=4); do not confuse the two.

The message envelope supports MCB/service timestamps, including `timestamp-mcb`, `timestamp-ms`, and `timestamp-service` aliases. The trainer also records local monotonic arrival time and handles duplicate MCB timestamps. Measure sample cadence, gaps, resets, and clock relationships on the actual device rather than assuming a particular refresh rate.

Other defined messages include device information (4130), mass profile (4131), arm position (4133), thermal samples (4120), legacy error conditions (4137), feature state (4140), electrical samples (4143), and accessory buttons (8195). They are candidates for observation, not a guarantee of continuous publication. Multi-motor samples (4116) exist in the shared protocol but must not be presumed available on the original machine.

Sources: `mcb/sources/com/tonal/mcb/data/{MotorSampleEvent,MultiMotorSampleEvent,Message,DeviceInfoEvent,FeatureControlEvent}.java` and neighboring event classes; `trainer/sources/defpackage/y3.java`.

## Eccentric resistance

This is more than UI text: `MassProfileSet` (message type **19**) contains `baseWeightLbs`, `eccWeightLbs`, `romWeightLbs`, `romWeightMode`, `controlMode`, and spotter settings. The trainer's recovered command builder sends `getEccWeight()` into `setEccWeightLbs()` for normal modes; it has a separate isokinetic special case. Native `libmcb-service.so` also contains the wire names `ecc_weight_lbs` and `ecc_weight_applied_lbs`.

Profile feedback (4131) includes requested/profile eccentric load, and motor samples (4132) separately expose applied eccentric load. This gives a practical way to distinguish a setting from resistance actually reported during the return phase.

The trainer represents eccentric load as an additional component alongside base load in its weight-profile calculations. One recovered eccentric-setting path defaults to 0.25 of base load and clamps that fraction to 0.6. These are application-path constants, **not** a verified default for every workout, a firmware capability limit, or a safe prescription for IRONBOUND. Do not reuse them as hardware limits.

The protocol also defines flat-with-eccentric and several ROM-dependent profiles. Eccentric resistance and tempo are separate: a slower return cue does not itself change motor resistance. IRONBOUND can implement tempo guidance immediately without claiming that it has enabled eccentric overload.

The service has runtime control-mode flags through `LDIntegration`; its persisted Classic cache enables all 22 entries, but active-memory values and firmware behavior remain unverified. The exact eccentric behavior, applicable profile, load scaling (including one-arm/two-arm presentation), saturation, and failure behavior require observation on this hardware. No motor commands were sent in this evaluation.

Sources: `mcb/sources/com/tonal/mcb/data/{MassProfileSet,MassProfileEvent,MotorSampleEvent}.java`; `trainer/sources/defpackage/iad.java:31`, `i51.java:86`, `tqi.java:84`; `mcb/sources/com/riptlabs/common/mcb/debugfw/LDIntegration.java:251`.

## Independent Android architecture

Keep campaign state, character progression, workout prescriptions, original movement-demo assets, and local history entirely inside IRONBOUND. Put Tonal-specific observation behind a small adapter that emits normalized samples, connection state, and explicit capabilities. Provide a simulated adapter for development. Do not bundle a modified trainer APK or depend on its screens or account flows.

For the workout screen, distinguish the prescribed tempo animation from measured cable motion. Phase transitions can drive pull/return feedback; timestamp differences can score tempo; completed reps can advance the campaign. Unknown or stale telemetry must stop measured feedback and XP awards instead of fabricating progress. Reconcile rep counters across reconnects and set resets.

This preserves an independent app while initially reusing the installed hardware service. It does not yet provide independence from Tonal's service or firmware. A later control adapter needs a demonstrated ownership arrangement, acknowledgments/readback, known load limits, and tested stop/disconnect handling. Do not let campaign rewards automatically raise resistance.

The service itself contains Sentry initialization and Firehose logging integration; Sentry events attach the tablet serial as user ID. A local Binder integration does not establish that the machine is offline or that vendor telemetry stops. IRONBOUND can keep its own records local, but service network behavior needs a separate runtime check if full offline operation is a requirement.

## Next hardware validation

1. Use the existing ADB server on port 5038. Android API/ABI and active APK versions are now verified; live APK hashes and board/firmware information remain to be recorded. Retain serial identifiers locally and redact shared captures.
2. Install a separately signed observation-only probe. Bind explicitly, read state, register the named listener, timestamp events locally, then unregister cleanly. Account for the service's device-information request during registration. Do not submit resistance, rack, firmware, or diagnostic-test commands.
3. Capture a short normal workout controlled by the stock app. Verify rep phases, cable directions, sample gaps, rep resets, and load units. Observe idle and disconnected states too.
4. With the stock app controlling its existing eccentric feature, compare profile feedback and applied-load samples between pull and return. This tests the actual firmware without inventing control parameters.
5. Only then design IRONBOUND motor control around verified ownership and failure behavior. A failed lease is a failed capability check, not a reason to race the stock app or bypass its safety state.

Completion criteria for this evaluation: APK integrity verified; local service and telemetry contract identified; eccentric command and feedback paths found; independent-app boundary and unresolved hardware checks documented. No IRONBOUND APK was built or installed by this analysis.
