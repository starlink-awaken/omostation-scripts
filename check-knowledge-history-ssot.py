#!/usr/bin/env python3
from __future__ import annotations

import sys

from lib.bootstrap import workspace_root


ROOT = workspace_root()

TARGETS = {
    ".omo/_knowledge/summaries/4-plus-1-plus-3-architecture-mapping.md": (
        "历史架构映射参考 / reference only",
        "不是当前项目清单、当前能力计数、当前入口拓扑或当前健康状态 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/summaries/workspace-architecture-final.md": (
        "历史架构总览参考 / reference only",
        "不是当前项目矩阵、当前 MCP/CLI 数量、当前测试状态或当前健康度 SSOT",
        "/.omo/PROJECTS.yaml",
        "/.omo/state/system.yaml",
    ),
    ".omo/_knowledge/management/workflows/architecture-final-state-v2.md": (
        "历史最终态修订提案 / reference only",
        "不是当前项目数量、当前包边界、当前依赖真相或当前实施状态 SSOT",
        "/.omo/PROJECTS.yaml",
        "/.omo/standards/eCOS-v6-Architecture-Alignment.md",
    ),
    ".omo/_knowledge/management/workflows/code-quality-baseline-phase16.md": (
        "历史代码质量基线 / reference only",
        "不是当前包数量、当前 lint 状态、当前测试分布或当前硬编码风险 SSOT",
        "/.omo/PROJECTS.yaml",
    ),
    ".omo/_knowledge/management/workflows/dependency-audit-post-phase16.md": (
        "历史依赖审计记录 / reference only",
        "不是当前依赖拓扑、当前消费者数量或当前运行验证状态 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/management/workflows/ARCH-AUDIT-2026-05.md": (
        "历史架构审计记录 / reference only",
        "不是当前项目清单、当前测试状态、当前 Git 健康或当前架构结论 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/management/playbooks/append-only-log-schemas-2026-06-09.md": (
        "历史 schema 治理记录 / reference only",
        "不是当前运行频率、当前治理健康分或当前所有 consumer 实装真相 SSOT",
    ),
    ".omo/_knowledge/management/workflows/cross-repo-probe-runtime-metaos-2026-06-10.md": (
        "历史跨仓探查记录 / reference only",
        "不是当前 runtime/metaos 能力面、当前 MCP/CLI 数量或当前落地状态 SSOT",
    ),
    ".omo/_knowledge/management/workflows/governance-debt-lifecycle-2026-06-10.md": (
        "历史治理流程提炼 / reference only",
        "不是当前债务状态、当前流程执行结果或当前治理结论 SSOT",
    ),
    ".omo/_knowledge/management/workflows/omo-convergence-audit-2026-05-31.md": (
        "Historical convergence audit / reference only.",
        "is not the current status/goal/index truth SSOT",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
    ),
    ".omo/_knowledge/management/workflows/phase1-6-comprehensive-review.md": (
        "历史阶段综合评审 / reference only",
        "不是当前架构拓扑、当前工具数量、当前测试状态或当前阶段门禁 SSOT",
        "/.omo/PROJECTS.yaml",
        "/.omo/state/system.yaml",
    ),
    ".omo/_knowledge/management/workflows/phase8-analysis-verification.md": (
        "历史阶段分析与验证 / reference only",
        "不是当前任务状态、当前健康分或当前治理结论 SSOT",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
    ),
    ".omo/_knowledge/management/workflows/phase9-debt-cleanup-plan.md": (
        "历史债务规划输入 / reference only",
        "不是当前债务账本、当前阶段状态或当前健康分 SSOT",
        "/.omo/debt/registry.yaml",
        "/.omo/state/system.yaml",
    ),
    ".omo/_knowledge/management/workflows/phase10-cross-audit.md": (
        "历史交叉审计记录 / reference only",
        "不是当前 system/goals/control 状态或当前审计结论 SSOT",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
    ),
    ".omo/_knowledge/management/workflows/phase11-cross-audit.md": (
        "历史交叉审计基线 / reference only",
        "不是当前计划注册表、当前控制面或当前健康轨迹 SSOT",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
    ),
    ".omo/_knowledge/summaries/architecture-redteam-retrospective.md": (
        "历史复盘总结 / reference only",
        "不是当前项目覆盖率、当前安全状态或当前架构角色分配 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/summaries/full-architecture-audit-redteam-v3.md": (
        "历史架构审计与红队分析 / reference only",
        "不是当前项目数、当前架构层覆盖、当前 MCP/测试状态或当前安全面 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/summaries/phase24/phase20-25-residual-analysis.md": (
        "历史遗留分析记录 / reference only",
        "不是当前遗留工作、当前健康分或当前完成度 SSOT",
        "/.omo/state/system.yaml",
        "/.omo/goals/current.yaml",
    ),
    ".omo/_knowledge/management/guides/omo-extension-architecture-v1.md": (
        "历史扩展架构提案 / reference only",
        "不是当前 OMO/runtime/Agora 集成状态、当前 CLI 覆盖或当前治理能力 SSOT",
        "/.omo/PROJECTS.yaml",
        "/.omo/standards/omo-governance-surfaces.md",
    ),
    ".omo/_knowledge/management/workflows/p33-north-star.md": (
        "历史北极星决策输入 / reference only",
        "不是当前 BOS 域实现状态、当前健康分或当前审批结论 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/management/workflows/strategy-observability-v1.md": (
        "历史可观测性战略方案 / reference only",
        "不是当前日志/事件/指标/状态链路的实时实现真相 SSOT",
        "/.omo/standards/omo-governance-surfaces.md",
        "/.omo/state/system.yaml",
    ),
    ".omo/_knowledge/management/workflows/tool-heatmap-phase28.md": (
        "历史工具热力图审计 / reference only",
        "不是当前 Agora 路由覆盖、当前工具可达性或当前调用热度 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/management/guides/x-plane-architecture-design-v1.md": (
        "历史控制平面设计提案 / reference only",
        "不是当前 X1-X4 实装状态、当前健康分构成或当前控制面执行真相 SSOT",
        "/.omo/standards/omo-governance-surfaces.md",
        "/.omo/state/system.yaml",
    ),
    ".omo/_knowledge/management/workflows/opc-p2-t1-memory-boundary-2026-06-11.md": (
        "历史 OPC 设计输入 / reference only",
        "不是当前记忆边界实现状态、当前 owner 分配或当前系统事实 SSOT",
        "/.omo/PROJECTS.yaml",
        "/docs/PANORAMA.md",
    ),
    ".omo/_knowledge/management/workflows/opc-p2-t3-recall-flow-2026-06-11.md": (
        "历史 OPC 流程设计输入 / reference only",
        "不是当前 collect/ingest/search/output/archive 落地真相或当前验收结果 SSOT",
        "/.omo/state/system.yaml",
    ),
    ".omo/_knowledge/management/workflows/opc-p6-t1-evolution-loop-2026-06-11.md": (
        "历史 OPC 自演进设计输入 / reference only",
        "不是当前 radar/gap/task/swarm/audit/retrospective 实施状态或当前 Gate F 结论 SSOT",
        "/.omo/state/system.yaml",
    ),
}


def main() -> int:
    errors: list[str] = []
    for rel, needles in TARGETS.items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f"{rel}: file missing (stale path? P77 migration residue?)")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{rel}: missing `{needle}`")

    if errors:
        print("FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("PASS: historical knowledge docs are explicitly separated from live SSOT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
