"""ssot_checker.py — SSOT 文档内容校验框架。

从 6 个 check-*-ssot.py 脚本提取统一的 require/read/error 模式。

用法:
    from lib.ssot_checker import SSOTChecker
    from lib.bootstrap import workspace_root

    checker = SSOTChecker(root=workspace_root())

    # 检查文件中包含指定文本
    checker.require_text(".omo/_knowledge/design/foo.md", "required phrase", "foo check")

    # 检查文件中不包含禁止文本
    checker.forbid_text(".omo/_knowledge/design/foo.md", "forbidden phrase", "foo check")

    # 检查文件存在
    checker.require_exists(".omo/INDEX.md", "index check")

    if checker.has_errors:
        checker.print_report()
        sys.exit(1)
    print("PASS")
"""

from __future__ import annotations

from pathlib import Path


class SSOTChecker:
    """SSOT 文档内容校验器。

    收集 require/forbid/exists 检查结果, 统一输出。
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def read(self, rel: str) -> str:
        """读取文件内容 (相对 root 路径)。"""
        return (self.root / rel).read_text(encoding="utf-8")

    def require_text(self, rel: str, needle: str, label: str = "") -> None:
        """检查文件中包含指定文本, 不包含则报 error。"""
        try:
            text = self.read(rel)
        except FileNotFoundError:
            self.errors.append(f"{rel}: file not found ({label})" if label else f"{rel}: file not found")
            return
        if needle not in text:
            self.errors.append(f"{rel}: missing `{needle}` ({label})" if label else f"{rel}: missing `{needle}`")

    def require_all_text(self, rel: str, needles: tuple[str, ...], label: str = "") -> None:
        """检查文件中包含所有指定文本。"""
        for needle in needles:
            self.require_text(rel, needle, label)

    def forbid_text(self, rel: str, needle: str, label: str = "") -> None:
        """检查文件中不包含指定文本, 包含则报 error。"""
        try:
            text = self.read(rel)
        except FileNotFoundError:
            self.errors.append(f"{rel}: file not found ({label})" if label else f"{rel}: file not found")
            return
        if needle in text:
            self.errors.append(f"{rel}: forbidden `{needle}` ({label})" if label else f"{rel}: forbidden `{needle}`")

    def forbid_all_text(self, rel: str, needles: tuple[str, ...], label: str = "") -> None:
        """检查文件中不包含任何指定文本。"""
        for needle in needles:
            self.forbid_text(rel, needle, label)

    def require_exists(self, rel: str, label: str = "") -> None:
        """检查文件/目录存在, 不存在则报 error。"""
        path = self.root / rel
        if not path.exists():
            self.errors.append(f"{rel}: path does not exist ({label})" if label else f"{rel}: path does not exist")

    def check_targets(self, targets: dict[str, tuple[str, ...]]) -> None:
        """批量检查: 对每个文件检查 require 文本列表。

        Args:
            targets: {relative_path: (required_needle_1, required_needle_2, ...)}
        """
        for rel, needles in targets.items():
            self.require_all_text(rel, needles)

    def check_targets_with_forbidden(
        self,
        targets: dict[str, tuple[str, ...]],
        forbidden: tuple[str, ...] = (),
    ) -> None:
        """批量检查: require + forbidden。

        Args:
            targets: {relative_path: (required_needles...)}
            forbidden: 全局禁止文本列表 (对所有文件检查)
        """
        for rel, needles in targets.items():
            self.require_all_text(rel, needles)
            if forbidden:
                self.forbid_all_text(rel, forbidden)

    def print_report(self) -> None:
        """打印检查报告。"""
        if self.errors:
            print("FAIL")
            for err in self.errors:
                print(f"- {err}")
        else:
            print("PASS")

    def exit_code(self) -> int:
        """返回退出码: 0=pass, 1=fail。"""
        return 1 if self.has_errors else 0
