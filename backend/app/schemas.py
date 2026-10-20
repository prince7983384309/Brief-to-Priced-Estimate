"""All Pydantic models: extraction, matching, CV, pricing, and the final API response."""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProductType(str, Enum):
    RING = "ring"
    NECKLACE = "necklace"
    BRACELET = "bracelet"
    EARRINGS = "earrings"
    PENDANT = "pendant"
    UNKNOWN = "unknown"


class Material(str, Enum):
    GOLD = "gold"
    SILVER = "silver"
    PLATINUM = "platinum"
    ROSE_GOLD = "rose_gold"
    WHITE_GOLD = "white_gold"
    UNKNOWN = "unknown"


class Dimensions(BaseModel):
    size: Optional[float] = Field(None, description="Ring size, chain length, etc.")
    unit: Optional[str] = Field(None, description="e.g. 'US', 'cm', 'inch'")


class ExtractedSpec(BaseModel):
    product_type: ProductType = ProductType.UNKNOWN
    material: Material = Material.UNKNOWN
    gem_count: int = Field(0, ge=0, description="Number of small gems/stones mentioned or implied")
    dimensions: Dimensions = Field(default_factory=Dimensions)
    budget: Optional[float] = Field(None, description="Mentioned budget, if any")
    notes: Optional[str] = None

    @classmethod
    def safe_default(cls) -> "ExtractedSpec":
        """Used by the extractor's fallback path when model output can't be salvaged."""
        return cls()


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FieldConfidence(BaseModel):
    level: ConfidenceLevel
    reason: str


class MatchCandidate(BaseModel):
    sku: str
    score: float
    product_type: str
    material: str
    gem_count: int
    price: float


class CVEstimate(BaseModel):
    estimated_gem_count: Optional[int] = None
    method: str
    confidence: FieldConfidence
    # Populated only when VISION_LLM_ENABLED=true, for comparison against the classical baseline.
    vision_llm_estimate: Optional[int] = None
    vision_llm_reason: Optional[str] = None


class PriceEstimate(BaseModel):
    estimated_price: float
    based_on_sku: str
    reason: str
    confidence: FieldConfidence


class AnalyzeResponse(BaseModel):
    extracted_spec: ExtractedSpec
    extraction_method: str  # "llm_success" | "llm_repaired" | "fallback_default"
    field_confidence: Dict[str, FieldConfidence]
    top_matches: List[MatchCandidate]
    cv_estimate: Optional[CVEstimate] = None
    price_estimate: Optional[PriceEstimate] = None
    review_required: bool
    review_reasons: List[str]
