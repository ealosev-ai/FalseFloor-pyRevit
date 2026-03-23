# Revit API for RaisedFloor

## Baseline

- Use this file first when a task touches model changes, selection, parameters, family placement, or geometry.
- Match the docs to the running Revit version whenever signatures or behavior are version-sensitive.
- This project explicitly carries compatibility code for Revit 2024 and Revit 2025+/2026 in `lib/floor_utils.py`.

## Selection and View Context

- Most commands assume the active view is a `ViewPlan`. The common pattern is: validate `doc.ActiveView`, alert early, and stop.
- Interactive picking is done through `uidoc.Selection.PickObject(...)` and sometimes `uidoc.Selection.PickBox(...)`.
- `PickObject(ObjectType.Element, selection_filter, prompt)` is the main pattern used in this repo.
- Always handle `OperationCanceledException` as a normal user cancel, not as a hard error.
- Custom `ISelectionFilter` is the right way to constrain picks. The repo pattern is in `lib/floor_common.py` via `FloorOrPartSelectionFilter`.

## Collectors, Families, and Symbols

- Use `FilteredElementCollector(doc)` for global lookup and `FilteredElementCollector(doc, view.Id)` for view-scoped lookup.
- `Family` is the definition container. `FamilySymbol` is the type that gets placed.
- Typical flow in this repo:
  find family by name,
  iterate symbol ids,
  resolve the symbol,
  inspect or set type parameters,
  place instances from the chosen symbol.
- Activate a `FamilySymbol` before placement if needed, and do it inside a transaction.

## Placement and Transforms

- All model writes belong inside a transaction. The repo standard is `with revit.Transaction("..."):`.
- Placement is done through `doc.Create.NewFamilyInstance(...)`.
- Different commands place different family types, but the pattern stays the same:
  compute XYZ or line,
  place the instance,
  then apply parameter values and transforms.
- `ElementTransformUtils.MoveElement(...)` is used for vertical offsets or post-placement corrections.
- `ElementTransformUtils.RotateElement(...)` is used for support or reinforcement orientation.
- Rotation angles are radians.

## Parameters and Shared Parameter Bindings

- `LookupParameter("RF_...")` is used heavily in this project because the parameter names are controlled by the extension itself.
- `LookupParameter(...)` is still name-based and can be fragile in general Revit code. Always check for `None`.
- Shared project parameters are created through:
  `ExternalDefinitionCreationOptions`
  plus `InstanceBinding` or `TypeBinding`
  plus `doc.ParameterBindings.Insert(...)` or `ReInsert(...)`.
- Category sets are built explicitly, not implicitly.
- The compatibility split in this repo is important:
  use `SpecTypeId` and `GroupTypeId` when available,
  fall back to `ParameterType` and `BuiltInParameterGroup` for older API paths.
- The local helpers that already encode this logic are:
  `get_storage_type_id`
  `get_data_group_type_id`
  `create_category_set`
  `get_existing_parameter_bindings`

## Geometry Basics

- `XYZ` is the base point/vector type.
- `Line.CreateBound(start, end)` is the standard way this repo creates finite model lines and placement axes.
- `CurveLoop` is the right abstraction for ordered closed contour geometry.
- Revit internal units are feet. This repo frequently converts to and from mm for user-facing values.
- Closed loops and consistent Z handling matter more than elegance. Most geometry bugs here come from units, closure, or tolerance drift.

## Version Notes That Matter Here

- Revit 2024 introduced additional collector support for link-visible elements in a host view. Useful only if linked-model workflows are added later.
- Revit 2024+ and newer APIs continue the shift toward `ForgeTypeId`-based parameter typing.
- For new code in this repo, prefer `SpecTypeId` and `GroupTypeId`. Keep enum fallbacks only for backward compatibility.

## Where These APIs Show Up in This Repo

- Selection and host floor resolution:
  `lib/floor_common.py`
  `RaisedFloor.tab/RaisedFloor.panel/01_Setup.pulldown/01_Floor.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/02_OptimizeLayout.pushbutton/script.py`
- Contour extraction and plan-view checks:
  `RaisedFloor.tab/RaisedFloor.panel/01_Setup.pulldown/02_Perimeter.pushbutton/script.py`
- Grid creation and line work:
  `lib/floor_grid.py`
- Shared parameter binding:
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Project.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/Families.pushbutton/script.py`
  `lib/floor_utils.py`
- Instance placement:
  `RaisedFloor.tab/RaisedFloor.panel/03_Stringers.pulldown/Place.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/04_Supports.pulldown/Place.pushbutton/script.py`
  `RaisedFloor.tab/RaisedFloor.panel/05_Tiles.pulldown/Place.pushbutton/script.py`

## Good Default Prompts for Context7

- "Revit API 2026 signature and caveats for `NewFamilyInstance` overloads used from Python."
- "Revit API docs for `ExternalDefinitionCreationOptions`, `InstanceBinding`, `TypeBinding`, and `GroupTypeId`."
- "Revit API docs for `ISelectionFilter`, `PickObject`, `PickBox`, and `ObjectType`."

## Source Basis

- Primary Context7 source:
  `/websites/revitapidocs`
- Version checks used while preparing this note:
  `/websites/revitapidocs_2024`
  `/websites/revitapidocs_2026`
