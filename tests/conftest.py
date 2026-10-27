import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
for _path in (str(_ROOT), str(_TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
