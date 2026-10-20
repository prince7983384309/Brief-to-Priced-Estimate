"""Per-field confidence levels, plus the logic that decides when a result
needs human review: low confidence anywhere, implausible values, or
CV/LLM disagreement.
"""
from app.extractor import (
    EXTRACTION_METHOD_FALLBACK,
    EXTRACTION_METHOD_REPAIRED,
    EXTRACTION_METHOD_SUCCESS,
)
from app.matcher import MIN_SCORE_THRESHOLD
from app.schemas import (
    ConfidenceLevel,
    ExtractedSpec,
    FieldConfidence,
    MatchCandidate,
    Material,
    ProductType,
)

PLAUSIBLE_GEM_COUNT_RANGE = (0, 200)
CV_LLM_DISAGREEMENT_TOLERANCE = 3

_BASE_LEVEL_BY_EXTRACTION_METHOD = {
    EXTRACTION_METHOD_SUCCESS: ConfidenceLevel.HIGH,
    EXTRACTION_METHOD_REPAIRED: ConfidenceLevel.MEDIUM,
    EXTRACTION_METHOD_FALLBACK: ConfidenceLevel.LOW,
}


def build_field_confidence(spec: ExtractedSpec, extraction_method: str) -> dict[str, FieldConfidence]:
    base_level = _BASE_LEVEL_BY_EXTRACTION_METHOD[extraction_method]
    base_reason = f"extraction_method={extraction_method}"

    confidence: dict[str, FieldConfidence] = {
        "product_type": FieldConfidence(level=base_level, reason=base_reason),
        "material": FieldConfidence(level=base_level, reason=base_reason),
        "gem_count": FieldConfidence(level=base_level, reason=base_reason),
        "dimensions": FieldConfidence(level=base_level, reason=base_reason),
    }

    if spec.product_type == ProductType.UNKNOWN:
        confidence["product_type"] = FieldConfidence(
            level=ConfidenceLevel.LOW, reason="model could not determine a product type"
        )

    if spec.material == Material.UNKNOWN:
        confidence["material"] = FieldConfidence(
            level=ConfidenceLevel.LOW, reason="model could not determine a material"
        )

    low, high = PLAUSIBLE_GEM_COUNT_RANGE
    if not (low <= spec.gem_count <= high):
        confidence["gem_count"] = FieldConfidence(
            level=ConfidenceLevel.LOW,
            reason=f"gem_count={spec.gem_count} is outside the plausible range {PLAUSIBLE_GEM_COUNT_RANGE}",
        )

    return confidence


def evaluate_review(
    spec: ExtractedSpec,
    field_confidence: dict[str, FieldConfidence],
    top_matches: list[MatchCandidate],
    cv_estimated_gem_count: int | None,
    cv_confidence: FieldConfidence | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if any(f.level == ConfidenceLevel.LOW for f in field_confidence.values()):
        reasons.append("one or more extracted fields have low confidence")

    if not top_matches or top_matches[0].score < MIN_SCORE_THRESHOLD:
        reasons.append(
            f"no inventory match scores at or above the minimum threshold ({MIN_SCORE_THRESHOLD})"
        )

    # cv_estimated_gem_count is only passed in when it already cleared the
    # plausibility check (see app/main.py) -- so this is purely a
    # CV-vs-LLM disagreement check, not a sanity check on the CV value itself.
    if cv_estimated_gem_count is not None:
        diff = abs(cv_estimated_gem_count - spec.gem_count)
        if diff > CV_LLM_DISAGREEMENT_TOLERANCE:
            reasons.append(
                f"CV gem count ({cv_estimated_gem_count}) and LLM gem count "
                f"({spec.gem_count}) disagree by {diff}"
            )

    # Separately: an implausible raw CV reading is worth flagging even if it
    # was excluded from pricing/disagreement above (e.g. a busy/textured
    # photo producing thousands of false-positive circle detections).
    if cv_confidence is not None and cv_confidence.level == ConfidenceLevel.LOW:
        reasons.append(f"CV gem-count estimate has low confidence: {cv_confidence.reason}")

    return (len(reasons) > 0, reasons)
