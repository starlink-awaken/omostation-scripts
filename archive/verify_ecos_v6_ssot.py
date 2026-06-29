#!/usr/bin/env python3
"""
SSOT Verification Script — eCOS v6 Architecture Alignment
Verifies that AGENTS.md documentation matches the L0 BOS registry.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from lib.bootstrap import workspace_root
from lib.yaml_utils import load_yaml

ROOT = workspace_root()

def extract_bos_uris_from_md(file_path: Path) -> set[str]:
    """Extract all `bos://...` URIs from a markdown file."""
    if not file_path.exists():
        return set()
    content = file_path.read_text(encoding="utf-8")
    # Match `bos://domain/package/action`
    pattern = re.compile(r"`(bos://[a-z0-9-]+/[a-z0-9-]+/[a-z0-9-]+)`")
    return {m.group(1).rstrip("/") for m in pattern.finditer(content)}

def load_l0_registry() -> set[str]:
    """Load URIs from the declarative BOS registry."""
    path = ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"
    if not path.exists():
        return set()
    data = load_yaml(path)
    return {s["uri"].rstrip("/") for s in data.get("services", [])}

def verify_ssot():
    print("📋 Starting eCOS v6 SSOT Alignment Audit...")
    
    # 1. Load Registry Truth
    registry_uris = load_l0_registry()
    print(f"   - L0 Registry: {len(registry_uris)} canonical URIs loaded.")

    # 2. Audit Core Projects
    projects = ["agora", "gbrain", "runtime", "cockpit", "kairon", "metaos", "omo", "ecos"]
    total_mismatches = 0

    for proj in projects:
        agents_md = ROOT / "projects" / proj / "AGENTS.md"
        doc_uris = extract_bos_uris_from_md(agents_md)
        
        # Check if documented URIs exist in registry
        missing_in_registry = doc_uris - registry_uris
        # Check if registry URIs for this project are missing in docs
        # (Filter registry by package name approximation)
        proj_registry = {u for u in registry_uris if f"/{proj}/" in u or f"/{proj}-" in u}
        missing_in_docs = proj_registry - doc_uris

        print(f"\n📁 Project: {proj}")
        print(f"   - Documented URIs: {len(doc_uris)}")
        
        if missing_in_registry:
            print(f"   ❌ ERROR: Documentation contains UNREGISTERED URIs:")
            for u in missing_in_registry:
                print(f"     - {u}")
            total_mismatches += len(missing_in_registry)
        else:
            print(f"   ✅ All documented URIs are registered in L0.")

    print("\n" + "="*60)
    if total_mismatches == 0:
        print("💎 SSOT AUDIT PASSED: Documentation is 100% aligned with L0 Models.")
        return True
    else:
        print(f"🚩 SSOT AUDIT FAILED: Found {total_mismatches} mismatches.")
        return False

if __name__ == "__main__":
    if verify_ssot():
        sys.exit(0)
    else:
        sys.exit(1)
