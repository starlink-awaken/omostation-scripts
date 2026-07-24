#!/usr/bin/env python3
"""检查治理 SSOT 引用链是否完整。

纯文本校验, 不依赖 PyYAML。
"""

from __future__ import annotations

from lib.bootstrap import workspace_root
from lib.paths import (
    OMO_DIR,
    REGISTRY_DIR,
    X1_POLICIES,
    X2_FRESHNESS,
    X3_VALUE,
    X4_CONSISTENCY,
)

WORKSPACE = workspace_root()

REGISTRY = REGISTRY_DIR / "omo-governance-surfaces.yaml"
X1 = X1_POLICIES
X2 = X2_FRESHNESS
X3 = X3_VALUE
X4 = X4_CONSISTENCY
L0 = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry" / "L0-constraints.yaml"
STANDARD = OMO_DIR / "standards" / "omo-governance-surfaces.md"
AGENTS = WORKSPACE / "AGENTS.md"
OMO_INDEX = OMO_DIR / "INDEX.md"
PANORAMA = WORKSPACE / "docs" / "PANORAMA.md"

CHAIN_PATHS = (
    ".omo/standards/omo-governance-surfaces.md",
    ".omo/_truth/registry/omo-governance-surfaces.yaml",
    ".omo/_truth/x1-governance-policies.yaml",
    ".omo/_truth/x2-freshness-rules.yaml",
    ".omo/_truth/x3-value-stack.yaml",
    ".omo/_truth/x4-consistency-rules.yaml",
    "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml",
)
def _assert_contains(text: str, needle: str, label: str, violations: list[str]) -> None:
    if needle not in text:
        violations.append(f"{label}: missing reference: {needle}")


def main() -> int:
    violations: list[str] = []

    registry_text = REGISTRY.read_text(encoding="utf-8")
    for needle in (
        "standards_ref:",
        ".omo/standards/omo-governance-surfaces.md",
        "ssot_refs:",
        "x1_policy: .omo/_truth/x1-governance-policies.yaml",
        "x2_freshness: .omo/_truth/x2-freshness-rules.yaml",
        "x3_value: .omo/_truth/x3-value-stack.yaml",
        "x4_consistency: .omo/_truth/x4-consistency-rules.yaml",
        "l0_constraints: projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml",
        "documentation_contract:",
        "- AGENTS.md",
        "- .omo/INDEX.md",
        "- docs/PANORAMA.md",
        "- .omo/standards/omo-governance-surfaces.md",
    ):
        _assert_contains(registry_text, needle, "registry", violations)

    for path, label, required in (
        (X1, "x1", ("documentation_contract:", "ssot_role:", "derived_consumers:", "- AGENTS.md")),
        (X2, "x2", ("documentation_contract:", "ssot_role:", "derived_consumers:", "- AGENTS.md")),
        (X3, "x3", ("documentation_contract:", "ssot_role:", "derived_consumers:", "- AGENTS.md")),
        (X4, "x4", ("documentation_contract:", "ssot_role:", "derived_consumers:", "- AGENTS.md")),
    ):
        text = path.read_text(encoding="utf-8")
        for needle in required:
            _assert_contains(text, needle, label, violations)

    standard_text = STANDARD.read_text(encoding="utf-8")
    for needle in CHAIN_PATHS:
        _assert_contains(standard_text, needle, "standard", violations)

    agents_text = AGENTS.read_text(encoding="utf-8")
    for needle in (
        ".omo/_truth/x1-governance-policies.yaml",
        ".omo/_truth/x2-freshness-rules.yaml",
        ".omo/_truth/x3-value-stack.yaml",
        ".omo/_truth/x4-consistency-rules.yaml",
        "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml",
        ".omo/_truth/registry/omo-governance-surfaces.yaml",
        ".omo/standards/omo-governance-surfaces.md",
    ):
        _assert_contains(agents_text, needle, "AGENTS.md", violations)

    omo_index_text = OMO_INDEX.read_text(encoding="utf-8")
    for needle in (
        "standards/omo-governance-surfaces.md",
        "_truth/registry/omo-governance-surfaces.yaml",
        "_truth/x1-governance-policies.yaml",
        "_truth/x2-freshness-rules.yaml",
        "_truth/x3-value-stack.yaml",
        "_truth/x4-consistency-rules.yaml",
    ):
        _assert_contains(omo_index_text, needle, ".omo/INDEX.md", violations)

    panorama_text = PANORAMA.read_text(encoding="utf-8")
    for needle in (
        "/.omo/standards/omo-governance-surfaces.md",
        "/.omo/_truth/registry/omo-governance-surfaces.yaml",
        "/.omo/_truth/x1-governance-policies.yaml",
        "/projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml",
    ):
        _assert_contains(panorama_text, needle, "docs/PANORAMA.md", violations)

    # Ensure L0 actually contains governance-surface-related constraints.
    l0_text = L0.read_text(encoding="utf-8")
    for needle in ("CR-OMO-SURFACE-01", "CR-OMO-SURFACE-02", "CR-C2G-INGRESS-01", "CR-OMO-DIRECT-IO-01"):
        _assert_contains(l0_text, needle, "L0-constraints", violations)

    if violations:
        for violation in violations:
            print(violation)
        print(f"ssot-reference-integrity: FAIL ({len(violations)} violations)")
        return 1

    print("ssot-reference-integrity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
