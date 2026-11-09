"""Report offline name-hint and model-supplied gold-candidate survival."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.character_hints import (
    evaluate_character_name_hints,
    evaluate_gold_candidate_auto_promotion,
    evaluate_gold_character_candidate_survival,
    evaluate_unlabeled_hint_auto_promotion,
)
from app.evaluation.story_intelligence import load_evaluation_cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check source-named character hints in the synthetic corpus; no AI calls."
    )
    parser.add_argument(
        "--corpus", type=Path, default=Path("evals/story_intelligence/v1/cases.json")
    )
    parser.add_argument(
        "--stage",
        choices=("hints", "cleaner", "promotion", "false-positives", "all", "both"),
        default="all",
    )
    args = parser.parse_args()
    cases = load_evaluation_cases(args.corpus)
    result = {
        **(
            {"name_hints": evaluate_character_name_hints(cases)}
            if args.stage in {"hints", "all", "both"}
            else {}
        ),
        **(
            {"gold_candidate_cleaner": evaluate_gold_character_candidate_survival(cases)}
            if args.stage in {"cleaner", "all", "both"}
            else {}
        ),
        **(
            {"gold_candidate_promotion": evaluate_gold_candidate_auto_promotion(cases)}
            if args.stage in {"promotion", "all", "both"}
            else {}
        ),
        **(
            {"unlabeled_hint_promotion": evaluate_unlabeled_hint_auto_promotion(cases)}
            if args.stage in {"false-positives", "all", "both"}
            else {}
        ),
    }
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
