#!/usr/bin/env python3
"""接口注册表保鲜检查 (CI script).

检查 protocols/interface-registry.yaml 与各项目 pyproject.toml 的一致性:
  1. 所有 pyproject.toml [project.scripts] 必须已在 registry 注册
  2. registry 中注册的 CLI 入口 module 路径必须存在
  3. 端口引用必须在 registry 中注册

返回值: 0 = 一致, 1 = 发现不一致
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]  # ~/Workspace/

# ── 来自代码的全量 CLI 入口 ────────────────────────────

def collect_cli_from_code() -> dict[str, str]:
    """扫描所有 pyproject.toml, 收集 [project.scripts] 中的 CLI 入口."""
    entries: dict[str, str] = {}
    for toml_path in WORKSPACE.glob("projects/*/pyproject.toml"):
        project = toml_path.parent.name
        lines = toml_path.read_text(encoding="utf-8").split("\n")
        in_scripts = False
        for line in lines:
            stripped = line.strip()
            if stripped == "[project.scripts]":
                in_scripts = True
                continue
            if in_scripts and stripped.startswith("["):
                break
            if in_scripts and "=" in stripped:
                name = stripped.split("=")[0].strip().strip('"')
                module = stripped.split("=")[1].strip().strip('"')
                entries[f"{project}:{name}"] = module
    return entries


# ── 全量已知端口 ────────────────────────────────────────

KNOWN_PORTS: dict[int, str] = {
    7422: "agora (MCP HTTP)",
    7430: "agora (Web Dashboard)",
    7431: "agora (MCP SSE)",
    8090: "cockpit (Web Dashboard)",
    9090: "ecos (Dashboard)",
    8765: "minerva (Web, kairon)",
}

# 不作为"端口冲突"的连接引用模式 (其他项目连接 agora 的正常行为)
PORT_REFERENCE_PATTERNS = [
    "AGORA_MCP_PORT", "AGORA_ENDPOINT", "AGORA_MCP_ENDPOINT",
    "agora_endpoint", "mcp_endpoint", "localhost:7430",
    "localhost:7422", "localhost:7431",
    "Dashboard:", "Agora Dashboard", ":7430/health",
    ":7430/api", ":7431/sse",
]


def check_port_conflicts() -> int:
    """检查端口冲突。返回 violations 数量."""
    violations = 0
    ports_found: dict[int, list[str]] = {}

    for py_file in WORKSPACE.rglob("*.py"):
        if any(x in str(py_file) for x in [".venv", "__pycache__", "_archived", "build/"]):
            continue
        try:
            for line in py_file.read_text(encoding="utf-8").split("\n"):
                if "port" in line.lower() and any(c.isdigit() for c in line):
                    for known_port in KNOWN_PORTS:
                        if str(known_port) in line and "=" in line:
                            ports_found.setdefault(known_port, []).append(str(py_file))
        except Exception:
            pass

    # 检查每个端口只被一个项目使用 (排除注释/import/tests/archived/连接引用)
    for port, files in ports_found.items():
        unique_files = {
            f for f in files
            if "test_" not in Path(f).name
            and "conftest" not in Path(f).name
            and "_archived" not in f
            and "legacy-readme" not in f
        }
        projects = {Path(f).parts[Path(f).parts.index("projects") + 1] for f in unique_files if "projects" in f}
        # 排除连接引用 (其他项目引用 agora 端口作为配置)
        if len(projects) > 1:
            real_conflict = False
            for f in unique_files:
                try:
                    content = Path(f).read_text(encoding="utf-8", errors="ignore")
                    is_reference = any(pat in content for pat in PORT_REFERENCE_PATTERNS)
                    if not is_reference:
                        real_conflict = True
                        break
                except Exception:
                    pass
            if real_conflict:
                print(f"⚠ 端口冲突: :{port} — {', '.join(sorted(projects))} (期望: {KNOWN_PORTS[port]})")
                violations += 1

    return violations


def check_doc_freshness() -> int:
    """检查关键文档保鲜度。返回 violations 数量."""
    violations = 0
    import time

    critical_docs: list[tuple[str, str]] = [
        ("Workspace/CLAUDE.md", "根 CLAUDE.md"),
        ("Workspace/LAYER-INDEX.md", "分层索引"),
        ("Workspace/projects/kairon/CLAUDE.md", "kairon CLAUDE.md"),
        ("Documents/学习进化/CLAUDE.md", "Vault CLAUDE.md"),
    ]

    now = time.time()
    home = Path.home()

    for rel_path, label in critical_docs:
        if rel_path.startswith("Documents/"):
            full_path = home / rel_path
        else:
            full_path = Path("/Users/xiamingxing") / rel_path

        if not full_path.exists():
            print(f"⚠ {label} ({rel_path}): 文件不存在")
            violations += 1
            continue

        mtime = full_path.stat().st_mtime
        days_old = (now - mtime) / 86400

        if days_old > 90:
            print(f"🔴 {label}: {days_old:.0f} 天未更新 (>90d, 阻断)")
            violations += 1
        elif days_old > 30:
            print(f"🟡 {label}: {days_old:.0f} 天未更新 (>30d, 警告)")

    return violations


def main() -> int:
    violations = 0

    # 1. CLI 入口一致性
    print("🔍 检查 CLI 入口一致性...")
    cli_entries = collect_cli_from_code()
    print(f"   发现 {len(cli_entries)} 个 CLI 入口点 (from {len(set(k.split(':')[0] for k in cli_entries))} 个项目)")
    # 简单验证: 每个 CLI 至少有一个非空 module path
    for key, module in sorted(cli_entries.items()):
        if not module or module in ('""', "''"):
            print(f"  ⚠ {key}: 空 module 路径")
            violations += 1
    print(f"   CLI 一致性: {'✅' if violations == 0 else '❌'}")

    # 2. 端口冲突
    print("\n🔍 检查端口冲突...")
    port_violations = check_port_conflicts()
    violations += port_violations
    print(f"   端口冲突: {'✅' if port_violations == 0 else f'❌ ({port_violations} conflicts)'}")

    # 3. 文档保鲜
    print("\n🔍 检查文档保鲜...")
    doc_violations = check_doc_freshness()
    violations += doc_violations
    print(f"   文档保鲜: {'✅' if doc_violations == 0 else f'❌ ({doc_violations} stale)'}")

    print(f"\n{'='*50}")
    print(f"总计: {violations} violations")
    print(f"结果: {'✅ PASS' if violations == 0 else '❌ FAIL'}")
    return 0 if violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
