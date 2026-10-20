"""FastAPI entrypoint: POST /analyze ties extraction -> matching -> CV ->
pricing -> confidence together. Swagger UI is auto-served at /docs.

Runnable two ways:
  python app/main.py                       (what this file's __main__ block does)
  uvicorn app.main:app --reload             (recommended for development)
"""
import sys
from pathlib import Path

# Makes "from app import ..." resolve whether this file is run directly
# (python app/main.py) or imported as a package (uvicorn app.main:app).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.confidence import PLAUSIBLE_GEM_COUNT_RANGE, build_field_confidence, evaluate_review
from app.extractor import extract_with_validation
from app.matcher import match_spec
from app.pricing import estimate_price
from app.schemas import AnalyzeResponse, ConfidenceLevel, CVEstimate, FieldConfidence
from app.vision import estimate_gem_count_classical, estimate_gem_count_vision_llm

app = FastAPI(
    title="Brief to Priced Estimate API",
    description=(
        "Turns a jewelry sales brief + optional reference photo into a structured "
        "spec, an inventory match, a gem-count estimate, and a priced estimate -- "
        "with a confidence level and review flags on every output."
    ),
    version="1.0.0",
)

# The frontend is a static page served from a different origin/port -- allow
# it to call this API. Dev-permissive by default; restrict via
# CORS_ALLOWED_ORIGINS in .env for anything beyond local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.CORS_ALLOWED_ORIGINS] if config.CORS_ALLOWED_ORIGINS != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analyze"])
async def analyze(brief: str = Form(...), image: Optional[UploadFile] = File(None)) -> AnalyzeResponse:
    spec, extraction_method = extract_with_validation(brief)
    field_confidence = build_field_confidence(spec, extraction_method)

    top_matches = match_spec(spec, top_k=3)

    cv_estimate: Optional[CVEstimate] = None
    cv_count: Optional[int] = None          # raw CV output, shown to the caller as-is
    trusted_cv_count: Optional[int] = None  # same value, but only if it passed a plausibility check
    if image is not None:
        image_bytes = await image.read()
        cv_count, cv_reason = estimate_gem_count_classical(image_bytes)

        low, high = PLAUSIBLE_GEM_COUNT_RANGE
        if cv_count is None:
            cv_level = ConfidenceLevel.LOW
        elif not (low <= cv_count <= high):
            # A busy/textured real photo can make Hough circle detection fire
            # thousands of false positives. Don't let an implausible count
            # propagate into pricing or the disagreement check below --
            # report it for transparency, but mark it untrusted.
            cv_level = ConfidenceLevel.LOW
            cv_reason = (
                f"{cv_reason}; {cv_count} is outside the plausible range {PLAUSIBLE_GEM_COUNT_RANGE} "
                "and is likely false positives from image noise/texture -- not used for pricing"
            )
        else:
            trusted_cv_count = cv_count
            llm_vs_cv_diff = abs(cv_count - spec.gem_count)
            cv_level = ConfidenceLevel.HIGH if llm_vs_cv_diff <= 1 else ConfidenceLevel.MEDIUM

        cv_estimate = CVEstimate(
            estimated_gem_count=cv_count,
            method="classical_cv_hough_circles",
            confidence=FieldConfidence(level=cv_level, reason=cv_reason),
        )

        if config.VISION_LLM_ENABLED:
            vision_llm_count, vision_llm_reason = estimate_gem_count_vision_llm(image_bytes)
            cv_estimate.vision_llm_estimate = vision_llm_count
            cv_estimate.vision_llm_reason = vision_llm_reason

    price_estimate = estimate_price(spec, top_matches[0] if top_matches else None, trusted_cv_count)

    review_required, review_reasons = evaluate_review(
        spec,
        field_confidence,
        top_matches,
        trusted_cv_count,
        cv_confidence=cv_estimate.confidence if cv_estimate is not None else None,
    )

    return AnalyzeResponse(
        extracted_spec=spec,
        extraction_method=extraction_method,
        field_confidence=field_confidence,
        top_matches=top_matches,
        cv_estimate=cv_estimate,
        price_estimate=price_estimate,
        review_required=review_required,
        review_reasons=review_reasons,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
