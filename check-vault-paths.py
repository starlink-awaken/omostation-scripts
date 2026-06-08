#!/usr/bin/env python3
"""Vault Paths 反 sed 检测器 —— 治本"硬编码 ~/Documents/X/"。

X-Plane 战役发现 omostation 多处硬编码 ~/Documents/驾驶舱/ 引发
"老目录自建 + 老路径 mkdir"等治理债。本脚本 = SSOT 治本配套:

  1. 反向扫描全仓:任何硬编码 ~/Documents/驾驶舱/(无 @)立即报红
  2. 提供 resolve_path() 编程接口:代码不再硬编码,改读 SSOT
  3. 接 pre-commit / CI:新代码若写硬编码立即阻断

v2 扩展: 也扫端口硬编码(SSOT = protocols/port-registry.yaml),
区分 production vs test 模式(test 端口预期硬编码,不算错)。

用法:
    python3 check-vault-paths.py --check         # 反 sed 扫描(路径)
    python3 check-vault-paths.py --check-ports   # 端口硬编码扫描
    python3 check-vault-paths.py --resolve KEY  # 解析路径键
    python3 check-vault-paths.py --validate     # 校验必填字段
    python3 check-vault-paths.py --all          # 全跑(路径+端口+validate)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: 需要 pyyaml (uv pip install pyyaml)", file=sys.stderr)
    sys.exit(1)

# ── SSOT 文件定位 ──────────────────────────────
SSOT_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "protocols" / "vault-paths.yaml",  # omostation/protocols/
    Path.home() / ".config" / "omostation" / "vault-paths.yaml",           # XDG
]


def find_ssot() -> Path | None:
    """找 vault-paths.yaml(优先级:env > 当前仓 > XDG)。"""
    for p in SSOT_CANDIDATES:
        if p.exists():
            return p
    return None


def load_ssot() -> dict:
    p = find_ssot()
    if not p:
        print(f"ERROR: vault-paths.yaml 不存在(查 {SSOT_CANDIDATES})", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


# ── 路径解析 ──────────────────────────────────
def resolve_path(key: str, ssot: dict | None = None) -> str:
    """解析 SSOT 路径键,优先级: env > yaml > 报错。

    设计: 绝不静默 fallback 老路径。三选一都没 → 报错。
    """
    if ssot is None:
        ssot = load_ssot()
    env_key = f"VAULT_PATHS_{key.upper()}"
    if env_key in os.environ:
        return os.path.expanduser(os.environ[env_key])
    paths = ssot.get("paths", {})
    if key in paths and paths[key]:
        return os.path.expanduser(paths[key])
    print(
        f"ERROR: vault-paths.yaml 缺必填字段 '{key}'(env 也无 {env_key})",
        file=sys.stderr,
    )
    sys.exit(2)


# ── 反 sed 扫描 ──────────────────────────────
# 排除 SSOT 自身(声明的就是"禁用"),mof L0 元模型,arch 文档
EXCLUDE_PATTERNS = [
    r"/protocols/vault-paths\.yaml$",
    r"/_archive/",
    r"/node_modules/",
    r"/\.venv/",
    r"/venv/",
    r"/__pycache__/",
    r"/\.git/",
    r"/venv-",
    r"/_delivery/",
    r"/mof/m[12]/",      # mof 元模型定义可能含路径示例
    r"/CONV-",           # mof 节点
    r"/checkpoint-",
]


def is_excluded(path: Path) -> bool:
    s = str(path)
    return any(re.search(pat, s) for pat in EXCLUDE_PATTERNS)


# 真实硬编码"驾驶舱/"(无 @)模式 — 老 KEMS 路径必禁
HARDCODE_PATTERNS = [
    (r'"~?/?Documents/驾驶舱/', '"~/Documents/驾驶舱/" — 老 KEMS 路径(无 @),改用 @驾驶舱/'),
    (r'"~?/?Documents/驾驶舱/scripts/', '"~/Documents/驾驶舱/scripts/" — 老脚本目录,改用 @驾驶舱/scripts/'),
    (r'"~?/?Documents/驾驶舱/CARDS/', '"~/Documents/驾驶舱/CARDS/" — 老 CARDS 目录,改用 @驾驶舱/CARDS/'),
    (r"mkdir -p [^/]*驾驶舱", "mkdir 老 KEMS 路径,改用 @驾驶舱/(治本)"),
    (r"python3 ~/Documents/驾驶舱/", "python3 调老脚本,改用 @驾驶舱/scripts/"),
]


def scan_for_hardcodes(root: Path = Path(".")) -> list[tuple[Path, int, str, str]]:
    """扫全仓,返 (文件,行号,匹配内容,建议) 列表。"""
    violations = []
    for f in root.rglob("*"):
        if not f.is_file() or is_excluded(f):
            continue
        if f.suffix not in {".py", ".sh", ".yaml", ".yml", ".json", ".md"}:
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            for pat, advice in HARDCODE_PATTERNS:
                if re.search(pat, line):
                    violations.append((f, lineno, line.strip()[:80], advice))
    return violations


# ── 必填字段校验 ──────────────────────────────
def validate_required(ssot: dict) -> list[str]:
    required = ssot.get("required_fields", [])
    paths = ssot.get("paths", {})
    missing = [k for k in required if not paths.get(k)]
    return missing


# ── 端口硬编码扫描 ──────────────────────────────
# SSOT: protocols/port-registry.yaml 已有 12 个端口(自动驾驶舱战役治理)
# 扫:生产代码 .py 含 port=数字/port:int=数字 不在 SSOT 报红
# 测试目录 (tests/, test_, e2e, conftest, fixtures, dry-run 文档) 跳过

PORT_TEST_PATTERNS = [
    r"/tests/", r"/test_", r"/e2e/", r"/conftest\.py$", r"/fixtures/",
    r"\.test\.py$", r"/_test/", r"/test_", r"/unit_", r"/iso-test/",
    r"/dry-run", r"/test-output", r"/archive/",
    r"/_archived/", r"/_checkpoints/", r"/\.venv/", r"/venv/",
    r"/site-packages/", r"/__pycache__/", r"/\.git/",
]

PORT_SSOT_PATH = Path(__file__).resolve().parents[1] / "protocols" / "port-registry.yaml"
PORT_HARDCODED_TYPES = [
    r"port\s*[=:]\s*\d+",                # port=1234 / port: 1234
    r"port\s*int\s*=\s*\d+",            # port: int = 1234
    r"default\s*=\s*\d+",                # default=1234 (含命令行 default=9290)
    r'\[(\d+)\]',                         # 数组含端口 [9290]
]


def is_port_test_path(path: Path) -> bool:
    s = str(path)
    return any(re.search(pat, s) for pat in PORT_TEST_PATTERNS)


def load_port_ssot() -> set[int]:
    """读 SSOT 端口集(治本:SSOT 来源单一)。"""
    if not PORT_SSOT_PATH.exists():
        return set()
    data = yaml.safe_load(PORT_SSOT_PATH.read_text(encoding="utf-8")) or {}
    return {int(p) for p in data.get("ports", {}).keys() if str(p).isdigit()}


def scan_for_port_hardcodes(root: Path = Path("projects/")) -> list[tuple[Path, int, int, str]]:
    """扫生产代码端口硬编码(不在 SSOT)。

    返回 (文件, 行号, 端口, 行内容) 列表。
    """
    violations = []
    ssot_ports = load_port_ssot()
    for f in root.rglob("*"):
        if not f.is_file() or is_port_test_path(f):
            continue
        if f.suffix not in {".py", ".sh", ".yaml", ".yml"}:
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            for pat in PORT_HARDCODED_TYPES:
                m = re.search(pat, line)
                if not m:
                    continue
                # 提取数字
                num = next((int(x) for x in re.findall(r"\d{3,5}", m.group(0)) if 1024 <= int(x) <= 65535), None)
                if num and num not in ssot_ports:
                    violations.append((f, lineno, num, line.strip()[:80]))
    return violations


# ── 主入口 ──────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(prog="check-vault-paths")
    ap.add_argument("--check", action="store_true", help="反 sed 扫描(路径)")
    ap.add_argument("--check-ports", action="store_true", help="端口硬编码扫描")
    ap.add_argument("--resolve", metavar="KEY", help="解析路径键")
    ap.add_argument("--validate", action="store_true", help="校验必填字段")
    ap.add_argument("--all", action="store_true", help="全跑(check + validate)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    if args.resolve:
        print(resolve_path(args.resolve))
        return 0

    ssot = load_ssot()

    if args.all or args.check:
        violations = scan_for_hardcodes()
        if args.json:
            import json
            print(json.dumps(
                [{"file": str(f), "line": ln, "match": m, "advice": a}
                 for f, ln, m, a in violations],
                ensure_ascii=False, indent=2,
            ))
        else:
            if not violations:
                print("✅ 反 sed 扫描通过:全仓无 ~/Documents/驾驶舱/ 硬编码")
            else:
                print(f"❌ 硬编码命中 {len(violations)} 处:")
                for f, ln, m, a in violations:
                    print(f"  {f}:{ln}: {m}")
                    print(f"     → {a}")
        check_rc = 1 if violations else 0
    else:
        check_rc = 0

    if args.all or args.check_ports:
        port_violations = scan_for_port_hardcodes()
        if port_violations:
            # 去重 by file:port
            by_file = {}
            for f, ln, p, _ in port_violations:
                by_file.setdefault(f, set()).add(p)
            if not args.json:
                print(f"\n❌ 端口硬编码命中 {sum(len(v) for v in by_file.values())} 处 ({len(by_file)} 个文件):")
                for f, ports in sorted(by_file.items()):
                    print(f"  {f}: ports={sorted(ports)}")
                print("     → 改用 protocols/port-registry.yaml + env 注入(测试 fixture 除外)")
            port_rc = 1
        else:
            if not args.json:
                print("\n✅ 端口硬编码扫描通过(生产代码)")
            port_rc = 0
    else:
        port_rc = 0

    if args.all or args.validate:
        missing = validate_required(ssot)
        if missing:
            print(f"❌ vault-paths.yaml 缺必填字段: {missing}")
            validate_rc = 1
        else:
            print("✅ 必填字段校验通过")
            validate_rc = 0
    else:
        validate_rc = 0

    return max(check_rc, port_rc, validate_rc)


if __name__ == "__main__":
    sys.exit(main())
