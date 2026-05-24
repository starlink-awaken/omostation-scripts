#!/usr/bin/env python3
"""Run workspace tests and print an aggregate rich report."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ensure_rich() -> None:
    if importlib.util.find_spec("rich") is not None:
        return
    subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)


def first_int(patterns: list[str], text: str) -> int:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def parse_counts(output: str) -> tuple[int, int]:
    passed = first_int([r"(\d+)\s+passed", r"(\d+)\s+pass\b"], output)
    failed = first_int([r"(\d+)\s+failed", r"(\d+)\s+fail\b"], output)
    return passed, failed


@dataclass
class TestRun:
    name: str
    cwd: Path
    command: list[str]
    timeout: int


def run_test(test_run: TestRun) -> dict[str, object]:
    try:
        result = subprocess.run(
            test_run.command,
            cwd=test_run.cwd,
            capture_output=True,
            text=True,
            timeout=test_run.timeout,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        returncode = result.returncode
    except FileNotFoundError as exc:
        output = str(exc)
        returncode = 127
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "") + "\nTIMEOUT"
        returncode = 124

    passed, failed = parse_counts(output)
    return {
        "name": test_run.name,
        "command": " ".join(test_run.command),
        "cwd": str(test_run.cwd),
        "returncode": returncode,
        "passed": passed,
        "failed": failed,
        "output": output,
    }


def main() -> int:
    ensure_rich()

    from rich.console import Console
    from rich.table import Table

    runs = [
        TestRun("agentmesh", ROOT / "agentmesh", ["bun", "test"], 1800),
        TestRun("agora", ROOT / "agora", [sys.executable, "-m", "pytest", "tests/", "-q"], 1800),
    ]

    results = [run_test(run) for run in runs]

    table = Table(title="Test Aggregation Report", show_lines=False)
    table.add_column("Project", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    table.add_column("Passed", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Return", justify="right")
    table.add_column("Command", overflow="fold")

    for result in results:
        status = "✅ OK" if result["returncode"] == 0 else "❌ FAIL"
        table.add_row(
            str(result["name"]),
            status,
            str(result["passed"]),
            str(result["failed"]),
            str(result["returncode"]),
            str(result["command"]),
        )

    console = Console()
    console.print(table)

    total_passed = sum(int(result["passed"]) for result in results)
    total_failed = sum(int(result["failed"]) for result in results)
    console.print(f"[bold]Total:[/bold] passed={total_passed} failed={total_failed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
