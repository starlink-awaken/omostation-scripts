#!/usr/bin/env python3
"""检查 `_truth` 与 M1 governance 模型之间的映射完整性。

纯文本校验, 不依赖 PyYAML。
"""

from __future__ import annotations


from lib.bootstrap import workspace_root

WORKSPACE = workspace_root()

TRUTH_TO_M1 = {
    ".omo/_truth/x1-governance-policies.yaml": "projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-X1-CONSTRAINT.yaml",
    ".omo/_truth/x2-freshness-rules.yaml": "projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-X2-POLICY.yaml",
    ".omo/_truth/x3-value-stack.yaml": "projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-X3-VALUE.yaml",
    ".omo/_truth/x4-consistency-rules.yaml": "projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-X4-CONSISTENCY.yaml",
}

MODEL_GOVERNANCE = WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1/model/MODEL-GOVERNANCE.yaml"
SURFACE_STANDARD = ".omo/standards/omo-governance-surfaces.md"
SURFACE_REGISTRY = ".omo/_truth/registry/omo-governance-surfaces.yaml"
def main() -> int:
    violations: list[str] = []
    model_text = MODEL_GOVERNANCE.read_text(encoding="utf-8")

    for truth_rel, m1_rel in TRUTH_TO_M1.items():
        m1_text = (WORKSPACE / m1_rel).read_text(encoding="utf-8")

        if truth_rel not in m1_text:
            violations.append(f"{m1_rel}: missing truth reference to {truth_rel} in source/validator")
        if SURFACE_STANDARD not in m1_text:
            violations.append(f"{m1_rel}: missing governance surface standard reference")
        if truth_rel not in model_text:
            violations.append(f"MODEL-GOVERNANCE: missing model_driven_refs -> {truth_rel}")
        if m1_rel not in model_text:
            violations.append(f"MODEL-GOVERNANCE: missing model_driven_refs -> {m1_rel}")

    if SURFACE_STANDARD not in model_text:
        violations.append(f"MODEL-GOVERNANCE: missing model_driven_refs -> {SURFACE_STANDARD}")
    if SURFACE_REGISTRY not in model_text:
        violations.append(f"MODEL-GOVERNANCE: missing model_driven_refs -> {SURFACE_REGISTRY}")

    if violations:
        for v in violations:
            print(v)
        print(f"truth-m1-governance-mapping: FAIL ({len(violations)} violations)")
        return 1

    print("truth-m1-governance-mapping: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
