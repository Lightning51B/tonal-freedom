# IRONBOUND implementation plan

Status: active. Updated November 15, 2026.

IRONBOUND is an independent Android strength-training RPG for the user's rooted original Tonal. Workouts automatically prescribe weights and compatible training modes. Four-week campaigns, standalone workouts, character customization, earned coins, a cosmetic store, and accessible training metrics form one product.

## Subscription constraint

The user has no active Tonal subscription and cannot run stock guided workouts. A paid subscription, stock workout playback, and stock calibration are not prerequisites for this project. IRONBOUND must provide its own workout content, calibration flow and progression. Local telemetry already works in the reported unsubscribed setup; independent motor control remains to be established. Validation proceeds through APK/native-interface analysis, simulation/replay, service lifecycle checks and eventually supervised independent control.

## Work sequence

| Phase | Deliverables | Exit criteria | Status |
| --- | --- | --- | --- |
| 1. Product specification | Flows, scope, requirements, acceptance criteria, open decisions | Core behavior is concrete enough to implement and review | Initial specification written; review pending |
| 2. Tonal hardware validation | Separate diagnostic APK, device evidence, capability matrix, control ownership investigation | Observation validated; each control capability individually tested before release | Independent observation validated; control and loaded modes pending |
| 3. Training engine specification | Calibration, initial estimates, exercise-specific progression, effort feedback, mode compatibility | Reviewable rules and sample prescriptions; no guessed hardware limits | Pending |
| 4. Content contract | Versioned exercise/workout/chapter/item schemas and sample pack | A second chapter can be added without application changes | Pending |
| 5. UX and asset prototype | Core screen flows, one character, three outfits, enemy, map, reviewed demo | Readable on the Tonal; asset consistency and performance demonstrated | Pending |
| 6. Data contracts | Local schema, metric definitions, export/backup formats and dashboard mockups | Prescribed versus measured data preserved and exportable | Pending |
| 7. Technical foundation | Android UI/rendering/storage/media decisions and device benchmark | Chosen runtime operates reliably on Android 6/API 23 | Diagnostic proof only; production stack pending |
| 8. Implementation backlog | Milestones with dependencies and acceptance checks | Ordered work ready for production code generation | Pending |

Phases 1 and 2 begin now. Small diagnostic prototypes are part of validation; they are not the production workout controller. Product/UI work may use simulated data while hardware control is unresolved.

## First release boundary

- One four-week chapter with four core workout days and one optional session per week.
- Calibration/familiarization, per-exercise working weights, and automatic prescriptions.
- Standalone core, HIIT and recovery routines using the same exercise engine.
- One customizable character template, starter cosmetics, coins, inventory and store.
- Local training and RPG history, basic dashboards, CSV/JSON export and backup/restore.
- A hardware adapter designed for the complete mode catalog. Only independently validated hardware functions become available for use; all supported Tonal training modes remain the overall scope.

Cloud accounts/sync, social features, real-money purchases, a large cinematic library and additional chapters are later extensions. No subscription or online connection is required for IRONBOUND's own campaign logic and saved data; actual vendor-service offline behavior must be measured before promising end-to-end offline workouts.

## First complete implementation milestone

Create character → complete calibration/familiarization → start a prescribed workout → apply and confirm a verified hardware configuration → complete a set with measured feedback → save session → receive coins and XP once → equip an earned item → inspect dashboard and export session.

Acceptance requires safe handling of interruption, reconnect and duplicate events. Restarting the app must not duplicate rewards or treat a partially completed workout as complete.

## Validation boundaries

Start with device inspection and an observation-only probe. It may bind to the existing service, read service state, register a telemetry listener, unregister and unbind. Registration itself makes the vendor service request device information. It must not send resistance/rack/firmware commands, reserve control, alter flags or run factory tests.

Physical control validation is a separate supervised step with the user at the machine. First establish firmware identity, confirmed load scaling, operating limits, ownership and stop behavior. Do not run a sweep of unknown modes. Calibration/engineering entries in the inventory are not automatically workout options.

## Working documents

- [Product specification](IRONBOUND_PRODUCT_SPEC.md)
- [Hardware validation](IRONBOUND_HARDWARE_VALIDATION.md)
- [APK investigation](IRONBOUND_TONAL_APK_FINDINGS.md)
- [Full mode evaluation](IRONBOUND_TONAL_MODES.md)
- [Extracted mode identifiers](IRONBOUND_TONAL_MODE_CATALOG.json)

Update statuses and evidence as work progresses. Proposed defaults are not confirmed user decisions; measured capability is separate from software definitions and cached flags.
