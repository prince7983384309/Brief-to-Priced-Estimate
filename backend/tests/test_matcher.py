from app.matcher import match_spec
from app.schemas import Dimensions, ExtractedSpec, Material, ProductType

SAMPLE_INVENTORY = [
    {"sku": "A", "product_type": "ring", "material": "gold", "gem_count": 5, "size": 7.0, "price": 450.0},
    {"sku": "B", "product_type": "ring", "material": "silver", "gem_count": 5, "size": 7.0, "price": 180.0},
    {"sku": "C", "product_type": "necklace", "material": "gold", "gem_count": 5, "size": 18.0, "price": 800.0},
]


def _spec(product_type=ProductType.RING, material=Material.GOLD, gem_count=5, size=7.0):
    return ExtractedSpec(
        product_type=product_type,
        material=material,
        gem_count=gem_count,
        dimensions=Dimensions(size=size, unit="US"),
    )


def test_exact_match_ranks_first():
    results = match_spec(_spec(), inventory=SAMPLE_INVENTORY, top_k=3)
    assert results[0].sku == "A"
    assert results[0].score == 1.0


def test_wrong_material_scores_lower_than_exact_match():
    results = match_spec(_spec(), inventory=SAMPLE_INVENTORY, top_k=3)
    scores_by_sku = {r.sku: r.score for r in results}
    assert scores_by_sku["A"] > scores_by_sku["B"]


def test_matching_is_deterministic():
    first_run = match_spec(_spec(), inventory=SAMPLE_INVENTORY, top_k=3)
    second_run = match_spec(_spec(), inventory=SAMPLE_INVENTORY, top_k=3)
    assert [r.sku for r in first_run] == [r.sku for r in second_run]
    assert [r.score for r in first_run] == [r.score for r in second_run]


def test_top_k_is_respected():
    results = match_spec(_spec(), inventory=SAMPLE_INVENTORY, top_k=1)
    assert len(results) == 1
