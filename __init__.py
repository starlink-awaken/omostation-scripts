"""Workspace scripts package.

NOTE: Historically scripts were executed directly from the scripts/ directory,
so many modules use absolute imports such as ``from lib.bootstrap import ...``.
When scripts is imported as a package (e.g. from OMO tests), insert the
scripts directory into sys.path so those imports continue to resolve.
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
