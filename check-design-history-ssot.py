#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

from lib.bootstrap import workspace_root


ROOT = workspace_root()


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str, errors: list[str]) -> None:
    if needle not in text:
        errors.append(f"{label}: missing `{needle}`")


def require_exists(rel: str, label: str, errors: list[str]) -> None:
    if not (ROOT / rel).exists():
        errors.append(f"{label}: missing path `{rel}`")


def main() -> int:
    errors: list[str] = []

    master = read(".omo/_knowledge/design/MASTER-BLUEPRINT.md")
    require(master, "历史主蓝图 / reference", "MASTER-BLUEPRINT", errors)
    require(master, "不是当前运行时 Phase、项目清单、能力计数或健康分 SSOT", "MASTER-BLUEPRINT", errors)
    require(master, "/.omo/PROJECTS.yaml", "MASTER-BLUEPRINT", errors)

    debt = read(".omo/_knowledge/design/debt-cleanup-plan.md")
    require(debt, "不是当前债务账本或当前系统健康分 SSOT", "debt-cleanup-plan", errors)
    require(debt, "历史状态记录", "debt-cleanup-plan", errors)
    require(debt, "/.omo/debt/registry.yaml", "debt-cleanup-plan", errors)

    baseline = read(".omo/_knowledge/design/system-design-baseline.md")
    require(baseline, "Status: reference baseline", "system-design-baseline", errors)
    require(baseline, "not current execution truth", "system-design-baseline", errors)

    hermes = read(".omo/_knowledge/design/hermes-convergence-strategy.md")
    require(hermes, "本文档是历史阶段输入", "hermes-convergence-strategy", errors)
    require(hermes, "/.omo/PROJECTS.yaml", "hermes-convergence-strategy", errors)

    remediation_v1 = read(".omo/_knowledge/design/architecture-remediation-plan.md")
    require(remediation_v1, "不是当前项目状态、测试通过率、健康分或执行计划 SSOT", "architecture-remediation-plan", errors)
    require(remediation_v1, "/.omo/PROJECTS.yaml", "architecture-remediation-plan", errors)

    remediation_v2 = read(".omo/_knowledge/design/architecture-remediation-plan-v2.md")
    require(remediation_v2, "不是当前系统健康、当前债务状态或当前执行面的权威来源", "architecture-remediation-plan-v2", errors)
    require(remediation_v2, "/.omo/debt/registry.yaml", "architecture-remediation-plan-v2", errors)

    strategic = read(".omo/_knowledge/design/omostation-strategic-architecture-v2.md")
    require(strategic, "历史阶段的战略规划输入", "omostation-strategic-architecture-v2", errors)
    require(strategic, "不是当前项目清单、当前架构事实或当前执行许可 SSOT", "omostation-strategic-architecture-v2", errors)

    sharedbrain = read(".omo/_knowledge/design/sharedbrain-architecture-governance-plan.md")
    require(sharedbrain, "historical governance-planning artifact", "sharedbrain-architecture-governance-plan", errors)
    require(sharedbrain, "not the live authority", "sharedbrain-architecture-governance-plan", errors)
    require(sharedbrain, "Historical location:", "sharedbrain-architecture-governance-plan", errors)

    insights = read(".omo/_knowledge/design/INSIGHTS-AND-ROADMAP.md")
    require(insights, "属于历史认知输入", "INSIGHTS-AND-ROADMAP", errors)
    require(insights, "不是当前项目状态、当前技术债或当前版本路线图 SSOT", "INSIGHTS-AND-ROADMAP", errors)

    phase5_entry = read(".omo/_knowledge/design/phase5-entry-architecture.md")
    require(phase5_entry, "历史阶段的入口设计分析", "phase5-entry-architecture", errors)
    require(phase5_entry, "/.omo/goals/current.yaml", "phase5-entry-architecture", errors)

    phase5_program = read(".omo/_knowledge/design/phase5-program-architecture.md")
    require(phase5_program, "historical program-architecture reference", "phase5-program-architecture", errors)
    require(phase5_program, "not the live authority", "phase5-program-architecture", errors)

    phase7_analysis = read(".omo/_knowledge/design/plans/phase7-planning-analysis-requirements.md")
    require(phase7_analysis, "历史阶段的规划分析输入", "phase7-planning-analysis-requirements", errors)
    require(phase7_analysis, "/.omo/tasks/active/", "phase7-planning-analysis-requirements", errors)

    sb_decision = read(".omo/_knowledge/summaries/SB-DECISION.md")
    require(sb_decision, "historical decision record", "SB-DECISION", errors)

    task_center = read(".omo/_knowledge/design/task-center-requirements.md")
    require(task_center, "历史阶段的需求与设计输入", "task-center-requirements", errors)
    require(task_center, "不是当前调度状态、当前 registry 真相或当前执行许可 SSOT", "task-center-requirements", errors)

    final_vision = read(".omo/_knowledge/design/plans/architecture-final-vision.md")
    require(final_vision, "属于长期参考输入", "architecture-final-vision", errors)
    require(final_vision, "不是当前项目清单、当前入口拓扑、当前能力计数或当前健康度 SSOT", "architecture-final-vision", errors)

    safe_mesh = read(".omo/_knowledge/design/plans/safe-mesh-rbac-deployment-roadmap.md")
    require(safe_mesh, "历史阶段的部署路线图输入", "safe-mesh-rbac-deployment-roadmap", errors)
    require(safe_mesh, "不是当前实现状态、当前权限面或当前 Mesh 事实 SSOT", "safe-mesh-rbac-deployment-roadmap", errors)

    mango = read(".omo/_knowledge/design/plans/gentle-toasting-mango.md")
    require(mango, "历史阶段的多 Phase 执行规划输入", "gentle-toasting-mango", errors)
    require(mango, "不是当前 phase 状态、当前债务状态或当前项目事实 SSOT", "gentle-toasting-mango", errors)

    federation = read(".omo/_knowledge/design/29-OMO联邦健康度、预算与Load-Shedding治理Playbook.md")
    require(federation, "历史提案草案", "federation-playbook", errors)
    require(federation, "不是当前联邦运行时、当前预算配置或当前治理状态 SSOT", "federation-playbook", errors)

    for rel in [
        ".omo/_knowledge/summaries/phase11/phase11-wave2-adr-ontoderive-inference-metatype.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave2-adr-ontoderive-scheme-metatype.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave2-adr-minerva-relation-metarelation.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave4-adr-kos-canonical-metatype.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave4-adr-eidos-protocol-contract-surface.md",
    ]:
        require(read(rel), "Historical ADR reference.", rel, errors)

    design_index = read(".omo/_knowledge/design/INDEX.md")
    require(design_index, "[debt-cleanup-plan.md](debt-cleanup-plan.md) | REFERENCE |", "design/INDEX", errors)
    require(design_index, "| reference baseline |", "design/INDEX", errors)
    require(design_index, "Hermes 收敛策略 — Phase 5 输入（历史输入", "design/INDEX", errors)
    require(design_index, "全景蓝图 v1.2（历史主蓝图", "design/INDEX", errors)
    require(design_index, "见解与路线图（历史洞察输入，不是当前路线图 SSOT） | reference", "design/INDEX", errors)
    require(design_index, "phase5-entry-architecture.md) | Phase 5 入口桥接设计", "design/INDEX", errors)
    require(design_index, "历史入口设计输入） | reference", "design/INDEX", errors)
    require(design_index, "plans/phase7-planning-analysis-requirements.md", "design/INDEX", errors)
    require(design_index, "历史规划输入） | reference", "design/INDEX", errors)
    require(design_index, "../summaries/SB-DECISION.md", "design/INDEX", errors)
    require(design_index, "历史决策记录） | reference", "design/INDEX", errors)

    for rel in [
        ".omo/_knowledge/design/plans/phase7-planning-analysis-requirements.md",
        ".omo/_knowledge/summaries/SB-DECISION.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave2-adr-ontoderive-inference-metatype.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave2-adr-ontoderive-scheme-metatype.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave2-adr-minerva-relation-metarelation.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave4-adr-kos-canonical-metatype.md",
        ".omo/_knowledge/summaries/phase11/phase11-wave4-adr-eidos-protocol-contract-surface.md",
    ]:
        require_exists(rel, "index-link-target", errors)

    plans = read(".omo/_knowledge/design/plans/README.md")
    require(plans, "历史全景主蓝图 + Post-Phase1 门禁输入", "plans/README", errors)
    require(plans, "历史参考基线", "plans/README", errors)
    require(plans, "🟢 REFERENCE", "plans/README", errors)

    if errors:
        print("FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("PASS: design history docs are explicitly downgraded from live SSOT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
