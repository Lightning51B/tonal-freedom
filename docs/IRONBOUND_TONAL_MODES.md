# IRONBOUND full Tonal mode evaluation

Scope: all training modes supported by the user's original Tonal, with IRONBOUND remaining an independent Android app. Evaluated November 15, 2026 using the backed-up MCB 4.16.2 and trainer 26.44.0 APKs and read-only ADB access through server port 5038.

## Device evidence

The device's persisted LaunchDarkly cache contains `ControlModesAllowedClassic`, flagVersion 5, version 387, with all **22** defined motor states/modes enabled. The recovered service selects this flag for Classic branches including T1_0 and T800. The cache also contains Tahoe flags; that does not identify this device as Tahoe.

This establishes cached policy, not active process memory, firmware acceptance, stock UI availability, or physical behavior. No flags or motor settings were changed. All hardware-validation statuses remain unverified. Root, Android 6/API 23, Hercules identity, active APK versions, and the stock trainer's binding to the MCB service were verified earlier.

The extracted [mode catalog](IRONBOUND_TONAL_MODE_CATALOG.json) contains 22 control states/modes, nine ROM profiles, and five spotter settings. These occupy separate namespaces. Counts were checked against the recovered definitions and the cached Classic entries.

## Training features

| Feature | Recovered interface | Validation needed |
| --- | --- | --- |
| Standard digital weight | Control mode 10 and base load | Load scaling, rack behavior, applied feedback |
| Eccentric | `ecc_weight_lbs` within a mass profile | Return-phase load and movement-specific behavior |
| Chains | ROM profile 0, `rom_weight_lbs` | Load curve and calibrated ROM |
| Smart Flex | Trainer identifies non-Chains ROM profiles as Flex; enum covers 1–5 | Movement-to-profile selection and curve |
| Spotter | `spotter_mode=2`, SingleRep | Trigger, reduction, next-rep restoration |
| Burnout | `spotter_mode=1` | Trigger and reduction retained across the set |
| Drop Set | Current command/trainer `spotter_mode=4`, speed threshold and reduction parameters | Reduction algorithm and set-end behavior |
| Drop Set research variant | `spotter_mode=3` | Separate variant; not ordinary Drop Set |
| Isokinetic | Control mode 14; speed parameters | Direction, force limits, speed behavior |
| Flywheel | Control mode 24; drag/type/mass/inertia parameters in schema | Firmware-supported parameters and physical response |
| Pilates spring resistance | Control mode 26; spring constant and maximum load | Spring behavior, accessory and movement requirements |
| Isometric trials | Control mode 27; high-resolution force event 4148 | Hold/release, force sampling, trial timing |
| Strength assessment | Modes 11 and 16, fit/strength and progressive calibration | Assessment-specific protocol and bounds |
| Assistance / Auto Weight Off | Separate feature controls, including timed-weight-off type 6 | Movement conditions, timing, accessory integration |

The trainer has actual command-building paths for isokinetic, flywheel, and Pilates, beyond enum declarations. The inspected builder sends outward speed for isokinetic, drag for flywheel, and spring constant/maximum for Pilates. The shared command schema includes additional fields that this builder does not necessarily populate. Their presence does not establish independent configurability on the original hardware.

Smart Flex is not one generic motor mode: it requires the movement's selected resistance curve and parameters. In the trainer, `RomWeightMode.isFlex()` identifies profiles other than Chains. Weight-state paths distinguish Flex from independent Chains and Eccentric adjustments. Several paths for flywheel, Pilates, isokinetic, and progressive assessment reset modifiers and/or turn Spotter off. IRONBOUND needs a compatibility matrix, not unrestricted stacking of every option.

A concrete protocol discrepancy must be resolved: `MotorSampleEvent` declares legacy `AUTOSPOTTER_DROPSET=3`, while `MassProfileSet` and trainer `SpotterMode` use research DropSet=3 and normal DropSet=4. Preserve raw feedback until validated; do not derive commands from legacy telemetry constants.

## ROM profiles and assistance

The command schema defines these ROM profiles:

| ID | Name |
| --- | --- |
| 0 | Chains |
| 1 | BellWithEcc |
| 2 | ReverseChainsWithEcc |
| 3 | ChainsWithEcc |
| 4 | FlatWithEcc |
| 5 | QuadraticAscendingWithEcc |
| 6 | Perturbation |
| 7 | ReverseChains |
| 8 | EccReduction |

The recovered trainer enum covers only 0–5. Profiles 6–8 remain command-schema definitions with unverified workout availability. Names do not establish exact firmware curves. Eccentric load can also be supplied as a distinct field; ROM profile names and eccentric settings must not be conflated.

Spotter settings are Off=0, Burnout=1, SingleRep=2, DropSetResearchStudy=3, DropSet=4 in the current command/trainer model.

## Complete motor inventory

All entries below are enabled in the device's cached Classic policy. That is not hardware certification.

| ID | APK name | Role or unresolved meaning |
| --- | --- | --- |
| 0 | OFF | Weight-off state |
| 1 | INIT | Initialization state |
| 2 | ERROR | Error state |
| 3 | FATAL | Fatal state |
| 10 | WEIGHT | Standard resistance and validated modifiers |
| 11 | STRENGTH_CAL / FIT_TEST | Assessment |
| 12 | LIFECYCLE_WEIGHT_LIFT | Engineering lifecycle test |
| 13 | LIFECYCLE_ANCHOR_PULL | Engineering lifecycle test |
| 14 | ISOKINETIC | Speed-controlled training candidate |
| 15 | SUSPENSION | Operational semantics unverified |
| 16 | PROGRESSIVE_STRENGTH_CAL | Progressive assessment |
| 17 | BALL_WHACK | Engineering/test definition |
| 18 | SPEED | Separate from isokinetic; semantics unverified |
| 19 | COGGING_MAP | Calibration/engineering definition |
| 20 | SELF_VERIFICATION | Diagnostic definition |
| 21 | WEIGHT_HOLD | Hold/release semantics unverified |
| 22 | HARDWARE_MODE | Low-level loop controls; message type 21 |
| 23 | CAM_MODE | Command-array interface; message type 22 |
| 24 | FLYWHEEL | Trainer path present |
| 25 | BOOST_WEIGHT | Semantics unverified |
| 26 | PILATES | Trainer path present |
| 27 | PT_ISOMETRIC | Trainer and force telemetry paths present |

Keep the full inventory in the capability model. Engineering modes are not campaign workout choices. `HardwareModeSet` exposes open/vector/torque-loop fields, while `CamModeSet` accepts command arrays; neither establishes a verified consumer workout interface.

Feature-control types also include bar bail (1), encoder correction (2), arm reseat (3), IMU stream (4), friction compensation (5), timed weight off (6), fan control (7), RSSI (9), cogging correction (10), resistance profile (11), plunger fix (12), and emergency-stop trigger (13). These are supporting controls, not additional resistance presets. An emergency-stop constant alone does not establish a tested stop contract.

## IRONBOUND integration requirements

Represent a workout with a base control mode, ROM profile, eccentric load, assistance setting, and validated parameters. Keep capability evidence separately: defined in APK, cached allowed, firmware identified, observed in stock workout, independently controlled and verified. Unknown IDs must remain unknown rather than silently becoming ordinary weight mode.

Use the existing telemetry interface across every mode family. For weight-based modes, observe profile 4131 and motor samples 4132: base, eccentric, ROM, spotted and total applied load, phase, count, ROM, and speed. For isometric trials also inspect force batches 4148. Preserve raw IDs and timestamps so a schema mismatch cannot masquerade as a valid mode change.

Campaign progression and workout feedback must suit the mode: rep/tempo/ROM for weight training, validated resistance behavior for flywheel/Pilates, and duration/force metrics for isometric trials. Keep prescribed demo animation separate from measured movement; cable telemetry is not full-body form tracking.

Hardware validation must cover each feature and its supported combinations. Observe stock-app operation first; record requested/profile values against applied feedback, transitions, termination, connection loss, and accessory weight-off behavior. Independently controlled modes additionally require verified exclusive ownership and stop behavior. No mode is marked working merely because its cached flag is true.

IRONBOUND retains its own APK, UI, assets, campaign state and storage. Reusing the installed MCB service is a local hardware integration, not a fork of the trainer. Full mode support remains the product scope; this evaluation does not claim it has been implemented or physically tested.

## Evidence locations

Paths below are relative to ignored `.tools/ironbound-analysis/`:

- `mcb/sources/com/riptlabs/common/mcb/debugfw/LDIntegration.java`: full motor enum, platform flag selection and enforcement logic.
- `mcb/sources/com/tonal/mcb/data/MassProfileSet.java`: command fields, ROM and assistance identifiers.
- `mcb/sources/com/tonal/mcb/data/MotorSampleEvent.java`: telemetry fields and legacy assistance identifiers.
- `mcb/sources/com/tonal/mcb/data/{FeatureControlSet,CamModeSet,HardwareModeSet,IsoHighResForceEvent}.java`: supplementary interfaces.
- `trainer/sources/com/tonal/insights/models/{ControlMode,RomWeightMode,SpotterMode}.java`: trainer interpretation.
- `trainer/sources/defpackage/{iad,tqi}.java`: command construction and mode-specific configuration paths.
- `trainer/resources/res/values/strings.xml`: user-facing feature descriptions, corroborating the mappings rather than proving availability.
- `live-mcb-flags.xml`: local read-only cache capture. Only mode-related policy values were copied into the catalog.

See [the original APK evaluation](IRONBOUND_TONAL_APK_FINDINGS.md) for hashes, decompilation limitations, local service access, ownership constraints and telemetry details.
