"""Evaluation harness: runs the labeled test set through the service
in-process (no network hop needed) and reports the required metrics.

Run:
    python scripts/evaluate.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.confidence import build_field_confidence, evaluate_review  # noqa: E402
from app.extractor import extract_with_validation  # noqa: E402
from app.matcher import match_spec  # noqa: E402
from app.vision import estimate_gem_count_classical  # noqa: E402

TEST_CASES_PATH = ROOT / "data" / "test_cases.json"
IMAGES_DIR = ROOT / "images"
RESULTS_PATH = ROOT / "evaluation_report.json"

EXTRACTION_FIELDS = ["product_type", "material", "gem_count", "size"]


def _spec_value(spec, field: str):
    if field == "size":
        return spec.dimensions.size
    value = getattr(spec, field)
    return value.value if hasattr(value, "value") else value


def run_case(case: dict) -> dict:
    spec, extraction_method = extract_with_validation(case["brief"])
    field_confidence = build_field_confidence(spec, extraction_method)
    top_matches = match_spec(spec, top_k=3)

    cv_count = None
    if case.get("image"):
        image_path = IMAGES_DIR / case["image"]
        cv_count, _ = estimate_gem_count_classical(image_path.read_bytes())

    review_required, review_reasons = evaluate_review(spec, field_confidence, top_matches, cv_count)

    field_correct = {
        field: _spec_value(spec, field) == case["expected"].get(field)
        for field in EXTRACTION_FIELDS
    }

    top_skus = [m.sku for m in top_matches]
    expected_sku = case.get("expected_top_sku")
    top1_hit = expected_sku is not None and top_skus[:1] == [expected_sku]
    top3_hit = expected_sku is not None and expected_sku in top_skus[:3]

    count_error = None
    if case.get("expected_cv_gem_count") is not None and cv_count is not None:
        count_error = abs(cv_count - case["expected_cv_gem_count"])

    return {
        "id": case["id"],
        "extraction_method": extraction_method,
        "field_correct": field_correct,
        "top1_hit": top1_hit,
        "top3_hit": top3_hit,
        "cv_count": cv_count,
        "count_error": count_error,
        "review_required": review_required,
        "review_reasons": review_reasons,
    }


def summarize(results: list[dict]) -> dict:
    n = len(results)

    field_accuracy = {
        field: sum(r["field_correct"][field] for r in results) / n for field in EXTRACTION_FIELDS
    }

    matchable = [r for r in results if r["top1_hit"] is not None]
    top1_rate = sum(r["top1_hit"] for r in matchable) / len(matchable) if matchable else None
    top3_rate = sum(r["top3_hit"] for r in matchable) / len(matchable) if matchable else None

    count_errors = [r["count_error"] for r in results if r["count_error"] is not None]
    mae = sum(count_errors) / len(count_errors) if count_errors else None

    review_flag_rate = sum(r["review_required"] for r in results) / n

    return {
        "n_cases": n,
        "field_accuracy": field_accuracy,
        "match_top1_hit_rate": top1_rate,
        "match_top3_hit_rate": top3_rate,
        "count_mae": mae,
        "review_flag_rate": review_flag_rate,
    }


def main() -> None:
    cases = json.loads(TEST_CASES_PATH.read_text())
    results = [run_case(case) for case in cases]
    summary = summarize(results)

    report = {"summary": summary, "per_case": results}
    RESULTS_PATH.write_text(json.dumps(report, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"\nFull report written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
