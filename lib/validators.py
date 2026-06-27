"""validators.py — 可复用的 lint / 校验基础设施。

从 lint-opc-carriers.py 提取, 为所有 YAML 治理校验脚本提供统一框架。

用法:
    from lib.validators import LintReport
    report = LintReport()
    report.err("file.yaml", "missing field: id")
    report.warn("file.yaml", "unusual status")
    report.ok("file.yaml", "parsed successfully")
    if report.has_errors:
        sys.exit(1)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class LintReport:
    """统一的 lint 报告收集器, 支持 err / warn / ok 三级。"""

    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []
        self.checks: list[tuple[str, str]] = []

    def err(self, where: str, msg: str) -> None:
        """记录错误 (导致 exit 1)。"""
        self.errors.append((where, msg))

    def warn(self, where: str, msg: str) -> None:
        """记录警告 (strict 模式下导致 exit 1)。"""
        self.warnings.append((where, msg))

    def ok(self, where: str, msg: str) -> None:
        """记录通过的检查。"""
        self.checks.append((where, msg))

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def print_summary(self, title: str = "Lint", verbose: bool = False) -> None:
        """打印汇总报告。"""
        print("=" * 70)
        print(f" {title}")
        print("=" * 70)
        for where, msg in self.checks:
            if verbose:
                print(f"  ✓ {where} — {msg}")
        for where, msg in self.warnings:
            print(f"  ⚠ {where} — {msg}")
        for where, msg in self.errors:
            print(f"  ✗ {where} — {msg}")
        print("-" * 70)
        print(f" Errors: {len(self.errors)}   Warnings: {len(self.warnings)}")
        print("=" * 70)

    def exit_code(self, strict: bool = False) -> int:
        """返回退出码: 0=pass, 1=fail。strict 模式下 warning 也算 fail。"""
        if self.has_errors:
            return 1
        if strict and self.has_warnings:
            return 1
        return 0


def require_text(text: str, needle: str, where: str, report: LintReport) -> None:
    """检查文本中是否包含指定字符串, 不包含则报 error。"""
    if needle not in text:
        report.err(where, f"missing reference: {needle}")


def require_exists(path: Path, where: str, report: LintReport) -> None:
    """检查文件/目录是否存在, 不存在则报 error。"""
    if not path.exists():
        report.err(where, f"path does not exist: {path}")


def require_fields(data: dict[str, Any], fields: list[str], where: str, report: LintReport) -> None:
    """检查 dict 中是否包含所有必填字段, 缺失则报 error。"""
    for f in fields:
        if f not in data:
            report.err(where, f"missing required field: {f}")


def require_list_min(data: dict[str, Any], key: str, minimum: int, where: str, report: LintReport) -> list[Any] | None:
    """检查 dict[key] 是否为 list 且长度 >= minimum。
    
    Returns:
        list if valid, None if invalid (error already recorded)
    """
    val = data.get(key)
    if not isinstance(val, list):
        report.err(where, f"{key} must be a list")
        return None
    if len(val) < minimum:
        report.err(where, f"{key} count = {len(val)} (need >= {minimum})")
        return None
    return val


def match_pattern_list(items: list[Any], pattern: re.Pattern, key: str, where: str, report: LintReport) -> None:
    """检查 list 中每个字符串是否匹配正则, 不匹配则报 error。"""
    for item in items:
        if not isinstance(item, str) or not pattern.match(item):
            report.err(where, f"{key} '{item}' violates naming rule: {pattern.pattern}")
