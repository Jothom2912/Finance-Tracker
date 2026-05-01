from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure local app package and shared contracts are importable
ROOT = Path(__file__).resolve().parent
CONTRACTS = ROOT.parent / "shared" / "contracts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CONTRACTS))
# Also set PYTHONPATH env for subprocesses or tooling that rely on it
os.environ.setdefault("PYTHONPATH", os.pathsep.join([str(ROOT), str(CONTRACTS)]))

import pytest


def main() -> int:
    return pytest.main(["tests/", "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
