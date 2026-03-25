# RaisedFloor.extension Technical Audit

Original audit date: 2026-03-22
Status update: 2026-03-24
Scope: current working tree, not last committed revision
Reference basis:
- `docs/reference/revit-api.md`
- `docs/reference/pyrevit.md`
- `docs/reference/pythonnet.md`
- `docs/reference/clipper2.md`
- `docs/reference/github-actions.md`
- `docs/reference/pyyaml.md`
- `docs/reference/dynamo.md`

## Status Summary

- The original audit is materially improved in the current worktree.
- No original audit finding from the 2026-03-22 scope remains open.
- The largest closed items are:
  - grid redraw ownership
  - canonical shared-parameter schema with stable GUIDs
  - project and family GUID migration flow
  - CI path-filter drift
  - release packaging drift
  - legacy Revit smoke runner gap at the code level
  - Ruff lint contour
  - operator-facing hosted reporting fallback
- Remaining follow-up is roadmap work, not audit-closeout work:
  - service extraction from long button scripts
  - optional YAML-backed tunables and presets

## Closed Findings Since 2026-03-22

### High

1. `redraw_grid_for_floor()` no longer deletes RF-styled curves across the active view.
- Current state:
  - `lib/floor_grid.py` now collects generated element IDs from the selected floor via `_collect_owned_grid_ids()`
  - delete/cleanup targets only floor-owned artifacts recorded in `RF_Grid_Lines_ID` and `RF_Base_Marker_ID`
- Assessment:
  - the original cross-zone destructive redraw bug is closed
- Refs:
  - `lib/floor_grid.py`
  - `tests/test_floor_grid_nonrevit.py`

2. Normal family-parameter maintenance no longer depends on the old disk-mutating `Save()` workflow.
- Current state:
  - `Families.pushbutton` routes family GUID repair through `migrate_family_doc()`
  - destructive `Remove+Add` behavior is isolated behind maintenance-only `allow_destructive`
  - explicit migration UX exists in `MigrateGUIDs.pushbutton`
- Assessment:
  - the original runtime repository-binary mutation concern is closed for normal operator flow
- Refs:
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/MigrateGUIDs.pushbutton/script.py`
  - `lib/rf_family_migration.py`

3. A canonical shared-parameter identity model with stable GUIDs now exists.
- Current state:
  - `resources/RaisedFloor.sharedparameters.txt` is the canonical schema source
  - `lib/rf_param_schema.py` centralizes `RF_PARAMETER_GUIDS`, schema creation, and mismatch detection
  - `lib/rf_project_migration.py` implements project GUID migration with snapshot, recreate, and restore flow
  - `lib/rf_family_migration.py` implements family GUID migration with safe `ReplaceParameter` strategies and maintenance-only destructive fallback
  - all relevant UI entrypoints now route through the new migration helpers
- Assessment:
  - the original "name-stable but GUID-unstable" parameter model is closed
- Refs:
  - `resources/RaisedFloor.sharedparameters.txt`
  - `lib/rf_param_schema.py`
  - `lib/rf_project_migration.py`
  - `lib/rf_family_migration.py`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Project.pushbutton/script.py`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/MigrateGUIDs.pushbutton/script.py`

### Medium

4. Workflow path filters now cover real runtime assets.
- Current state:
  - `.github/workflows/ci-cd.yml` now includes `Families/**/*.rfa`
  - it also includes `RaisedFloor.tab/**/*.yaml`, `RaisedFloor.tab/**/*.html`, and `RaisedFloor.tab/**/*.htm`
- Assessment:
  - the original CI bypass risk from untracked runtime asset changes is closed
- Refs:
  - `.github/workflows/ci-cd.yml`

5. Release packaging now excludes the dev-only tests panel correctly.
- Current state:
  - release build removes `RaisedFloor.tab/RaisedFloor.panel/99_Tests.pulldown11`
- Assessment:
  - the original package drift on the dev test panel path is closed
- Refs:
  - `.github/workflows/ci-cd.yml`

6. Revit-hosted smoke execution is no longer only a tiny legacy sanity script.
- Current state:
  - `run_tests.py` now delegates to grouped smoke execution in `lib/revit_smoke.py`
  - pure tests exist for hosted smoke/report shaping
- Assessment:
  - the original "strategy says one thing, hosted runner does almost nothing" finding is materially closed at the code level
- Refs:
  - `run_tests.py`
  - `lib/revit_smoke.py`
  - `tests/test_revit_smoke_pure.py`

7. Ruff lint contour is now green again.
- Current state:
  - the last remaining unused imports/local variable were removed from `lib/floor_utils.py` and `lib/rf_project_migration.py`
  - `.\.venv\Scripts\python.exe -m ruff check lib RaisedFloor.tab tests` now passes
- Assessment:
  - the original CI lint finding is closed
- Refs:
  - `lib/floor_utils.py`
  - `lib/rf_project_migration.py`
  - `.github/workflows/ci-cd.yml`

8. Hosted operator-facing diagnostics/reporting now uses multi-sink fallback.
- Current state:
  - `lib/rf_reporting.py` writes the same trace to `pyRevit output`, `script.get_logger()`, and a temporary text log file
  - `MigrateGUIDs.pushbutton` now reports stages and final details through the shared helper
  - `lib/revit_smoke.py` now renders smoke reports through the same helper and returns `log_path`
  - pure tests cover the shared reporting helper
- Assessment:
  - the output window is no longer the sole reporting surface, so the original operator-facing reporting gap is closed
- Refs:
  - `lib/rf_reporting.py`
  - `lib/revit_smoke.py`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/MigrateGUIDs.pushbutton/script.py`
  - `tests/test_rf_reporting.py`

## Open Findings

- None for the original 2026-03-22 audit scope.
- Remaining work is architectural improvement, not audit defect remediation.

## Architecture

- Strong part:
  - geometry/core domain logic remains concentrated in `lib/`
- Improved parts:
  - parameter identity and migration are now extracted into dedicated services instead of being spread only across button scripts
  - reporting for maintenance/diagnostic flows is now centralized in `lib/rf_reporting.py`
- Remaining weak part:
  - several large pyRevit button scripts still mix UI, orchestration, Revit API calls, model writes, and cleanup
- Persistent state is still primarily stored as:
  - `RF_*` parameters
  - semicolon-separated element ID lists on the floor element
- Assessment:
  - this is acceptable for the current extension stage, but service extraction is still the main architectural follow-up

## Risks And Bugs

- No original high-severity audit finding remains open in the same form.
- Near-term risk is now mostly architectural rather than data-destructive:
  - orchestration-heavy button scripts
  - string-based element ID persistence
  - name-based `LookupParameter("RF_*")` access patterns in runtime code

## Revit API / pyRevit / pythonnet / Clipper2

### Revit API

- Usage remains broadly aligned with local reference:
  - `ISelectionFilter`
  - `PickObject`
  - `FilteredElementCollector`
  - transaction-scoped model writes
  - `LookupParameter("RF_*")`
- Cross-version parameter handling is stronger than in the original audit state because schema and migration logic are now centralized.

### pyRevit

- `forms`, `revit.Transaction`, `script.get_output()`, and `script.get_logger()` usage are consistent with local project guidance.
- Maintenance/diagnostic scripts now have a shared reporting layer instead of ad hoc output-only rendering.

### pythonnet

- Interop handling improved in the migration work:
  - family `ReplaceParameter` logic now explicitly tries multiple overload-resolution strategies
- Assessment:
  - this is a stronger and more defensible interop approach than the original ad hoc state

### Clipper2

- This remains a strong part of the implementation.
- No new audit concern was introduced here.

### Dynamo

- Current relevance remains low.
- Repository still does not implement Dynamo interop, which is consistent with `docs/reference/dynamo.md`.

## Tests And CI

### Focused verification in this worktree

- `.\.venv\Scripts\python.exe -m ruff check lib RaisedFloor.tab tests`
  - Result: pass
- `.\.venv\Scripts\python.exe -m pytest tests/test_rf_reporting.py tests/test_revit_smoke_pure.py tests/test_rf_migration.py -q`
  - Result: `22 passed`
- `.\.venv\Scripts\python.exe -m py_compile` on touched reporting and migration files
  - Result: pass

### Assessment

- Non-Revit unit coverage remains useful and catches real regressions.
- The parameter migration area now has direct focused tests.
- The hosted smoke runner is materially improved versus the original audit baseline.
- The reporting layer now has direct pure tests, which reduces regressions in maintenance UX.

## YAML Config Candidates

Good future candidates:
- geometry/search tunables
- visual style presets
- workflow defaults and placement presets

Bad candidates:
- canonical parameter GUID schema
- any identity-critical data that must remain stable and explicit

Assessment:
- YAML remains a later convenience layer, not an audit-closeout dependency.

## Improvement Plan

1. Continue extracting orchestration logic from large button scripts into `lib/` services.
2. Keep YAML work scoped to tunables and presets, not parameter identity.
3. Expand the shared reporting helper gradually to other long-running maintenance flows when it reduces duplication.

## Short Roadmap

### Phase 1
- service extraction from long button scripts

### Phase 2
- optional YAML-backed tunables and presets

### Phase 3
- incremental reuse of shared reporting/service helpers across remaining heavy scripts
