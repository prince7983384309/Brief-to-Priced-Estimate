"""Turns the best inventory match plus the (CV or LLM) gem-count estimate
into a priced estimate.

This is a deliberately simple heuristic, not a real pricing engine: each
gem of difference from the matched SKU's own gem count shifts price by a
fixed fraction of that SKU's base price. It exists so "how much" has an
answer, with a confidence level attached, rather than just returning the
matched SKU's flat catalog price unadjusted.
"""
from app.schemas import ConfidenceLevel, ExtractedSpec, FieldConfidence, MatchCandidate, PriceEstimate

PRICE_PER_GEM_FRACTION = 0.04  # each gem of difference shifts price by ~4% of the base price
GEM_DIFF_HIGH_CONFIDENCE_TOLERANCE = 1
GEM_DIFF_MEDIUM_CONFIDENCE_TOLERANCE = 3
MIN_MATCH_SCORE_FOR_HIGH_CONFIDENCE = 0.7


def estimate_price(
    spec: ExtractedSpec,
    best_match: MatchCandidate | None,
    cv_gem_count: int | None,
) -> PriceEstimate | None:
    if best_match is None:
        return None

    # Prefer the CV-measured count when we have a photo; otherwise trust the
    # LLM-extracted count from the brief.
    actual_gem_count = cv_gem_count if cv_gem_count is not None else spec.gem_count
    gem_diff = actual_gem_count - best_match.gem_count
    price_per_gem = best_match.price * PRICE_PER_GEM_FRACTION
    estimated_price = max(best_match.price + gem_diff * price_per_gem, 0.0)

    reason = (
        f"base price from {best_match.sku} (${best_match.price:.2f}), adjusted by "
        f"{gem_diff:+d} gem(s) at ~${price_per_gem:.2f}/gem"
    )

    if (
        best_match.score >= MIN_MATCH_SCORE_FOR_HIGH_CONFIDENCE
        and abs(gem_diff) <= GEM_DIFF_HIGH_CONFIDENCE_TOLERANCE
    ):
        level = ConfidenceLevel.HIGH
    elif abs(gem_diff) <= GEM_DIFF_MEDIUM_CONFIDENCE_TOLERANCE:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    return PriceEstimate(
        estimated_price=round(estimated_price, 2),
        based_on_sku=best_match.sku,
        reason=reason,
        confidence=FieldConfidence(level=level, reason=reason),
    )
