# IRONBOUND product specification

Version 0.1 — November 15, 2026. Initial implementation specification; hardware and training-engine validation remain in progress.

## Product objective

Make structured strength training on an original Tonal feel like advancing through an RPG. IRONBOUND owns its Android package, UI, workout definitions, campaign, character and training history. The installed Tonal motor service may provide the hardware interface; IRONBOUND is not a modified trainer APK.

The user selects a quest workout or standalone routine. The app chooses the prescribed working weight and compatible modes for each set, applies them through a validated adapter and confirms the resulting state before declaring readiness. The user retains accessible weight reduction, permitted adjustments and stop controls.

## Confirmed product requirements

| ID | Requirement | Acceptance condition |
| --- | --- | --- |
| P01 | Four-week chapters and 4–5-day schedules | Chapter contains core sessions and optional supplemental sessions; missed days reschedule without lost progress |
| P02 | Campaign map, XP, levels and accolades | Completed objectives advance the map and award persistent rewards exactly once |
| P03 | Automatic weight and mode selection | Each set has a stored prescription; hardware feedback must confirm a verified configuration before readiness |
| P04 | Tonal-like calibration | Guided assessment establishes estimates; new exercises receive familiarization and individual confirmation |
| P05 | Animated movement demo, pull/return cues and tempo guide | Prescribed timing and observed movement remain distinguishable; unknown/stale input cannot fabricate reps |
| P06 | Standalone workouts | Core, HIIT and other routines can run outside quests and appear in total training history |
| P07 | Character customization and store | Preview, buy and equip cosmetic items with earned coins; inventory survives restart and restore |
| P08 | Accessible training metrics | In-app dashboards and documented CSV/JSON export expose prescribed settings and measured results |
| P09 | Easy addition of levels and content | New chapters using existing mechanisms arrive as validated versioned data, without new screen logic |
| P10 | Complete Tonal training-mode scope | Track individual capability evidence and combinations; expose only verified capabilities on the actual device |
| P11 | Independent Android application | Separate signing identity/package; no vendor assets/code bundled as the app's implementation |
| P12 | No Tonal subscription prerequisite | Calibration, prescriptions and IRONBOUND content do not require paid stock workouts or a Tonal account entitlement; validate end-to-end operation on the user's unsubscribed device |

## Proposed first-release defaults

Single local player profile, four core sessions plus an optional fifth, earned-only currency, cosmetic-only equipment, local-first storage, no required account. The suggested enchanted-forge art direction is a proposal, not yet approved. Android UI/animation technologies and the exact exercise library remain to be selected after device benchmarks.

The first chapter and standalone routines require reviewed programming; the illustrative upper/lower split from discussion is a starting concept, not a finalized prescription. Exact rep ranges, load changes and training limits belong in the training-engine specification.

## Main flows

The user has no active Tonal subscription. Stock guided workouts and stock calibration are unavailable as required setup or validation steps. IRONBOUND supplies original workout content and its own assessment flow; feasibility of independent motor control is still a release gate.

### First launch and calibration

1. Create a local profile and character; choose preferred schedule, units and experience level.
2. Explain attachments, arm setup, session controls and how calibration estimates will be used.
3. Detect the hardware service and show capability/connection state. A simulation environment must be explicitly marked and cannot issue hardware commands.
4. Run a separately validated assessment using representative patterns. Reusing a Tonal calibration mode requires understanding its full protocol; enum presence is insufficient.
5. Store estimates with their provenance and confidence. Confirm the working weight during familiarization when an exercise first appears.
6. Offer recalibration, easier/harder feedback and manual corrections without overwriting the historical record.

No claim that a few assessment movements precisely calibrate all exercises. Changes in attachment, side, stance and mode must be considered when transferring estimates.

### Campaign workout

Home shows the next scheduled session and recent training. Selecting a map encounter opens duration, equipment, target movements and relevant recent workload. Setup screens show the attachment, arm positions and movement demo before each transition.

The set lifecycle is preparing → prescribing → applying → confirming → ready → active → completed → rest. Interrupted and disconnected are explicit states available from the appropriate stages. Configuration mismatch, stale data or service loss prevents a ready indication. Acknowledged transport submission alone does not prove applied load.

During a set, show exercise, reps/time, prescribed and reported weight, active modes, demo, phase and tempo. Keep controls large enough for exercising distance and never rely solely on color. RPG reactions remain secondary to training feedback. Rest screens host larger battle events, story and rewards.

After the workout, save a summary, award eligible rewards once, update exercise history and advance only the relevant chapter objective. Interrupted sessions retain completed work; resume must reconcile hardware and session state instead of continuing a stale prescription.

### Standalone workouts

Library filters include duration, muscle group, workout type, intensity and equipment. Standalone sessions use the same calibration, prescriptions, modes and measurement pipeline as quest sessions. They contribute to overall workload, history, XP and coins, but do not automatically complete required story encounters.

HIIT supports timed intervals and rep targets, with explicit attachment/arm transition time. Equipment setup is not counted as failed exercise time. Off-Tonal exercises use clearly identified timer/manual completion rather than fabricated motor telemetry.

Recent standalone work informs the next quest recommendation. Exact fatigue rules and schedule adjustments remain a training-engine decision; users should see the reason for a proposed change.

### Character, rewards and store

Initial appearance is customizable. Equipment slots support themed outfits, headwear/hair, weapons, accessories and effects using compatible asset templates. Preview an item before purchase and retain owned items permanently.

Earn coins/XP for prescribed workout completion, milestones and appropriate objectives. Avoid incentives for excessive extra volume or maximum loads. Using Spotter, reducing weight or resting does not impose a character penalty. Character levels unlock story/cosmetics/options, never directly determine motor resistance.

Use an auditable, transactional currency/reward ledger with stable reward identifiers. Retrying a completion event cannot duplicate coins; buying an item cannot spend coins without granting ownership. No real-money economy is planned for the first release.

### Dashboards and data access

Show consistency, session history, exercise trends, completed workload, tempo/ROM measures where valid, and campaign progression. Allow Quest / Standalone / All filters and drill-down from session to set and rep.

Persist planned prescriptions, configuration confirmations, observed values, manual changes, assistance, effort feedback, completion state and data-quality indicators. Include timestamps, units, device/app/content versions and exercise/mode identity. Represent missing measurements as unavailable, not zero.

Definitions of volume, personal records and comparable exercise histories must account for modes and unilateral/bilateral scaling. Do not compare an assisted or ROM-varying set directly to ordinary resistance without labeling the distinction.

Keep durable summaries locally, bounded raw telemetry retention, documented versioned CSV/JSON exports, and backup/restore. Store personal training data privately; exporting is an explicit user action. Optional future sync must preserve local operation and handle deduplication/conflicts. No open unauthenticated network endpoint is required for first release.

## Content contracts

Separate shared exercise definitions, workout prescriptions, four-week chapters, encounters, character/item definitions and media manifests. Use stable IDs, schema/content versions and explicit references. Each exercise defines setup, demonstration assets, calibration mapping, supported modes and progression family. Chapter files select workouts and progression/reward rules rather than implementing motor behavior.

Validate missing assets/references, invalid durations, duplicate reward IDs, impossible dependencies and incompatible mode combinations before activating a pack. Pin active sessions to their content version. New motor behaviors require application changes and validation even if new chapters do not.

## Hardware boundary

The hardware adapter reports connection, raw/normalized samples, quality, capabilities, requested/applied state and failures. Keep command access separate from observation. Production control requires verified ownership and stop/disconnect semantics; a normal app cannot assume the vendor signature-gated reservation is available.

All mode families are in scope: standard, Eccentric, Chains, Smart Flex, Spotter, Burnout, Drop Sets, plus other supported training/assessment modes established by validation. Engineering modes, low-level loops and firmware utilities do not become workout presets. Unknown telemetry IDs remain unknown.

## Release acceptance scenarios

- Fresh profile completes onboarding and receives appropriately labeled weight estimates.
- A verified workout applies and confirms its prescription without manual entry for every set.
- A rejected configuration or stale telemetry prevents readiness and measured-progress awards.
- Disconnect/restart retains completed work and never automatically re-enables a stale load.
- Duplicate rep/completion events do not duplicate progression, history or coins.
- Standalone sessions appear in overall workload while required chapter stages remain correct.
- Purchase/equip/restart/restore retains a consistent balance and inventory.
- Exported records reproduce dashboard summaries under the documented metric definitions.
- A second test chapter can be added through a content pack using existing features.
- The workout screen and asset sample run acceptably on the original device; performance thresholds are set by the technical benchmark.

## Decisions still to resolve

Production Android/rendering stack; exact calibration and progression rules; reviewed exercise and first-chapter selection; verified mode-combination matrix; metric definitions; raw-data retention and export delivery UX; asset pipeline and redistribution rights; final visual direction; optional future sync destination.

These decisions do not block a passive hardware probe or simulated UI prototype. They do block claiming production-ready automatic training.
