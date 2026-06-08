#!/usr/bin/env python3
"""端口注册表保鲜检查 (CI script).
检查 protocols/port-registry.yaml 是否与代码中的实际端口引用一致.
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


def load_registry_ports() -> set[int]:
    """加载 port-registry.yaml 中的已注册端口。"""
    try:
        import yaml
        reg = WORKSPACE / "protocols" / "port-registry.yaml"
        data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
        return set(data.get("ports", {}).keys())
    except Exception:
        return set()


def load_env_only_ports() -> set[int]:
    """加载注册表 types 字段标记的 env-only 端口(代码用 env 变量注入,不硬编码)。"""
    try:
        import yaml
        reg = WORKSPACE / "protocols" / "port-registry.yaml"
        data = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
        return {int(p) for p, t in (data.get("types") or {}).items() if t == "env-only"}
    except Exception:
        return set()


def scan_code_ports() -> set[int]:
    """扫描项目代码中所有硬编码的端口定义 (非注释/非引用)。"""
    code_ports: set[int] = set()
    for py_file in WORKSPACE.glob("projects/*/src/**/*.py"):
        if any(x in str(py_file) for x in [".venv", "__pycache__", "_archived", "build/"]):
            continue
        try:
            for line in py_file.read_text(encoding="utf-8").split("\n"):
                # 只匹配端口赋值: port = 1234 或 port=1234
                if "port" in line.lower() and "=" in line:
                    for word in line.split():
                        if word.isdigit() and 1024 <= int(word) <= 65535:
                            code_ports.add(int(word))
        except Exception:
            pass
    return code_ports


def main() -> int:
    registry = load_registry_ports()
    code = scan_code_ports()
    env_only = load_env_only_ports()  # 端口在注册表,代码用 env 变量,不视为僵尸

    unregistered = code - registry
    # 僵尸条目排除 env-only 端口(显式声明只用 env,不硬编码 = 合规)
    stale = (registry - code) - env_only

    print(f"  Registry ports: {len(registry)}")
    print(f"  Code ports:     {len(code)}")

    violations = 0
    if unregistered:
        print(f"  ❌ 未注册端口 (需添加到 port-registry.yaml): {sorted(unregistered)}")
        violations += len(unregistered)
    else:
        print("  ✅ 所有代码端口已在 registry 注册")

    if stale:
        print(f"  ⚠️  Registry 僵尸条目 (代码中未使用): {sorted(stale)}")
        violations += len(stale)

    return 0 if violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
