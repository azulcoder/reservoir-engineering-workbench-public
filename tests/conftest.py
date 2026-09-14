"""Make the src-layout package and the shared oracles importable under pytest.

`scripts/check.py` does the equivalent for the standard-library runner. Keeping both
paths working means the test suite is runnable with a stock interpreter and, when the
development extra is installed, under pytest with no changes to the test files.
"""

from __future__ import annotations

import pathlib
import sys

_TESTS = pathlib.Path(__file__).resolve().parent
_SRC = _TESTS.parent / "src"
_SCRIPTS = _TESTS.parent / "scripts"

for _path in (str(_SRC), str(_TESTS), str(_SCRIPTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
