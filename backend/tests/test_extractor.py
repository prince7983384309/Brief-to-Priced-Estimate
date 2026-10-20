from app import extractor
from app.schemas import ExtractedSpec


def test_malformed_json_falls_back_without_crashing(monkeypatch):
    monkeypatch.setattr(extractor, "call_llm_for_extraction", lambda brief, model=None: "not valid json {{{")

    spec, extraction_method = extractor.extract_with_validation("gold ring with 5 gems")

    assert isinstance(spec, ExtractedSpec)
    assert extraction_method == extractor.EXTRACTION_METHOD_FALLBACK


def test_empty_response_falls_back_without_crashing(monkeypatch):
    monkeypatch.setattr(extractor, "call_llm_for_extraction", lambda brief, model=None: "")

    spec, extraction_method = extractor.extract_with_validation("")

    assert isinstance(spec, ExtractedSpec)
    assert extraction_method == extractor.EXTRACTION_METHOD_FALLBACK


def test_transport_error_falls_back_without_crashing(monkeypatch):
    def _raise(brief, model=None):
        raise RuntimeError("simulated API outage")

    monkeypatch.setattr(extractor, "call_llm_for_extraction", _raise)

    spec, extraction_method = extractor.extract_with_validation("silver bracelet")

    assert isinstance(spec, ExtractedSpec)
    assert extraction_method == extractor.EXTRACTION_METHOD_FALLBACK


def test_valid_json_on_primary_model_succeeds(monkeypatch):
    valid_json = (
        '{"product_type": "ring", "material": "gold", "gem_count": 5, '
        '"dimensions": {"size": 7, "unit": "US"}, "budget": null, "notes": null}'
    )
    monkeypatch.setattr(extractor, "call_llm_for_extraction", lambda brief, model=None: valid_json)

    spec, extraction_method = extractor.extract_with_validation("gold ring with 5 gems, size 7")

    assert extraction_method == extractor.EXTRACTION_METHOD_SUCCESS
    assert spec.gem_count == 5
    assert spec.material.value == "gold"
