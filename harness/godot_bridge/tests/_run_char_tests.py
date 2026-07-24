"""Standalone test runner for character_controller tests (no pytest required).

Run:  python _run_char_tests.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_BRIDGE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BRIDGE_ROOT))

import test_character_controller as t  # noqa: E402

tests = [
    (name, fn)
    for name, fn in sorted(vars(t).items())
    if name.startswith("test_") and callable(fn)
]

passed = 0
failed = 0
for name, fn in tests:
    try:
        fn()
        passed += 1
        print(f"PASS  {name}")
    except Exception:
        failed += 1
        print(f"FAIL  {name}")
        traceback.print_exc()

print(f"\n==== {passed} passed, {failed} failed, {len(tests)} total ====")
sys.exit(1 if failed else 0)
