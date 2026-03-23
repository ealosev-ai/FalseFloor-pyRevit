# -*- coding: utf-8 -*-
"""Run ribbon smoke tests without coverage gate.

Useful for fast local regression checks:
    python run_smoke_tests.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(root / "tests" / "test_ribbon_smoke.py"),
        "--no-cov",
        "-q",
    ]
    return subprocess.call(cmd, cwd=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
