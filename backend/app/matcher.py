"""Deterministic, weighted matching of extracted specs against the inventory.
No LLM anywhere in this file.

Why this step is NOT an LLM call:
- Same input must always return the same ranked candidates. LLMs are not
  guaranteed to be reproducible call-to-call, even at temperature 0, across
  model versions/providers.
- The score must be auditable: a sales rep can ask "why did this SKU rank
  #1?" and a fixed formula can be printed and justified; an LLM's internal
  reasoning cannot.
- It's instant and free (no network round trip, no token cost) for a small,
  well-structured problem that doesn't need general-purpose reasoning.
"""
import csv
from pathlib import Path

from app import config
from app.schemas import ExtractedSpec, MatchCandidate

# Weights sum to 1.0 so the final score lands naturally in [0, 1].
WEIGHTS = {
    "product_type": 0.40,   # wrong product type is close to a dealbreaker
    "material": 0.30,       # material drives price/appearance most
    "gem_count": 0.20,      # partial credit scaled by closeness, not exact-match-only
    "size": 0.10,           # least weight: easiest spec to special-order/adjust
}

MIN_SCORE_THRESHOLD = 0.4   # below this, a candidate is not auto-selected as a confident match
GEM_COUNT_TOLERANCE = 3     # +/- this many gems still earns partial credit


def load_inventory(path: str | None = None) -> list[dict]:
    path = path or config.INVENTORY_PATH
    rows: list[dict] = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["gem_count"] = int(row["gem_count"])
            row["size"] = float(row["size"]) if row["size"] else None
            row["price"] = float(row["price"])
            rows.append(row)
    return rows


def _score_item(spec: ExtractedSpec, item: dict) -> float:
    score = 0.0

    if spec.product_type.value == item["product_type"]:
        score += WEIGHTS["product_type"]

    if spec.material.value == item["material"]:
        score += WEIGHTS["material"]

    gem_diff = abs(spec.gem_count - item["gem_count"])
    if gem_diff == 0:
        score += WEIGHTS["gem_count"]
    elif gem_diff <= GEM_COUNT_TOLERANCE:
        score += WEIGHTS["gem_count"] * (1 - gem_diff / (GEM_COUNT_TOLERANCE + 1))

    spec_size = spec.dimensions.size
    if spec_size is not None and item["size"] is not None:
        size_diff = abs(spec_size - item["size"])
        if size_diff == 0:
            score += WEIGHTS["size"]
        elif size_diff <= 1:
            score += WEIGHTS["size"] * (1 - size_diff)

    return round(score, 4)


def match_spec(spec: ExtractedSpec, inventory: list[dict] | None = None, top_k: int = 3) -> list[MatchCandidate]:
    """Deterministic: same spec + same inventory always yields the same
    ranked list (ties broken by SKU for stable ordering)."""
    inventory = inventory if inventory is not None else load_inventory()

    scored = [(_score_item(spec, item), item) for item in inventory]
    scored.sort(key=lambda pair: (-pair[0], pair[1]["sku"]))

    return [
        MatchCandidate(
            sku=item["sku"],
            score=score,
            product_type=item["product_type"],
            material=item["material"],
            gem_count=item["gem_count"],
            price=item["price"],
        )
        for score, item in scored[:top_k]
    ]
