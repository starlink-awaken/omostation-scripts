#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = ROOT / "projects" / "runtime" / "src"
LLM_GATEWAY_SRC = ROOT / "projects" / "llm-gateway" / "src"
OMO_SRC = ROOT / "projects" / "omo" / "src"
sys.path.insert(0, str(OMO_SRC))

from omo.omo_io import write_text_atomic


def _load_jsonl_last(path: Path) -> dict:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else {}


def main() -> int:
    sys.path.insert(0, str(RUNTIME_SRC))
    sys.path.insert(0, str(LLM_GATEWAY_SRC))
    sys.path.insert(0, str(OMO_SRC))

    os.environ["WORKSPACE"] = str(ROOT)
    audit_dir = ROOT / "projects" / "llm-gateway" / "audit"
    os.environ["LLM_GATEWAY_AUDIT_DIR"] = str(audit_dir)

    import llm_gateway.detection as detection
    import llm_gateway.registry_data_loader as registry_loader
    from runtime.executor.engine import AgentRuntime

    class DemoProvider:
        provider_name = "anthropic"
        default_model = "claude-sonnet-4"

        def is_available(self) -> bool:
            return True

        async def generate(self, request):
            return SimpleNamespace(
                content="demo-ok",
                provider="anthropic",
                model="claude-sonnet-4",
                finish_reason="stop",
                input_tokens=120,
                output_tokens=40,
            )

    original_detect = detection.detect_backends
    original_route = registry_loader.route_role_request
    original_estimate = registry_loader.estimate_model_cost
    detection.detect_backends = lambda: [DemoProvider()]
    registry_loader.route_role_request = lambda role, required_capabilities=None: SimpleNamespace(
        provider_name="anthropic",
        model=SimpleNamespace(id="anthropic/claude-sonnet-4", name="claude-sonnet-4"),
        reasoning="Matched demo route anthropic/claude-sonnet-4",
    )
    registry_loader.estimate_model_cost = lambda model_id, input_tokens, output_tokens: 0.02 if input_tokens < 200 else 0.25

    try:
        runtime = AgentRuntime()

        # E4: successful call writes audit trail
        success = runtime.run_task("generate a concise summary", context={"task_id": "opc-p4-audit-demo"})
        if success.get("error"):
            raise RuntimeError(success["error"])
        audit_log = audit_dir / "llm_calls.jsonl"
        audit_record = _load_jsonl_last(audit_log)

        e4_dir = ROOT / ".omo" / "tasks" / "registry" / "done" / "OPC-P4-E4"
        write_text_atomic(
            e4_dir / "llm-audit-sample.json",
            json.dumps(audit_record, ensure_ascii=False, indent=2) + "\n",
        )

        rollout_out = ROOT / ".omo" / "_delivery" / "audit-rollout" / "2026-06-12-opc-p4.json"
        rollout_cmd = [
            "python3",
            "-m",
            "omo.cli",
            "audit-rollout",
            "--repos",
            "workspace:.",
            "--repos",
            "omo:projects/omo",
            "--include-metrics",
            "--output",
            str(rollout_out),
        ]
        rollout_result = subprocess.run(
            rollout_cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(OMO_SRC)},
            check=False,
        )
        write_text_atomic(
            e4_dir / "audit-rollout-summary.md",
            "\n".join(
                [
                    "# OPC P4 E4 rollout summary",
                    "",
                    f"- returncode: {rollout_result.returncode}",
                    f"- output: `{rollout_out}`",
                    "",
                    "```text",
                    rollout_result.stdout.strip(),
                    rollout_result.stderr.strip(),
                    "```",
                    "",
                ]
            ),
        )

        # E3: budget reject registers formal debt
        reject = runtime.run_task(
            "generate a concise summary",
            context={
                "task_id": "opc-p4-budget-demo",
                "llm_budget_usd": 0.01,
                "llm_max_output_tokens": 512,
            },
        )
        if "Budget policy blocked task opc-p4-budget-demo" not in reject.get("error", ""):
            raise RuntimeError(f"budget reject missing: {reject}")

        debt_path = ROOT / ".omo" / "debt" / "items" / "DEBT-OPC-P4-BUDGET-OPC-P4-BUDGET-DEMO.yaml"
        e3_dir = ROOT / ".omo" / "tasks" / "registry" / "done" / "OPC-P4-E3"
        write_text_atomic(
            e3_dir / "budget-reject-summary.md",
            "\n".join(
                [
                    "# OPC P4 E3 budget reject summary",
                    "",
                    f"- debt: `{debt_path}`",
                    f"- error: `{reject['error']}`",
                    "",
                ]
            ),
        )
    finally:
        detection.detect_backends = original_detect
        registry_loader.route_role_request = original_route
        registry_loader.estimate_model_cost = original_estimate

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
