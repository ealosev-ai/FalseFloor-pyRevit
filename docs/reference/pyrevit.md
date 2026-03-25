# pyRevit for RaisedFloor

## Coverage Reality

- pyRevit docs in Context7 are useful, but much thinner than Revit API docs.
- The strongest pyRevit coverage is:
  extension structure and bundle metadata,
  wrapper properties such as `revit.doc` and `revit.uidoc`,
  command and dev-registration workflow.
- The weakest pyRevit coverage is:
  real-world `forms` recipes,
  transaction-helper examples,
  `script.get_logger()` and config-save usage examples.
- For day-to-day command authoring in this repo, local code is often the best example set.

## Extension Structure

- pyRevit uses folder structure as UI structure.
- The structure relevant to this repo is:
  `.extension -> .tab -> .panel -> .pulldown/.pushbutton`
- `bundle.yaml` carries display and behavior metadata.
- Common metadata keys surfaced in docs:
  `title`
  `tooltip`
  `author`
  `authors`
  `help_url`
  `context`
  min and max Revit version keys
  layout-related keys
- The main panel layout for this repo is declared in `RaisedFloor.tab/RaisedFloor.panel/bundle.yaml`.

## Wrapper Modules Used Here

### `revit`

- `revit.doc` is the active Revit document.
- `revit.uidoc` is the active UI document.
- `revit.active_view` is also available in docs, but this repo mostly reads `doc.ActiveView`.
- Docs also expose `docs`, `open_doc`, and `close_doc`, though this repo does not rely on them much.

### `forms`

- Context7 coverage is sparse on concrete examples.
- In this repo, the practical patterns are:
  `forms.alert(...)` for messages and confirmations
  `forms.CommandSwitchWindow.show(...)` for mode or type selection
  `forms.ask_for_string(...)` for quick numeric or text input
- Good local examples:
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/UILanguage.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/02_OptimizeLayout.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/03_Stringers.pulldown/Place.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/04_Supports.pulldown/Place.pushbutton/script.py`

### `script`

- Documented in Context7:
  `script.get_output()`
  `script.get_config(section=None)`
  general utility helpers such as `clipboard_copy`, `journal_read`, `store_data`, `load_data`
- `script.get_logger()` is referenced in local docs and code, but Context7 surfaced less direct usage material for it.
- Local references:
  `docs/DEVELOPER_GUIDE.md`
  `run_tests.py`
- Current project pattern:
  long-running maintenance and smoke flows should prefer `lib/rf_reporting.py`,
  which wraps `script.get_output()` and `script.get_logger()` behind one reporter object

## Reporting Pattern In This Repo

- For short user interactions:
  `forms.alert(...)`
- For longer maintenance or diagnostic flows:
  `lib/rf_reporting.py`
- That helper currently writes to:
  `pyRevit output`
  `script.get_logger()`
  temporary text log file
- Good local examples:
  `lib/revit_smoke.py`
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/MigrateGUIDs.pushbutton/script.py`

## Transactions in Practice

- Context7 did not surface a strong pyRevit recipe for `revit.Transaction`.
- The local repo pattern is still clear and stable:
  keep transactions narrow,
  wrap only actual model mutation,
  validate as much as possible before starting the transaction.
- Good local examples:
  `lib/floor_grid.py`
  `RaisedFloor.tab/RaisedFloor.panel/02_OptimizeLayout.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/03_Stringers.pulldown/Place.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/05_Tiles.pulldown/Place.pushbutton/script.py`

## Bundle and UI Notes for This Repo

- This repository already uses `bundle.yaml` consistently across panel, pulldown, and button folders.
- The main panel bundle uses `title`, `tooltip`, and `layout`.
- Button bundles mostly use `title` and `tooltip`.
- Help content is handled locally through `help.html` and button scripts, not only through external URLs.

## Install and Dev Workflow

- Project install path already documented locally:
  `pyrevit extend ui RaisedFloor https://github.com/ealosev-ai/RaisedFloor-pyRevit.git --branch=main`
- Manual workflow already documented locally:
  add the `RaisedFloor.extension` folder in pyRevit and run Reload.
- pyRevit core development workflow surfaced by Context7:
  `pyrevit clones add dev <path-to-your-git-directory>`
  `pyrevit attach dev default --installed`
- The clone-and-attach workflow matters when hacking pyRevit itself, not just this extension repo.

## Dynamo-Related Hooks Inside pyRevit

- The pyRevit extensions docs expose Dynamo-related constants and metadata fields.
- Context7 surfaced:
  `.dyn` as a recognized script format
  Dynamo-related engine metadata keys in `pyrevit.extensions`
- This repo does not use those hooks today, but pyRevit itself has room for future Dynamo-backed commands.

## Good Default Prompts for Context7

- "pyRevit docs for extension metadata keys in `bundle.yaml`."
- "pyRevit docs for `revit.doc`, `revit.uidoc`, and output/config helpers."
- "pyRevit docs for `.extension`, `.tab`, `.panel`, `.pushbutton`, and `bundle.yaml` naming conventions."

## Source Basis

- Primary Context7 sources:
  `/pyrevitlabs/pyrevit`
  `/llmstxt/pyrevitlabs_io_llms-full_txt`


