#!/usr/bin/env python3
"""Check that new Python files have 'from __future__ import annotations'."""

import sys
from pathlib import Path



def check_file(filepath: Path) -> bool:
    """Return True if file passes (has the import or is exempt)."""
    content = filepath.read_text(encoding="utf-8")

    # Exempt files that can't have the import
    exempt = [
        "__init__.py",  # May be empty or just re-exports
        "__main__.py",  # Entry points
        "conftest.py",  # Test config
    ]
    if filepath.name in exempt:
        return True

    # Exempt stub files (<=5 lines)
    if len(content.splitlines()) <= 5:
        return True

    # Check for the import
    return "from __future__ import annotations" in content


def main() -> int:
    errors = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        if path.suffix == ".py" and path.exists():
            if not check_file(path):
                errors.append(str(path))

    if errors:
        print(f"Missing 'from __future__ import annotations' in {len(errors)} file(s):")
        for e in errors:
            print(f"  {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
