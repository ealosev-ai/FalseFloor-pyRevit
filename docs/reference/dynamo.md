# Dynamo Notes

## Current Relevance

- This repository does not currently contain Dynamo graphs or Dynamo command bundles.
- Because of that, Dynamo is not a first-line source for normal `RaisedFloor.extension` work.
- For current tasks, prioritize Revit API docs first and pyRevit docs second.

## What Context7 Covers

- `/dynamods/dynamo` has broad coverage, but much of it is developer-internal:
  integration docs,
  element binding behavior,
  package tooling,
  node documentation generation,
  extension help-doc assets.
- `/dynamods/dynamorevit` exists, but the surfaced coverage is much thinner.
- The Dynamo Revit docs that surfaced are mostly about add-in setup, runtime wiring, and build configuration.

## What Could Still Be Useful Later

- Element binding lifecycle:
  reuse an existing Revit element when possible,
  update it in place,
  recreate only when necessary.
- Transaction patterns used in Dynamo integration code.
- Package and node documentation generation if the project ever ships Dynamo-facing assets.
- Revit runtime linkage if Dynamo-backed tooling is added later.

## When to Care

- Care now only if a task explicitly introduces:
  `.dyn` files,
  Dynamo-driven workflows,
  graph execution from pyRevit,
  or shared behavior between Dynamo graphs and pyRevit commands.
- Otherwise Dynamo is mostly background knowledge for this repo.

## Relation to pyRevit

- pyRevit extension metadata already knows about Dynamo-related script and engine constants.
- That means future Dynamo integration is technically plausible without redesigning the repo shape.
- It is still a separate decision. The current repository is a code-first pyRevit extension, not a Dynamo graph package.

## Source Basis

- Context7 libraries:
  `/dynamods/dynamo`
  `/dynamods/dynamorevit`
