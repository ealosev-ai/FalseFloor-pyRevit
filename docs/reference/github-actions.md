# GitHub Actions for RaisedFloor

## Why It Matters Here

- This repo already has a working CI/CD workflow in `.github/workflows/ci-cd.yml`.
- It covers:
  tests,
  lint,
  docs checks,
  Windows packaging into a release zip.
- For this project, GitHub Actions is not theory. It is part of shipping and regression control.

## What the Current Workflow Already Does

- Runs on `windows-latest`.
- Uses a Python-version matrix for tests.
- Runs separate jobs for:
  test,
  lint,
  build,
  docs.
- Builds a zip package in PowerShell and uploads it as an artifact.

## Practical Guidance from Docs

- Keep `push` and `pull_request` triggers filtered by both `branches` and `paths` when you want runs only for relevant changes.
- In workflow YAML, path filters should use repo-style `/` separators even when the runner OS is Windows.
- Use matrix jobs for Python version coverage and keep `include` only for special cases.
- Start jobs with `actions/checkout` so the repository exists in `$GITHUB_WORKSPACE`.
- Use `actions/setup-python` with pip caching and include all requirements files in `cache-dependency-path` if there is more than one.
- On Windows, `pwsh` is the default shell, but setting `defaults.run.shell: pwsh` explicitly makes intent clearer.

## PowerShell and Windows Notes

- Inside `run:` blocks on Windows, use PowerShell syntax:
  `$env:VAR`
  `Join-Path`
  `Compress-Archive`
- Prefer `Join-Path` over hand-built paths to avoid mixed separator bugs.
- Keep workflow YAML globs and path filters in `/` format, but inside PowerShell scripts use normal PowerShell path handling.

## Conditional Jobs and Artifacts

- Packaging jobs should be gated by `needs` plus an explicit `if`.
- Typical packaging condition for this repo shape:
  only on successful CI,
  only on `push`,
  only on `main` or tags.
- If a downstream job must run even after failures, use `if: ${{ always() }}`.
- For PR source branch conditions, use `github.head_ref`, not `github.ref`.

## Repo-Specific Notes

- The current workflow already uses the right broad structure for this project.
- Likely future cleanup points:
  include both `requirements.txt` and `requirements-dev.txt` in pip cache metadata,
  make shell defaults explicit,
  review whether artifact naming should include branch, tag, or commit SHA.
- Context7 surfaced newer action versions in examples, while this repo currently pins older but valid versions in some places. Treat version bumps as deliberate maintenance, not an automatic edit.

## Good Default Prompts for Context7

- "GitHub Actions docs for Windows PowerShell workflow syntax."
- "GitHub Actions docs for branch plus path filters on push and pull_request."
- "setup-python docs for pip cache with multiple requirements files."

## Source Basis

- Primary Context7 sources:
  `/websites/github_en_actions`
  `/actions/setup-python`
  `/actions/upload-artifact`
