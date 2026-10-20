"""LLM extraction: calls the configured provider, then retries on a fallback
model, repairs partially-valid JSON, or degrades to a safe default -- so
malformed or empty model output never crashes a request.
"""
import json

from pydantic import ValidationError

from app import config
from app.schemas import ExtractedSpec

EXTRACTION_METHOD_SUCCESS = "llm_success"
EXTRACTION_METHOD_REPAIRED = "llm_repaired"
EXTRACTION_METHOD_FALLBACK = "fallback_default"

SYSTEM_PROMPT = (
    "You extract structured product specs from a jewelry sales brief. "
    "Respond with ONLY a JSON object (no markdown, no commentary) with keys: "
    "product_type (one of ring, necklace, bracelet, earrings, pendant, unknown), "
    "material (one of gold, silver, platinum, rose_gold, white_gold, unknown), "
    "gem_count (integer >= 0), "
    "dimensions (object with 'size' number-or-null and 'unit' string-or-null), "
    "budget (number or null), "
    "notes (short string or null)."
)


def _call_openai(brief: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": brief},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return completion.choices[0].message.content


def _call_anthropic(brief: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": brief}],
    )
    return message.content[0].text


def _call_gemini(brief: str, model: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(model, system_instruction=SYSTEM_PROMPT)
    response = gemini_model.generate_content(
        brief,
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
    )
    return response.text


def call_llm_for_extraction(brief: str, model: str | None = None) -> str:
    """Returns the raw text response from the configured LLM provider."""
    model = model or config.MODEL_NAME
    if config.LLM_PROVIDER == "anthropic":
        return _call_anthropic(brief, model)
    if config.LLM_PROVIDER == "gemini":
        return _call_gemini(brief, model)
    return _call_openai(brief, model)


def _try_parse_json(raw_text: str) -> dict | None:
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return None


def _validate(raw_json: dict) -> ExtractedSpec | None:
    try:
        return ExtractedSpec.model_validate(raw_json)
    except ValidationError:
        return None


def extract_with_validation(brief: str) -> tuple[ExtractedSpec, str]:
    """Always returns a valid ExtractedSpec, plus a label for how it got there."""
    try:
        raw_text = call_llm_for_extraction(brief, model=config.MODEL_NAME)
        parsed = _try_parse_json(raw_text)
        if parsed is not None:
            spec = _validate(parsed)
            if spec is not None:
                return spec, EXTRACTION_METHOD_SUCCESS
    except Exception:
        pass

    # Retry once on the fallback model: covers transient errors and models
    # that occasionally emit malformed JSON.
    try:
        raw_text = call_llm_for_extraction(brief, model=config.FALLBACK_MODEL_NAME)
        parsed = _try_parse_json(raw_text)
        if parsed is not None:
            spec = _validate(parsed)
            if spec is not None:
                return spec, EXTRACTION_METHOD_REPAIRED
            # Partial repair: keep whatever fields do validate, default the rest.
            repaired = {k: v for k, v in parsed.items() if k in ExtractedSpec.model_fields}
            spec = _validate(repaired)
            if spec is not None:
                return spec, EXTRACTION_METHOD_REPAIRED
    except Exception:
        pass

    return ExtractedSpec.safe_default(), EXTRACTION_METHOD_FALLBACK
