#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="${OMO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

if [[ ! -d "$ROOT_DIR/.omo" ]]; then
  echo "ERROR: $ROOT_DIR/.omo not found" >&2
  exit 1
fi

NOW_ARGS=()
if [[ -n "${OMO_NOW:-}" ]]; then
  NOW_ARGS=(--now "$OMO_NOW")
fi

cd "$ROOT_DIR"

python3 "$SCRIPT_DIR/sync_omo_state.py" "${NOW_ARGS[@]}"
python3 "$SCRIPT_DIR/check-state-goals-alignment.py"

python3 - <<'PY'
from pathlib import Path
import sys
import yaml

root = Path(".")
goals = yaml.safe_load((root / ".omo" / "goals" / "current.yaml").read_text(encoding="utf-8")) or {}
state = yaml.safe_load((root / ".omo" / "state" / "system.yaml").read_text(encoding="utf-8")) or {}
plans_readme = (root / ".omo" / "plans" / "README.md").read_text(encoding="utf-8")

phase = goals.get("phase")
wave = goals.get("current_wave")
errors: list[str] = []

if phase != state.get("current_phase"):
    errors.append(f"current phase mismatch: goals={phase!r} state={state.get('current_phase')!r}")
if wave != state.get("current_wave"):
    errors.append(f"current wave mismatch: goals={wave!r} state={state.get('current_wave')!r}")
if phase is None:
    errors.append("goals/current.yaml missing top-level phase")
else:
    program_ref = f"phase{phase}-program-plan.md"
    if program_ref not in plans_readme:
        errors.append(f"plans/README.md missing {program_ref}")
if wave is not None and phase is not None:
    wave_ref = f"phase{phase}-wave{wave}-execution-plan.md"
    if wave_ref not in plans_readme:
        errors.append(f"plans/README.md missing {wave_ref}")

if errors:
    for error in errors:
        print(f"ERROR: {error}")
    raise SystemExit(1)

print("System-goals-plans registry: OK")
PY

python3 "$SCRIPT_DIR/omo_experience.py" freshness "${NOW_ARGS[@]}"
python3 "$SCRIPT_DIR/omo_experience.py" control --budget-limit 2.5 "${NOW_ARGS[@]}"
