# pyRevit Dev Tools And Examples

## Purpose

This note collects the pyRevit documentation and example patterns that are
actually useful for developing and testing `RaisedFloor.extension`.

It is intentionally curated. The goal is not to mirror all pyRevit docs, but
to keep the high-value parts close to the repo:

- Revit-hosted smoke checks
- output/logging patterns
- forms/UI helpers
- family reload helpers
- command-bundle utilities

## What pyRevit Gives Us

Official pyRevit docs position pyRevit as a Revit development environment and
state that it ships with developer-oriented tools plus a CLI and extension
workflow.

Practical implication for this repo:

- use pyRevit for fast in-Revit iteration
- keep `pytest` for non-Revit logic
- use pyRevit-hosted smoke commands for real Revit API validation

## Most Useful Official Modules

### `pyrevit.script`

Official reference:

- https://docs.pyrevitlabs.io/reference/pyrevit/script/

Useful functions for this repo:

- `script.get_logger()`
- `script.get_output()`
- `script.get_config(section=None)`
- `script.load_index(index_file='index.html')`
- `script.load_ui(ui_instance, ui_file='ui.xaml', ...)`

What to use it for here:

- smoke-runner output
- grouped diagnostics
- loading local `help.html` or small HTML reports
- small command-local config if needed later
- backing `lib/rf_reporting.py`, which combines output + logger + text-log fallback

### `pyrevit.output`

Official reference:

- https://docs.pyrevitlabs.io/reference/pyrevit/output/

Useful examples from docs:

- `output.print_md(...)`
- `output.print_html(...)`
- `output.print_code(...)`
- `output.print_image(...)`
- `output.linkify(element_id)`
- `output.set_title(...)`

Why it matters for this repo:

- better smoke reports than plain `forms.alert(...)`
- clickable element IDs in diagnostics
- structured debug output for grid/layout/cleanup checks
- still useful, but no longer the only reporting surface after `lib/rf_reporting.py`

### `pyrevit.forms`

Official reference:

- https://docs.pyrevitlabs.io/reference/pyrevit/forms/

Useful patterns:

- `forms.alert(...)`
- input dialogs
- command switch windows

What to keep in mind:

- good for small operator-facing prompts
- not a replacement for richer smoke output
- for test reports, `script.get_output()` is usually better than many modal dialogs

### `pyrevit.unittests`

Official reference:

- https://docs.pyrevitlabs.io/reference/pyrevit/unittests/

What the docs say in practice:

- pyRevit has a Revit-hosted testing layer
- its main value is complete tests in a live Revit environment

How to use that here:

- not as a replacement for repo `pytest`
- useful as design guidance for Revit-hosted smoke suites
- appropriate for environment/document/family/transaction checks

## Family Reload Example Worth Reusing

Official pyRevit docs expose `pyrevit.revit.db.create.FamilyLoaderOptionsHandler`
and `load_family(...)` helpers.

Reference:

- https://docs.pyrevitlabs.io/reference/pyrevit/revit/db/create/

Why this matters for this repo:

- it confirms the right shape of `IFamilyLoadOptions` handling
- it aligns with our current fix to reload edited families back into the project
  without calling `Save()` on the `.rfa`

Practical takeaway:

- when reloading a family into the source project, prefer explicit
  `IFamilyLoadOptions`
- do not rely on disk save as part of normal parameter-sync flow

## What To Copy Into This Repo

Good candidates for local reuse:

- output-window report patterns
- linkified element diagnostics
- small HTML report loading
- `IFamilyLoadOptions` family reload pattern
- smoke-runner structure for Revit-hosted checks

Bad candidates for blind copying:

- whole pyRevit developer tool bundles
- unrelated extension-management code
- generic pyRevit sample code that does not match our Revit workflow

## Recommended Use In RaisedFloor

### Revit-Hosted Smoke Button

The most useful pyRevit-devtools-style addition for this repo is a better
smoke runner under `99_Tests.pulldown`.

It should check:

- active document and plan-view assumptions
- canonical project shared parameters
- family GUID mismatch state
- family reload viability
- floor/grid/layout preconditions
- cleanup sanity

### Output Style

Use a mixed strategy:

- `forms.alert(...)` for short blocking decisions
- `lib/rf_reporting.py` for the main report path in long-running or maintenance commands
- `script.get_output()` as one sink inside that report path, not the only sink
- `output.linkify(...)` when reporting problematic Revit elements

Current repo pattern:

- `lib/rf_reporting.py` centralizes multi-sink reporting
- `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/MigrateGUIDs.pushbutton/script.py`
  uses it for staged migration tracing
- `lib/revit_smoke.py` uses it for grouped smoke reports and text-log fallback

### Bundle-Local Help

When a command has richer diagnostics or help:

- keep `help.html` inside the command bundle
- load it through `script.load_index(...)`

This fits the repo's existing pattern better than external URLs.

## Source Basis

Primary official sources used for this note:

- pyRevit docs home:
  https://docs.pyrevitlabs.io/
- `pyrevit.script`:
  https://docs.pyrevitlabs.io/reference/pyrevit/script/
- `pyrevit.output`:
  https://docs.pyrevitlabs.io/reference/pyrevit/output/
- `pyrevit.forms`:
  https://docs.pyrevitlabs.io/reference/pyrevit/forms/
- `pyrevit.unittests`:
  https://docs.pyrevitlabs.io/reference/pyrevit/unittests/
- `pyrevit.revit.db.create`:
  https://docs.pyrevitlabs.io/reference/pyrevit/revit/db/create/



