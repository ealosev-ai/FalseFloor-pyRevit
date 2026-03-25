# Local Reference

This folder is a compact local knowledge base for developing `RaisedFloor.extension`.

It was assembled from:
- project code and local docs
- Context7 library lookups for Revit API, pyRevit, and Dynamo

Context7 libraries used:
- `/websites/revitapidocs`
- `/websites/revitapidocs_2024`
- `/websites/revitapidocs_2026`
- `/pyrevitlabs/pyrevit`
- `/llmstxt/pyrevitlabs_io_llms-full_txt`
- `/dynamods/dynamo`
- `/dynamods/dynamorevit`

## Read Order

1. Start with `revit-api.md`.
2. Then read `pyrevit.md`.
3. Read `pyrevit-devtools.md` when a task involves Revit-hosted smoke checks, output windows, debug UX, `script.get_logger()`, or the shared reporting helper `lib/rf_reporting.py`.
4. Read `pythonnet.md` when a task involves `clr`, `System.*`, WPF, or .NET interop behavior.
5. Read `clipper2.md` when a task touches exact contour geometry, clipping, or offset logic.
6. Read `github-actions.md` when a task touches CI, packaging, or workflow behavior.
7. Read `pyyaml.md` when a task plans YAML-backed settings or presets.
8. Open `dynamo.md` only if the task really involves Dynamo graphs or Dynamo interop.
9. For exact signatures, always prefer the docs for the Revit version that is actually running.

## What This Project Uses Most

- Selection and source-floor resolution:
  `lib/floor_common.py`,
  `RaisedFloor.tab/RaisedFloor.panel/01_Setup.pulldown/01_Floor.pushbutton/script.py`,
  `RaisedFloor.tab/RaisedFloor.panel/01_Setup.pulldown/02_Perimeter.pushbutton/script.py`,
  `RaisedFloor.tab/RaisedFloor.panel/02_OptimizeLayout.pushbutton/script.py`
- Parameter bindings and cross-version compatibility:
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Project.pushbutton/script.py`,
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py`,
  `lib/floor_utils.py`
- Grid and geometry:
  `lib/floor_grid.py`,
  `lib/floor_exact.py`
- Family placement and transforms:
  `RaisedFloor.tab/RaisedFloor.panel/03_Stringers.pulldown/Place.pushbutton/script.py`,
  `RaisedFloor.tab/RaisedFloor.panel/04_Supports.pulldown/Place.pushbutton/script.py`,
  `RaisedFloor.tab/RaisedFloor.panel/05_Tiles.pulldown/Place.pushbutton/script.py`
- pyRevit UI helpers:
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/UILanguage.pushbutton/script.py`,
  `RaisedFloor.tab/RaisedFloor.panel/07_Help.pushbutton/script.py`
- Reporting and maintenance diagnostics:
  `lib/rf_reporting.py`,
  `lib/revit_smoke.py`,
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/MigrateGUIDs.pushbutton/script.py`
- CLR and WPF interop:
  `lib/floor_ui.py`,
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/UILanguage.pushbutton/script.py`
- Clipper2 exact geometry:
  `lib/floor_exact.py`,
  `lib/floor_grid.py`,
  `tests/test_floor_exact_nonrevit.py`,
  `tests/test_ribbon_smoke.py`
- CI and packaging:
  `.github/workflows/ci-cd.yml`

## Practical Priority

- First source of truth: matching Revit API docs for the active Revit version.
- Second source of truth: working patterns already used in this repository.
- Third source of truth: pyRevit docs for wrapper behavior, bundle metadata, and dev workflow.
- Dynamo is currently secondary because this repository does not contain `.dyn` graphs.

## Project Baseline

- Scripts tested in Revit 2024 and 2026.
- Current release families are saved in Revit 2026.
- pyRevit baseline in local docs: 6.1.0.x.
- Revit internal length units are feet, even when the UI talks in mm.


