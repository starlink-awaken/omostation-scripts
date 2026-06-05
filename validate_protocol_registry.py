#!/usr/bin/env python3
"""Validate L0-registry.yaml — eCOS Protocol Registry SSOT.

Checks:
- Every protocol entry has required fields: name, version, category, status, description
- No duplicate protocol names
- Status values are in allowed set
- Category values are in allowed set
"""
import os
import sys
from pathlib import Path

import yaml


REQUIRED_FIELDS = ["name", "version", "category", "status", "description"]
ALLOWED_STATUSES = {"active", "draft", "deprecated", "planned", "partial"}
ALLOWED_CATEGORIES = {
    "agent-communication", "model-access", "service-discovery",
    "state-sync", "identity-auth", "data-exchange", "orchestration",
    "runtime-management", "governance",
}

REPO_ROOT = Path(__file__).resolve().parent
REGISTRY = REPO_ROOT / "projects" / "runtime" / "protocols" / "L0-registry.yaml"


def main() -> int:
    errors = []
    if not REGISTRY.exists():
        print(f"❌ Registry not found: {REGISTRY}")
        return 1

    with open(REGISTRY) as f:
        data = yaml.safe_load(f)

    protocols = data.get("protocols", [])
    if not isinstance(protocols, list):
        print("❌ protocols field is not a list")
        return 1

    seen_names: set[str] = set()
    for i, proto in enumerate(protocols):
        if not isinstance(proto, dict):
            errors.append(f"Protocol #{i}: not a dict")
            continue

        name = proto.get("name", f"#{i}")
        for field in REQUIRED_FIELDS:
            if field not in proto:
                errors.append(f"'{name}': missing required field '{field}'")

        if name in seen_names:
            errors.append(f"'{name}': duplicate protocol name")
        seen_names.add(name)

        status = proto.get("status", "")
        if status not in ALLOWED_STATUSES:
            errors.append(f"'{name}': invalid status '{status}', allowed: {sorted(ALLOWED_STATUSES)}")

        cat = proto.get("category", "")
        if cat and cat not in ALLOWED_CATEGORIES:
            errors.append(f"'{name}': invalid category '{cat}', allowed: {sorted(ALLOWED_CATEGORIES)}")

    if errors:
        print(f"❌ {len(errors)} validation error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"✅ {len(protocols)} protocols validated, 0 errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
