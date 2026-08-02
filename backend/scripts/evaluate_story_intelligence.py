from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.story_intelligence import (
    evaluate_predictions,
    evaluate_rollout_gates,
    load_evaluation_cases,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate versioned LoreVia character and continuity predictions."
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("evals/story_intelligence/v1/cases.json"),
    )
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--check-gates", action="store_true")
    parser.add_argument("--production-dismissal-rate", type=float)
    args = parser.parse_args()

    cases = load_evaluation_cases(args.corpus)
    if args.validate_only:
        print(json.dumps({"valid": True, "case_count": len(cases)}, indent=2))
        return
    if args.predictions is None:
        parser.error("--predictions is required unless --validate-only is used")
    prediction_payload = json.loads(args.predictions.read_text(encoding="utf-8"))
    predictions = (
        prediction_payload.get("predictions")
        if isinstance(prediction_payload, dict)
        else prediction_payload
    )
    if not isinstance(predictions, list):
        raise ValueError("Predictions must be a list or a predictions object.")
    metrics = evaluate_predictions(cases, predictions)
    output: dict[str, object] = dict(metrics)
    if args.check_gates:
        gates = evaluate_rollout_gates(
            metrics,
            production_dismissal_rate=args.production_dismissal_rate,
        )
        output["rollout_gates"] = gates
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.check_gates and not gates["rollout_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
