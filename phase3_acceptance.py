#!/usr/bin/env python3
"""Run the curated Phase 3 acceptance suites and emit a markdown report."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


from lib.bootstrap import workspace_root
ROOT = workspace_root()
DEFAULT_REPORT = ROOT / ".omo" / "summaries" / "phase3-acceptance-report.md"


def _first_int(patterns: list[str], text: str) -> int:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _parse_counts(output: str, returncode: int) -> tuple[int, int]:
    passed = _first_int([r"(\d+)\s+passed", r"(\d+)\s+pass\b"], output)
    failed = _first_int([r"(\d+)\s+failed", r"(\d+)\s+fail\b"], output)
    if returncode != 0 and failed == 0:
        failed = 1
    return passed, failed


@dataclass(frozen=True)
class AcceptanceRun:
    name: str
    category: str
    cwd: Path
    command: list[str]
    timeout: int = 600
    env: dict[str, str] | None = None


def _with_pythonpath(*segments: str) -> dict[str, str]:
    paths = [str(ROOT / "projects" / "kairon" / segment) for segment in segments]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    return {"PYTHONPATH": os.pathsep.join(paths)}


def default_suites() -> list[AcceptanceRun]:
    return [
        AcceptanceRun(
            name="wksp-orchestration",
            category="workspace",
            cwd=ROOT / "projects" / "kairon",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "packages/wksp/src/wksp/tests/test_e2e_journey.py",
                "packages/wksp/src/wksp/tests/test_cli_mcp.py",
                "packages/wksp/src/wksp/tests/test_cli_research_publish.py",
                "packages/wksp/src/wksp/tests/test_cli_research_restore.py",
                "packages/wksp/src/wksp/tests/test_cli_research_reliability.py",
                "-q",
            ],
        ),
        AcceptanceRun(
            name="kos-skill-router",
            category="capabilities",
            cwd=ROOT / "projects" / "kairon",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "packages/kos/tests/test_mcp_server.py",
                "-q",
                "--tb=short",
                "-k",
                "SkillRouter",
            ],
            timeout=900,
            env=_with_pythonpath("packages/kos/src"),
        ),
        AcceptanceRun(
            name="minerva-cross-domain-research",
            category="capabilities",
            cwd=ROOT / "projects" / "kairon",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "packages/minerva/tests/unit/test_mcp_server.py",
                "-q",
                "--tb=short",
                "-k",
                "cross_domain_research or build_cross_domain_report",
            ],
            timeout=900,
            env=_with_pythonpath("packages/minerva/src"),
        ),
        AcceptanceRun(
            name="metaos-capability-tools",
            category="capabilities",
            cwd=ROOT / "projects" / "kairon",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "packages/metaos/tests/test_unit.py",
                "-q",
                "--tb=short",
                "-k",
                "CapabilityTools",
            ],
            timeout=900,
            env=_with_pythonpath("packages/metaos/src"),
        ),
        AcceptanceRun(
            name="iris-wechat-connector",
            category="capabilities",
            cwd=ROOT / "projects" / "kairon",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "packages/iris/tests/test_new_connectors.py",
                "-q",
                "--tb=short",
                "-k",
                "WeChatConnector",
            ],
            timeout=900,
            env=_with_pythonpath("packages/iris/src"),
        ),
        AcceptanceRun(
            name="gbrain-memory-and-recovery",
            category="recovery",
            cwd=ROOT / "projects" / "gbrain",
            command=[
                "bun",
                "test",
                "test/memory-tree-op.test.ts",
                "test/e2e/worker-abort-recovery.test.ts",
                "test/minions.test.ts",
            ],
            timeout=900,
        ),
    ]


def run_suite(run: AcceptanceRun) -> dict[str, object]:
    try:
        result = subprocess.run(
            run.command,
            cwd=run.cwd,
            capture_output=True,
            text=True,
            timeout=run.timeout,
            env={**os.environ, **(run.env or {})},
        )
    except FileNotFoundError as exc:
        output = str(exc)
        returncode = 127
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode()
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode()
        output = f"{stdout}\n{stderr}\nTIMEOUT".strip()
        returncode = 124
    else:
        output = (result.stdout or "") + (f"\n{result.stderr}" if result.stderr else "")
        returncode = result.returncode

    passed, failed = _parse_counts(output, returncode)
    status = "PASS" if returncode == 0 else "FAIL"
    return {
        "name": run.name,
        "category": run.category,
        "cwd": str(run.cwd),
        "command": " ".join(run.command),
        "returncode": returncode,
        "passed": passed,
        "failed": failed,
        "status": status,
        "output": output.strip(),
    }


def build_markdown_report(results: list[dict[str, object]]) -> str:
    total_passed = sum(int(item["passed"]) for item in results)
    total_failed = sum(int(item["failed"]) for item in results)
    lines = [
        "# Phase 3 acceptance report",
        "",
        "| Category | Suite | Status | Passed | Failed |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for item in results:
        status = item.get("status", "PASS" if int(item.get("returncode", 1)) == 0 else "FAIL")
        lines.append(
            f"| {item['category']} | {item['name']} | {status} | {item['passed']} | {item['failed']} |"
        )
    lines.extend(
        [
            "",
            f"Totals: passed={total_passed} failed={total_failed} suites={len(results)}",
            "",
            "## Commands",
        ]
    )
    for item in results:
        lines.append(f"- `{item['name']}`: `{item['command']}`")
    failing = [item for item in results if int(item["returncode"]) != 0 and item.get("output")]
    if failing:
        lines.extend(["", "## Failures"])
        for item in failing:
            lines.extend(
                [
                    "",
                    f"### {item['name']}",
                    "",
                    "```text",
                    str(item["output"]).strip(),
                    "```",
                ]
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true", help="Write markdown report to .omo/summaries/")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT, help="Override markdown output path")
    args = parser.parse_args(argv)

    results = [run_suite(run) for run in default_suites()]
    report = build_markdown_report(results)
    if args.write_report:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 0 if all(int(item["returncode"]) == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
