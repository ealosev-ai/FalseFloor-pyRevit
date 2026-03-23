# PyYAML for RaisedFloor

## Current Relevance

- This repo already contains many `bundle.yaml` files, but the project does not currently parse YAML in Python code.
- That means PyYAML is a future-facing tool here, not a current runtime dependency.
- It becomes relevant if you decide to externalize:
  presets,
  family mappings,
  tolerances,
  layout rules,
  environment-specific config.

## Safe Loading and Dumping

- Use `yaml.safe_load()` for future config parsing.
- Avoid bare `yaml.load(...)` entirely.
- If trusted input ever requires richer Python-specific types, only then use `yaml.load(..., Loader=yaml.FullLoader)` or `yaml.full_load(...)`.
- Use `yaml.safe_dump()` when writing config back.
- For readable diffs, good defaults are:
  `sort_keys=False`
  `default_flow_style=False`

## Data Shape Expectations

- Normal config structures round-trip fine as plain data:
  `dict`
  `list`
  `str`
  `int`
  `float`
  `bool`
  `None`
- Be careful with YAML implicit typing rules. If a value must stay string-like, quote it deliberately.

## Multi-Document YAML

- PyYAML supports `safe_load_all()` and `safe_dump_all()` for `---` separated streams.
- For this repo, single-document files are the right default.
- Multi-document YAML only matters if you intentionally choose that format for generated data.

## Windows and Encoding Notes

- Open YAML files with explicit encoding.
- Practical default:
  read with `encoding="utf-8-sig"` if BOM may appear,
  write with `encoding="utf-8"`.
- Good pattern:

```python
with open(path, "r", encoding="utf-8-sig") as f:
    data = yaml.safe_load(f) or {}
```

## Round-Trip Caveats

- PyYAML is good for data, not for editing hand-crafted YAML while preserving formatting.
- It does not reliably preserve:
  comments,
  original quote style,
  original layout choices.
- Key order can also change unless you set `sort_keys=False`.
- Practical implication:
  do not use PyYAML to rewrite `bundle.yaml` files if preserving human formatting and comments matters.
- If exact round-trip fidelity ever becomes a requirement, PyYAML is likely the wrong tool.

## Where It Could Fit in This Repo

- A good fit:
  new machine-managed config files under `docs/`, `config/`, or `release/`.
- A bad fit:
  bulk rewriting pyRevit bundle metadata files that people maintain manually.

## Good Default Prompts for Context7

- "PyYAML docs for `safe_load` versus `load`."
- "PyYAML docs for stable readable dumps with `sort_keys=False`."
- "PyYAML docs for multiple YAML documents and when to use them."

## Source Basis

- Primary Context7 source:
  `/yaml/pyyaml`
