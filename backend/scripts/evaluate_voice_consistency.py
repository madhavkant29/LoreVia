"""Validate the synthetic Voice Review corpus or score real prediction files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.voice_consistency import (
    evaluate_voice_predictions,
    load_voice_evaluation_cases,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate evidence-backed Voice Review results.")
    parser.add_argument(
        "--corpus", type=Path, default=Path("evals/voice_consistency/v1/cases.json")
    )
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    cases = load_voice_evaluation_cases(args.corpus)
    if args.validate_only:
        print(json.dumps({"valid": True, "case_count": len(cases)}, indent=2))
        return
    if args.predictions is None:
        parser.error("--predictions is required unless --validate-only is used")
    payload = json.loads(args.predictions.read_text(encoding="utf-8"))
    predictions = payload.get("predictions") if isinstance(payload, dict) else payload
    if not isinstance(predictions, list):
        raise ValueError("Predictions must be a list or a predictions object.")
    print(json.dumps(evaluate_voice_predictions(cases, predictions), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
