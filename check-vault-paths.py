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

from lib.bootstrap import workspace_root
from lib.yaml_utils import load_yaml

try:
    import yaml
except ImportError:
    print("ERROR: 需要 pyyaml (uv pip install pyyaml)", file=sys.stderr)
    sys.exit(1)

# ── SSOT 文件定位 ──────────────────────────────
SSOT_CANDIDATES = [
    workspace_root() / "protocols" / "vault-paths.yaml",  # omostation/protocols/
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
    return load_yaml(p) or {}


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
    r"/check-vault-paths\.py$",      # 自匹配(本检测器代码含禁用模式字符串)
    r"/protocols/vault-paths\.yaml$",
    r"/vault-paths\.yaml$",          # 任意路径的 vault-paths.yaml(SSOT 自己声明禁用模式是合规的)
    r"/_archive/",
    r"/_archive/",
    r"/node_modules/",
    r"/\.venv/",
    r"/venv/",
    r"\.omo/capabilities/",      # PAI 框架运行时测试数据
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

PORT_SSOT_PATH = workspace_root() / "protocols" / "port-registry.yaml"
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
    data = load_yaml(PORT_SSOT_PATH) or {}
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
            # 排除整行注释(# 开头 / # ... inline)/纯字符串示例
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            for pat in PORT_HARDCODED_TYPES:
                m = re.search(pat, line)
                if not m:
                    continue
                # 提取数字
                num = next((int(x) for x in re.findall(r"\d{3,5}", m.group(0)) if 1024 <= int(x) <= 65535), None)
                if num and num not in ssot_ports:
                    violations.append((f, lineno, num, line.strip()[:80]))
    return violations


# ── 端口硬编码 baseline (增量 enforce) ──────────────────
# 历史: 子模块内部已有端口硬编码 (kairon 8765 / agora 8080 等) 属治理边界外.
# baseline 锚定已知历史 → 增量 (新 file:port) 才 fail, 全景容忍.
# DRY 对齐 omo-logs-audit baseline 模式 (.omo/_knowledge/_audit_baseline.json).
PORT_BASELINE_PATH = workspace_root() / "protocols" / "port-hardcode-baseline.yaml"


def load_port_baseline() -> set[str]:
    """读 baseline 锚点. 返回 {relpath:port} 集合; 文件不存在则空集 (全景严格模式)."""
    if not PORT_BASELINE_PATH.exists():
        return set()
    data = load_yaml(PORT_BASELINE_PATH) or {}
    return set(data.get("entries", []))


def write_port_baseline(violations: list[tuple[Path, int, int, str]]) -> int:
    """把当前端口违规刷新进 baseline (锚定已知历史). 返回锚定条数."""
    entries = sorted({f"{f}:{p}" for f, _, p, _ in violations})
    payload = {
        "comment": "端口硬编码 baseline (历史已知, 增量 file:port 才 fail). 刷新: python3 scripts/check-vault-paths.py --baseline-init",
        "count": len(entries),
        "entries": entries,
    }
    PORT_BASELINE_PATH.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return len(entries)


# ── 主入口 ──────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(prog="check-vault-paths")
    ap.add_argument("--check", action="store_true", help="反 sed 扫描(路径)")
    ap.add_argument("--check-ports", action="store_true", help="端口硬编码扫描")
    ap.add_argument("--resolve", metavar="KEY", help="解析路径键")
    ap.add_argument("--validate", action="store_true", help="校验必填字段")
    ap.add_argument("--all", action="store_true", help="全跑(check + validate)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--baseline-init", action="store_true", help="端口: 把当前违规写入 baseline (刷新锚点, 隐含 --check-ports)")
    ap.add_argument("--strict", action="store_true", help="端口: 忽略 baseline, 全景严格扫描")
    args = ap.parse_args()

    if args.baseline_init:
        args.check_ports = True  # --baseline-init 隐含端口扫描

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
        # 去重 by file:port
        by_file: dict[Path, set[int]] = {}
        for f, ln, p, _ in port_violations:
            by_file.setdefault(f, set()).add(p)
        all_hits = {f"{f}:{p}" for f, ports in by_file.items() for p in ports}

        if args.baseline_init:
            n = write_port_baseline(port_violations)
            if not args.json:
                print(f"✅ 端口 baseline 已刷新: {n} 处锚定 → {PORT_BASELINE_PATH.name}")
            port_rc = 0
        else:
            # baseline 增量: 非严格模式 → 只对增量 fail; --strict 则全景严格
            baseline = set() if args.strict else load_port_baseline()
            delta = sorted(all_hits - baseline)
            tolerated = len(all_hits) - len(delta)
            if delta:
                if not args.json:
                    print(f"\n❌ 端口硬编码增量 {len(delta)} 处 (全景 {len(all_hits)}, baseline 容忍 {tolerated}):")
                    for hit in delta:
                        print(f"  {hit}")
                    print("     → 改用 protocols/port-registry.yaml + env 注入, 或 --baseline-init 锚定")
                port_rc = 1
            else:
                if not args.json:
                    if all_hits:
                        print(f"\n✅ 端口硬编码: 增量 0 (全景 {len(all_hits)}, baseline 容忍 {tolerated})")
                    else:
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
