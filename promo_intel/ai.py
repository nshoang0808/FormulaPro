"""AI insights for promotions, with a deterministic fallback."""
import json
import logging
from pathlib import Path

from .data import get_leaderboard, get_next_candidates
from .rule_based import rule_insight, rule_next_recs
from .schemas import NextPromoRec, PromoInsight

log = logging.getLogger(__name__)
FIXTURES = Path(__file__).parent / "fixtures"


def _promo_row(promo_id: str) -> dict:
    df = get_leaderboard()
    match = df[df["promo_id"] == promo_id]
    if match.empty:
        raise ValueError(f"Unknown promo_id: {promo_id}")
    return match.iloc[0].to_dict()


def _fixture(name: str):
    path = FIXTURES / name
    return json.loads(path.read_text()) if path.exists() else None


def _fallback_insight(promo_id: str, row: dict) -> PromoInsight:
    stored = (_fixture("insights.json") or {}).get(promo_id)
    if stored:
        return PromoInsight(**{**stored, "source": "fallback"})
    return rule_insight(row)


def _fallback_recs() -> list[NextPromoRec]:
    stored = _fixture("next_recs.json")
    if stored:
        return [NextPromoRec(**{**rec, "source": "fallback"}) for rec in stored]
    return rule_next_recs(get_next_candidates())


def analyze_promo(promo_id: str) -> PromoInsight:
    return _fallback_insight(promo_id, _promo_row(promo_id))


def recommend_next() -> list[NextPromoRec]:
    return _fallback_recs()
