"""Public interface for the UI. app.py imports only from here."""
from .ai import analyze_promo, recommend_next
from .data import get_kpis, get_leaderboard, get_next_candidates, get_promo_timeseries
from .schemas import Action, NextPromoRec, PromoInsight

__all__ = [
    "get_kpis", "get_leaderboard", "get_promo_timeseries", "get_next_candidates",
    "analyze_promo", "recommend_next", "Action", "PromoInsight", "NextPromoRec",
]
