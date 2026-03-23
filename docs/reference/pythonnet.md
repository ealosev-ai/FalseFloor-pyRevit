# Python.NET for RaisedFloor

## Why It Matters Here

- This repo is not pure Python. It crosses into CLR and WPF through `clr` and `System.*`.
- The two main local use cases are:
  loading private or framework assemblies,
  then importing .NET namespaces and types from Python.
- Current project examples:
  `lib/floor_ui.py`
  `RaisedFloor.tab/RaisedFloor.panel/00_Parameters.pulldown/UILanguage.pushbutton/script.py`
  test stubs in `tests/test_ribbon_smoke.py`

## Assembly Loading

- Use `clr.AddReference("AssemblyName")` when the assembly can be resolved by name.
- Use `clr.AddReferenceToFileAndPath(absolute_path)` for private DLLs shipped inside the extension.
- For this repo, `AddReferenceToFileAndPath(...)` is the important pattern because `lib/floor_exact.py` loads `lib/Clipper2Lib.dll` directly from the extension root.
- Prefer absolute paths derived from the extension root, not the current working directory.
- Load assemblies explicitly before importing types from their namespaces.

## Import Pattern

- After a successful reference load, .NET namespaces are imported like Python packages:
  `from System.Windows import Window`
- If an import fails, suspect assembly loading first and namespace spelling second.
- Avoid broad `*` imports in shared code. Explicit imports are easier to read and less fragile.

## Overloads, Enums, and Type Conversion

- Python values can match multiple .NET overloads. That is a common cause of ambiguous or incorrect calls.
- When needed, disambiguate with:
  `Method.Overloads[...]`
  or `Method.__overloads__[...]`
- The same rule applies to overloaded constructors.
- Prefer passing enum members instead of raw integers.
- If overload resolution still looks unstable, use explicit CLR types such as `Int32(...)` or `String(...)`.

## Exceptions Across the Boundary

- Managed .NET exceptions can be caught directly in Python:
  `except SomeDotNetException as e:`
- Useful fields include `e.Message` and often `e.InnerException`.
- Unhandled Python exceptions inside .NET callbacks or event handlers may surface as wrapped .NET errors.
- Practical rule for this repo:
  wrap event handlers and WPF callbacks with `try/except`,
  then log or show the Python-side context explicitly.

## WPF Notes for This Repo

- The local WPF dialog code in `lib/floor_ui.py` follows the correct broad pattern:
  load `PresentationFramework`,
  load `PresentationCore`,
  load `WindowsBase`,
  then import `System.Windows` and `System.Windows.Controls` types.
- Missing references usually fail later as parser or type-resolution errors, not always at the first import line.
- Revit UI rules still apply. Anything modeless or cross-threaded should respect Revit API constraints.

## Testing Pattern Already Used Here

- The tests do not require a real CLR runtime for import-level validation.
- `tests/test_ribbon_smoke.py` and `tests/test_floor_exact_nonrevit.py` stub `clr.AddReference` and `clr.AddReferenceToFileAndPath`.
- That is the right approach for non-Revit unit tests:
  isolate your import surface,
  stub the CLR bridge,
  test your Python logic separately from the real host runtime.

## Practical Checklist

- If a new .NET import fails:
  verify the assembly is loaded first.
- If a method call behaves strangely:
  suspect overload resolution before suspecting business logic.
- If a private DLL fails to load:
  check absolute path construction and extension-root discovery.
- If WPF code works in Revit but fails in tests:
  keep the imports lazy and keep CLR/WPF stubs lightweight.

## Good Default Prompts for Context7

- "pythonnet docs for `clr.AddReference` and assembly resolution behavior."
- "pythonnet docs for overloaded .NET methods from Python."
- "pythonnet docs for catching managed exceptions in Python."

## Source Basis

- Primary Context7 source:
  `/pythonnet/pythonnet`
