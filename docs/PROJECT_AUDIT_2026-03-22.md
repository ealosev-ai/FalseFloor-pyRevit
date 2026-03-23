# RaisedFloor.extension Technical Audit

Date: 2026-03-22
Scope: current working tree, not last committed revision
Reference basis:
- `docs/reference/revit-api.md`
- `docs/reference/pyrevit.md`
- `docs/reference/pythonnet.md`
- `docs/reference/clipper2.md`
- `docs/reference/github-actions.md`
- `docs/reference/pyyaml.md`
- `docs/reference/dynamo.md`

## Findings

### High

1. `redraw_grid_for_floor()` deletes RF-styled curves across the active view, not only for the selected floor.
- Risk: redraw of one zone can erase grid and markers of another zone on the same plan.
- Refs:
  - `lib/floor_grid.py:178`
  - `lib/floor_grid.py:324`
  - `lib/floor_grid.py:372`

2. Family parameter sync mutates versioned `.rfa` files on disk and the rollback path is not reliable after `Save()`.
- Risk: runtime command changes repository assets and leaves dirty binaries.
- Refs:
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py:388`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py:404`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py:405`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py:423`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py:436`

3. There is no canonical shared-parameter schema with stable GUIDs for both project and family parameters.
- Current state:
  - project params are created from a temporary shared-parameter file
  - family params are created from the user shared-parameter file
- Risk: name-stable but GUID-unstable `RF_*` parameters, fragile across reloads, schedules, tags, and cross-project consistency.
- Refs:
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Project.pushbutton/script.py:254`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Project.pushbutton/script.py:291`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py:175`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py:213`

### Medium

4. CI lint contour is currently red while pytest is green.
- Main issues:
  - unused variables/imports
  - import-order violations in tests
- Refs:
  - `.github/workflows/ci-cd.yml:87`
  - `lib/floor_ui.py:243`
  - `lib/floor_utils.py:37`
  - `RaisedFloor.tab/RaisedFloor.panel/03_Stringers.pulldown/Place.pushbutton/script.py:637`
  - `tests/test_floor_common.py:15`

5. Release packaging excludes `99_Tests.pulldown`, but the actual dev panel is `99_Tests.pulldown11`.
- Risk: dev-only test button may ship in production ZIP.
- Refs:
  - `.github/workflows/ci-cd.yml:129`
  - `RaisedFloor.tab/RaisedFloor.panel/99_Tests.pulldown11/Run Tests.pushbutton/script.py:1`
  - `README.md:61`

6. Workflow path filters do not cover some real runtime assets.
- Missing categories:
  - `Families/*.rfa`
  - `RaisedFloor.tab/**/*.yaml`
  - help/html content
- Risk: runtime regressions can bypass CI.
- Refs:
  - `.github/workflows/ci-cd.yml:7`
  - `.github/workflows/ci-cd.yml:17`
  - `RaisedFloor.tab/RaisedFloor.panel/bundle.yaml:1`

7. Revit-hosted test contour is much weaker than the declared strategy.
- Real state:
  - `run_tests.py` is a small in-Revit sanity script
  - coverage gate exists in CI command, not in `pytest.ini`
  - high-risk hosted scenarios are not covered well
- Refs:
  - `run_tests.py:25`
  - `pytest.ini:1`
  - `docs/TEST_STRATEGY.md:16`
  - `docs/TEST_STRATEGY.md:175`

## Architecture

- Strong part: geometry and scoring logic are reasonably concentrated in `lib/floor_exact.py` and shared helpers in `lib/floor_common.py`.
- Weak part: long pyRevit button scripts still mix UI, orchestration, Revit API calls, data writes, and cleanup.
- Heaviest scripts:
  - `RaisedFloor.tab/RaisedFloor.panel/03_Stringers.pulldown/Place.pushbutton/script.py`
  - `RaisedFloor.tab/RaisedFloor.panel/05_Tiles.pulldown/Place.pushbutton/script.py`
  - `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py`
- Persistent state is mostly stored as `RF_*` parameters and semicolon-separated element ID lists on the floor element.
- That is simple for MVP, but weak for migrations, ownership tracking, and multi-zone behavior.

## Risks And Bugs

- Cross-zone destructive redraw on one active view.
- Runtime modification of versioned family binaries.
- Missing canonical parameter identity model.
- CI/package drift from actual repository structure.
- Operational dependence on string-based ID persistence and name-based `LookupParameter("RF_*")`.

## Revit API / pyRevit / pythonnet / Clipper2

### Revit API

- Usage is broadly aligned with local reference:
  - `ISelectionFilter`
  - `PickObject`
  - `FilteredElementCollector`
  - transaction-scoped model writes
  - `LookupParameter("RF_*")`
- Cross-version parameter typing compatibility is handled in `lib/floor_utils.py`.

### pyRevit

- `forms` and `revit.Transaction` usage is consistent.
- Main issue is not pyRevit API misuse, but excessive orchestration logic inside button scripts.

### pythonnet

- Good:
  - lazy WPF imports in `lib/floor_ui.py`
  - private DLL load through `clr.AddReferenceToFileAndPath()` in `lib/floor_exact.py`
- Risk:
  - `floor_exact` performs Clipper loading at import time, so DLL/load failures break module import entirely.

### Clipper2

- This is a strong part of the implementation.
- Flow matches local reference:
  - Revit internal feet
  - convert to mm
  - scale to int64
  - Clipper2 boolean/offset ops
  - convert back to mm/internal units
- Key locations:
  - `lib/floor_exact.py:17`
  - `lib/floor_exact.py:480`
  - `lib/floor_exact.py:543`

### Dynamo

- Current relevance is low.
- Repository does not contain `.dyn` assets and does not implement Dynamo interop.
- This matches `docs/reference/dynamo.md`.

## Tests And CI

### Executed locally during audit

- `.\.venv\Scripts\python -m pytest tests/ -m "not revit" -q`
  - Result: `250 passed, 2 skipped`
- `.\.venv\Scripts\python run_smoke_tests.py`
  - Result: `75 passed`
- `.\.venv\Scripts\python -m pytest tests/ -m "not revit" --cov=lib --cov-fail-under=60 -q`
  - Result: pass
  - Total coverage: `76.43%`
- `.\.venv\Scripts\python -m mypy lib --ignore-missing-imports --no-error-summary`
  - Result: pass
- `.\.venv\Scripts\python -m ruff check lib RaisedFloor.tab tests`
  - Result: fail

### Assessment

- Non-Revit unit contour is materially useful and catches real regressions.
- `test_ribbon_smoke.py` is high-value because it protects script imports and call signatures outside Revit.
- Revit-hosted contour is still too weak relative to the strategy in `docs/TEST_STRATEGY.md`.
- CI structure is broadly correct, but repository filters and release packaging are not fully aligned with actual project layout.

## YAML Config Candidates

Good candidates for external config:
- geometry/search thresholds from `lib/floor_exact.py`
- visual styles and colors from `lib/floor_grid.py`
- default workflow inputs:
  - tile step
  - floor height
  - tile thickness
  - lower stringer step
  - max stringer length
  - support spacing
- family/type presets and placement presets
- release manifest and dev-only exclusions for packaging

Bad candidates for YAML:
- shared-parameter identity schema with GUIDs
- `bundle.yaml` rewriting through PyYAML

Notes from local reference:
- use `yaml.safe_load()` and `yaml.safe_dump()`
- do not use PyYAML to rewrite pyRevit `bundle.yaml` files if comments/formatting matter

## Improvement Plan

1. Introduce a canonical shared-parameter file with stable GUIDs and make both project/family parameter commands depend on it.
2. Remove disk-mutating family sync behavior from normal runtime flow. Use copy/import workflow or explicit maintenance command.
3. Fix generated-element ownership so grid redraw/cleanup touches only the selected floor's artifacts.
4. Bring CI back to green:
   - fix Ruff findings
   - correct dev-panel exclusion path
   - expand workflow path filters to runtime assets
5. Replace `run_tests.py` with a real grouped Revit smoke runner matching `docs/TEST_STRATEGY.md`.
6. Refactor long button scripts into `lib/` services:
   - parameter schema
   - family sync
   - grid ownership
   - stringer layout
   - support placement
   - tile placement
7. After that, introduce YAML only for tunables and presets, not for identity-critical data.

## Short Roadmap

### Phase 1
- parameter schema stabilization
- CI/package fixes
- green lint

### Phase 2
- generated-element ownership model
- family-sync redesign

### Phase 3
- Revit smoke runner
- service extraction from long button scripts

### Phase 4
- YAML-backed tunables and presets
- richer hosted integration scenarios
