"""Pydantic models shared by the AI layer and the UI."""
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]
Source = Literal["gemini", "fallback"]


class Action(BaseModel):
    action: str
    type: Literal["reduce_discount", "stop", "shorten_duration", "change_product", "bundle", "scale_up"]
    expected_impact: str
    confidence: Confidence


class PromoInsightBody(BaseModel):
    """What Gemini returns for one promotion (source is set by code)."""
    promo_id: str
    headline: str = Field(description="At most 15 words, states revenue change and profit change")
    explanation: str = Field(description="2-4 sentences")
    root_causes: list[str] = Field(description="1-3 items")
    actions: list[Action] = Field(description="1-3 items")
    suggested_discount_pct: float | None = Field(description="Fraction, 0.10 = 10%, or null")


class PromoInsight(PromoInsightBody):
    source: Source


class NextPromoRecBody(BaseModel):
    product_id: str
    product_name: str
    suggested_discount_pct: float | None
    rationale: str
    expected_impact: str
    confidence: Confidence


class NextPromoRec(NextPromoRecBody):
    source: Source


class NextRecsBody(BaseModel):
    recs: list[NextPromoRecBody]
