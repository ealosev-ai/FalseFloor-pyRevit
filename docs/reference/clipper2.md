# Clipper2 for RaisedFloor

## Why It Matters Here

- Clipper2 is part of the geometry core of this repo, not an optional add-on.
- Main local entry points:
  `lib/floor_exact.py`
  `lib/floor_grid.py`
- The repo loads `Clipper2Lib.dll` through CLR and works in this flow:
  Revit internal feet -> mm -> scaled int64 -> Clipper2 ops -> back to mm/internal units.

## Core Types

- `Point64` is one integer point with `X` and `Y`.
- `Path64` is one contour.
- `Paths64` is a list of contours.
- In practical terms:
  one outer contour is one `Path64`,
  hole contours are more `Path64`,
  the full shape set is a `Paths64`.

## Boolean Operations

- Core boolean calls surfaced by docs:
  `Clipper.Intersect(Paths64 subject, Paths64 clip, FillRule fillRule)`
  `Clipper.Difference(Paths64 subject, Paths64 clip, FillRule fillRule)`
- For this repo, `Intersect(...)` is the main operation for exact cell clipping.
- `Difference(...)` matters for subtracting holes or building clipped subject regions.
- `FillRule.NonZero` is the practical default for CAD-style contour and hole work.

## Offsetting

- Main offset API:
  `InflatePaths(Paths64, delta, JoinType, EndType, miterLimit=2.0, arcTolerance=0.0)`
- Closed contours should use `EndType.Polygon`.
- `JoinType` controls corner behavior:
  `Miter` for sharp corners,
  `Round` for rounded corners,
  `Bevel` for chamfer-like behavior.
- Local docs already describe contour offset usage around stringer logic and exact zone handling.

## Scaling and Numeric Range

- Clipper64 is integer-based for robustness.
- This repo uses `SCALE = 1000.0`, meaning mm are converted to finer int64 units before clipping.
- That is a sound pattern, but large world coordinates can still hurt robustness and speed.
- Clipper2 docs note:
  safe math range is roughly within 62-bit coordinates,
  practical robustness degrades when magnitudes get very large.
- Repo implication:
  keep using a fixed scale,
  and if future tasks use very large site coordinates, consider normalizing around a local origin before clipping.

## Fill Rules, Orientation, and Holes

- Supported fill rules include:
  `EvenOdd`
  `NonZero`
  `Positive`
  `Negative`
- For this project, `NonZero` is the right default unless a specific geometric counterexample proves otherwise.
- Orientation matters when interpreting holes.
- Clipper2 docs note that holes in solutions are associated with negative winding.
- Do not rely on flat `Paths64` output order to mean semantic nesting by itself.

## Repeated Rectangle Clipping

- If the clip region is strictly rectangular, `RectClip64` is faster than general `Intersect(...)`.
- Docs note these practical differences:
  it performs intersection only,
  it preserves orientation,
  it is fill-rule agnostic,
  it clips each subject independently.
- For this repo, that suggests a future optimization path:
  fast rectangle-window filtering first,
  then general `Intersect` or `Difference` only where exact contour logic still matters.
- This is relevant because `floor_grid.py` repeatedly clips line or cell-like geometry against contour-derived regions.

## Local Implementation Notes

- `lib/floor_exact.py` already does the important low-level things correctly:
  extension-root discovery,
  absolute DLL path build,
  explicit `AddReferenceToFileAndPath(...)`,
  conversion helpers,
  explicit import of `Point64`, `Path64`, `Paths64`, `Intersect`, `Difference`, `InflatePaths`.
- `lib/floor_grid.py` builds on top of that for repeated clipping operations.
- The tests already protect the DLL-load edge cases:
  missing DLL path,
  CLR load failure,
  stubbed Clipper types for non-Revit tests.

## Practical Checklist

- If geometry results look wrong:
  verify units and scaling before debugging the boolean itself.
- If holes behave strangely:
  inspect fill rule and contour orientation before touching heuristics.
- If performance degrades:
  look for repeated general-purpose clipping that could be windowed or simplified first.
- If imports fail:
  debug DLL path and CLR load before debugging geometry.

## Good Default Prompts for Context7

- "Clipper2 docs for `Intersect`, `Difference`, and `FillRule.NonZero`."
- "Clipper2 docs for `InflatePaths` with closed polygon contours."
- "Clipper2 docs for `RectClip64` versus general boolean clipping."

## Source Basis

- Primary Context7 source:
  `/websites/angusj_clipper2`
