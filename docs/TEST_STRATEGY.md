# RaisedFloor.extension - Test Strategy and Roadmap

## Purpose

This document defines the target testing model for the plugin, the test layers,
the rollout sequence, and the acceptance criteria for each stage.

The goal is not only to increase coverage, but to make future refactoring safe
and to create a practical Revit-hosted smoke/integration test contour for
Revit 2024 and Revit 2026.

## Current State

### Automated non-Revit contour

- `pytest -m "not revit"` is configured and passing.
- Coverage gate is enabled in `pytest.ini`.
- Current non-Revit total coverage baseline is above 40%.
- Pure/non-Revit tests already cover significant parts of:
  - `floor_common`
  - `floor_exact`
  - `floor_grid`
  - `floor_i18n`
  - `floor_ui`
  - `floor_utils`

### Revit-hosted contour

- A pyRevit tests button is planned but not yet implemented.
- Future button behavior will be a lightweight mixed smoke/check script.
- Revit-specific tests are not yet organized into explicit suites by scope.
- There is no formal separation yet between:
  - smoke tests in the current document
  - smoke tests on a known test model
  - integration tests that modify model state

## Target Model

The final testing model should have three layers.

### Layer 1 - Non-Revit unit tests

Purpose:

- Fast feedback during development.
- Safe refactoring of logic-heavy modules.
- Maximum execution frequency.

Characteristics:

- Runs outside Revit.
- Primary command: `pytest tests/ -m "not revit"`.
- Covers pure logic, geometry helpers, formatting, parameter parsing, and logic
  that can be tested via lightweight stubs.

### Layer 2 - pyRevit smoke tests

Purpose:

- Validate that the plugin is alive inside real Revit.
- Catch broken imports, broken API assumptions, missing families, invalid view
  context, transaction failures, and version-specific regressions.

Characteristics:

- Runs inside a live Revit session via pyRevit button.
- Must finish quickly.
- Must produce a structured pass/fail report.
- Should be safe to run repeatedly.

### Layer 3 - Revit integration tests

Purpose:

- Validate end-to-end behavior on prepared project models.
- Confirm that the actual workflow works across supported Revit versions.

Characteristics:

- Runs inside Revit.
- Can modify document state.
- Uses either a dedicated test model or a dedicated disposable copy.
- Covers the full workflow pipeline.

## Version Matrix

Supported manual/hosted verification target:

- Revit 2024
- Revit 2026

Expected policy:

- Every smoke suite must be run on both versions before release.
- If API behavior differs, tests should report the Revit version explicitly.
- Version-specific branches are allowed only when documented.

## Scope By Layer

### Non-Revit unit scope

Must cover:

- Pure geometry helpers.
- Formatting and UI helper logic.
- Shift scoring helpers.
- Parameter parsing and serialization helpers.
- Deduplication, bbox, snapping, loop building, void decomposition.

Should not cover:

- Real transactions.
- Real document modifications.
- Family loading against the actual Revit document.

### pyRevit smoke scope

Must cover:

- Revit host availability.
- Active document presence.
- Project vs family document validation.
- Active view compatibility.
- Basic access to floor-related parameters.
- Basic access to plugin families.
- Transaction open/commit/rollback safety.
- Command precondition checks.

Should avoid:

- Heavy model mutations.
- Long-running geometry generation across many elements.
- Complex setup assumptions about the current user model.

### Revit integration scope

Must cover:

- Project parameters creation.
- Family parameters creation/update.
- Contour generation.
- Grid drawing.
- Shift search and application.
- Stringer placement.
- Support placement.
- Tile placement.
- Clear all / cleanup.

Should also cover:

- Failure/rollback scenarios.
- Missing family / wrong view / no level cases.
- Revit 2024 vs 2026 compatibility.

## Roadmap

### Phase 1 - Stabilize non-Revit contour

Status:

- In progress and already productive.

Goals:

- Reach stable high-value coverage on logic-heavy modules.
- Keep raising `--cov-fail-under` gradually.
- Build confidence for future refactoring.

Definition of done:

- Non-Revit suite is green by default.
- Coverage gate is meaningful and enforced.
- Critical logic modules have characterization tests.

### Phase 2 - Redesign pyRevit test button into a smoke runner

Goals:

- Turn the existing tests button into a structured Revit smoke runner.
- Separate checks into named scenarios.
- Make output actionable for both developers and testers.

Planned smoke groups:

1. Environment
   - Revit version
   - pyRevit availability
   - extension root detection
   - library imports
2. Document context
   - active document exists
   - project document required checks
   - active view suitability
   - level availability when required
3. Families and parameters
   - required families found or loadable
   - shared/project parameters accessible
   - key RF parameters readable
4. Transaction safety
   - start/commit empty transaction
   - rollback on forced failure
5. Lightweight command readiness
   - contour prerequisites
   - grid prerequisites
   - placement prerequisites

Definition of done:

- The button shows a clear grouped report.
- Failures point to a specific subsystem.
- The smoke runner is safe on any open test-ready project.

### Phase 3 - Introduce a dedicated Revit test model workflow

Goals:

- Standardize integration verification on a known model.
- Remove randomness caused by arbitrary user projects.

Artifacts to prepare:

- A dedicated test model per supported Revit baseline or a version-compatible set.
- Required RF families in known-good versions.
- Expected test zones:
  - rectangle
  - rectangle with opening/column
  - L-shape

Definition of done:

- A tester can open the model and run the smoke/integration flow reliably.
- The expected results are documented.

### Phase 4 - Add structured Revit integration suites

Goals:

- Move from smoke validation to scenario-based workflow verification.

Planned integration suites:

1. Parameters suite
   - project parameters creation
   - family parameters synchronization
2. Geometry preparation suite
   - floor selection
   - contour generation
   - grid generation
3. Layout suite
   - best shift search
   - offset writeback
4. Placement suite
   - stringers
   - supports
   - tiles
5. Cleanup suite
   - clear all removes generated elements

Definition of done:

- The main workflow is covered on a known model in both Revit versions.

### Phase 5 - Refit for automation on a Revit host machine

Goals:

- Make Revit-hosted execution repeatable beyond manual clicking.

Possible execution options:

- pyRevit button run in a prepared interactive session.
- journal-driven startup and scripted command execution.
- external Revit batch/test runner on a machine with installed Revit.

Definition of done:

- The hosted suite can be run with minimal operator work.
- Results are stored in a reproducible form.

## Test Data Strategy

### Required models

- One minimal project model for smoke tests.
- One prepared scenario model for integration tests.

### Required families

- RF_Tile
- RF_Stringer
- RF_Support

### Required scenario geometry

- rectangular zone without openings
- zone with one column/opening
- L-shaped zone

## Reporting Strategy

### Non-Revit

- pytest console output
- HTML coverage
- XML coverage

### pyRevit smoke

- grouped pass/fail summary
- Revit version in report
- active document name in report
- error list with subsystem labels
- report must not rely on one UI surface only
- preferred reporting sinks:
  - `pyRevit output`
  - `script.get_logger()`
  - temporary text log file when the flow is diagnostic or maintenance-heavy
- if a text log file is created, its path should be surfaced in the final summary

### Revit integration

- scenario name
- pass/fail
- created element counts where relevant
- rollback/cleanup status

## Quality Metrics

The test system must evaluate not only whether a command completed, but also
whether the produced result is acceptable from a geometry and layout quality
perspective.

### Why quality metrics matter

A command may technically succeed while still producing a weak result.

Examples:

- the layout is generated but contains too many non-viable cuts
- the grid is generated but badly aligned near openings
- placement completes but leaves gaps, duplicates, or unstable results
- cleanup finishes but leaves residual generated elements

For this reason, the test contour should distinguish:

- execution success
- data correctness
- quality of the produced outcome
- stability of repeated execution

### Metric groups

#### Build success metrics

Used to answer: did the command produce any usable result at all?

Examples:

- command completed without unhandled exception
- expected RF parameters were written
- expected ID parameters were not empty
- expected element count is greater than zero
- cleanup removed generated content fully

#### Geometry quality metrics

Used to answer: is the generated geometry acceptable?

Examples:

- `full_count`
- `viable_simple_count`
- `complex_count`
- `non_viable_count`
- `unwanted_count`
- `acceptable_count`
- `good_count`
- `micro_fragment_count`
- `min_viable_cut_mm`
- `min_cut_all_mm`
- `total_cut_area_mm2`
- `unique_sizes`

#### Placement quality metrics

Used to answer: was placement complete and sensible?

Examples:

- number of created stringers, supports, and tiles
- duplicate placements
- missing placements in expected cells
- placements outside expected zone
- invalid level or offset use

#### Stability metrics

Used to answer: is the result repeatable and safe?

Examples:

- repeated run produces the same counts and same key metrics
- rollback works on forced failure
- rerun does not accumulate stale elements
- cleanup is idempotent

### Recommended quality gates

The exact thresholds may differ by scenario, but the system should support
pass/fail decisions based on measurable rules.

#### Baseline quality gates for layout-related scenarios

- `non_viable_count == 0`
- `micro_fragment_count == 0`
- `min_cut_all_mm >= 50`
- `min_viable_cut_mm >= 100`
- `complex_count <= scenario_limit`
- `unique_sizes <= scenario_limit`

#### Baseline quality gates for placement-related scenarios

- expected placement count is reached
- no placement outside the target zone
- no unexpected duplicates
- no critical transaction failure

#### Baseline quality gates for cleanup-related scenarios

- all tracked generated IDs are deleted
- tracked RF ID parameters are cleared or updated correctly
- rerunning cleanup does not fail

### Scenario-specific expectations

The thresholds should be scenario-based, not globally hardcoded.

Examples:

- simple rectangle: almost zero tolerance for complex cuts
- rectangle with opening: limited complex cuts allowed near the opening
- L-shape: more complex cuts allowed, but still no non-viable cuts

### Weakness detection

Tests should explicitly help identify weak areas, not just final failures.

The report should show which subsystem degraded:

- contour quality
- grid quality
- shift quality
- placement completeness
- cleanup completeness

Typical weak signals:

- rising `complex_count`
- appearance of `non_viable_count`
- smaller `min_cut_all_mm`
- more unique cut sizes than expected
- unstable shift choice between runs or Revit versions
- residual elements after cleanup

### Where these metrics should be enforced

#### Non-Revit tests

- metric-producing helper functions in `floor_exact`
- result ranking helpers
- geometry and void decomposition helpers

#### pyRevit smoke tests

- lightweight sanity thresholds
- created element presence
- critical parameter write/read validation
- cleanup verification on safe test scenarios

#### Revit integration tests

- full quality assertions per scenario
- expected counts and thresholds on known test models
- comparison across Revit 2024 and Revit 2026

### Definition of a good test report

A good test report should answer all of these:

- did it run?
- did it build anything?
- was the result acceptable?
- where exactly is the weak spot?
- is the outcome stable across reruns and versions?
- did the command write to at least one non-modal surface even if the output window misbehaves?
- is there enough step-by-step trace to identify the failing phase quickly?
- can a tester reopen the same log outside the modal dialog path?

## Exit Criteria For Refactoring

Refactoring of large functions should start only when:

- Non-Revit coverage is strong enough on extracted logic.
- Smoke runner exists for real Revit host checks.
- At least one stable Revit model-based workflow exists.

This avoids rewriting large Revit-dependent scripts without a safety net.

## Immediate Next Steps

1. Keep expanding non-Revit tests where ROI is still high.
2. Refactor the existing pyRevit tests button into grouped smoke checks.
3. Define the exact smoke checklist for Revit 2024 and 2026.
4. Prepare a dedicated test project model.
5. Add first end-to-end integration scenarios on that model.


