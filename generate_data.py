"""Generate deterministic synthetic retail data with planted promotion stories."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START = dt.date(2026, 4, 1)
DAYS = 183
NOISE_SD = 0.06
WEEKEND_BUMP = 1.2

# product_id, name, category, list_price, unit_cost, base_daily_units
PRODUCTS = [
    ("B01", "Fizz Cola 330ml", "Beverages", 2.00, 1.30, 60),
    ("B02", "Lemon Sparkle 330ml", "Beverages", 2.00, 1.20, 45),
    ("B03", "Cold Brew Coffee", "Beverages", 3.50, 1.75, 25),
    ("B04", "Spring Water 1L", "Beverages", 1.20, 0.60, 70),
    ("B05", "Orange Juice 1L", "Beverages", 3.00, 1.95, 30),
    ("S01", "Sea Salt Chips", "Snacks", 3.00, 1.50, 40),
    ("S02", "Cheddar Crackers", "Snacks", 2.50, 1.50, 35),
    ("S03", "Dark Chocolate Bar", "Snacks", 2.00, 0.90, 50),
    ("S04", "Trail Mix", "Snacks", 4.50, 2.70, 20),
    ("S05", "Pretzel Bites", "Snacks", 2.50, 1.75, 45),
    ("C01", "Herbal Shampoo", "Personal Care", 6.00, 3.00, 60),
    ("C02", "Classic Shampoo", "Personal Care", 6.00, 3.00, 60),
    ("C03", "Vitamin C Serum", "Personal Care", 15.00, 6.00, 25),
    ("C04", "Mint Toothpaste", "Personal Care", 3.50, 1.75, 40),
    ("C05", "Body Lotion", "Personal Care", 8.00, 4.40, 20),
    ("H01", "Dish Soap", "Household", 3.50, 2.10, 40),
    ("H02", "Paper Towels 6pk", "Household", 7.00, 5.25, 30),
    ("H03", "Laundry Pods", "Household", 12.00, 6.60, 20),
    ("H04", "Trash Bags 30ct", "Household", 6.00, 3.60, 25),
    ("H05", "Glass Cleaner", "Household", 4.00, 1.80, 25),
]

# promo_id, promo_name, product_id, discount_pct, start_day, days, planted_lift, sibling_effects
PROMOTIONS = [
    ("PR01", "Cola Summer Blast 30% Off", "B01", 0.30, 60, 14, 0.85, {}),  # margin trap
    ("PR02", "Cold Brew 15% Off", "B03", 0.15, 120, 14, 0.45, {}),
    ("PR03", "Chips 20% Off", "S01", 0.20, 45, 14, 0.70, {}),
    ("PR04", "Chocolate 10% Off", "S03", 0.10, 100, 14, 0.35, {}),
    ("PR05", "Pretzel 25% Off", "S05", 0.25, 150, 14, 0.40, {}),
    ("PR06", "Herbal Shampoo 15% Off", "C01", 0.15, 70, 14, 0.80, {"C02": -0.50}),  # cannibalizer
    ("PR07", "Serum Glow 10% Off", "C03", 0.10, 130, 14, 0.60, {}),  # winner
    ("PR08", "Dish Soap 20% Off", "H01", 0.20, 50, 14, 0.03, {}),  # subsidy dud
    ("PR09", "Laundry Pods 15% Off", "H03", 0.15, 95, 14, 0.55, {}),
    ("PR10", "Glass Cleaner 10% Off", "H05", 0.10, 140, 14, 0.25, {}),
]


def build_products() -> pd.DataFrame:
    return pd.DataFrame(
        [p[:5] for p in PRODUCTS],
        columns=["product_id", "name", "category", "list_price", "unit_cost"],
    )


def build_promotions() -> pd.DataFrame:
    rows = [
        (pid, name, product, disc, START + dt.timedelta(days=start),
         START + dt.timedelta(days=start + days - 1))
        for pid, name, product, disc, start, days, _, _ in PROMOTIONS
    ]
    return pd.DataFrame(
        rows,
        columns=["promo_id", "promo_name", "product_id", "discount_pct", "start_date", "end_date"],
    )


def _demand_plan() -> tuple[dict, dict]:
    """Return demand multipliers and active promotion per (product_id, day)."""
    multiplier: dict[tuple[str, int], float] = {}
    active: dict[tuple[str, int], tuple[str, float]] = {}
    for pid, _, product, disc, start, days, lift, siblings in PROMOTIONS:
        for day in range(start, start + days):
            multiplier[(product, day)] = multiplier.get((product, day), 1.0) * (1 + lift)
            active[(product, day)] = (pid, disc)
            for sibling, effect in siblings.items():
                multiplier[(sibling, day)] = multiplier.get((sibling, day), 1.0) * (1 + effect)
    return multiplier, active


def build_sales() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    multiplier, active = _demand_plan()
    rows = []
    order_seq = 0
    for day in range(DAYS):
        date = START + dt.timedelta(days=day)
        weekend = WEEKEND_BUMP if date.weekday() >= 5 else 1.0
        for product, _, _, price, _, base in PRODUCTS:
            mean = base * weekend * multiplier.get((product, day), 1.0)
            units = max(0, round(mean * rng.normal(1.0, NOISE_SD)))
            promo_id, disc = active.get((product, day), (None, 0.0))
            while units > 0:
                qty = min(units, int(rng.integers(1, 4)))
                units -= qty
                order_seq += 1
                rows.append((f"O{order_seq:07d}", date, product, qty, price,
                             round(qty * price * disc, 2), promo_id))
    return pd.DataFrame(
        rows,
        columns=["order_id", "order_date", "product_id", "quantity", "unit_price",
                 "discount_amount", "promo_id"],
    )


def generate(out_dir: Path) -> dict[str, pd.DataFrame]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = {"products": build_products(), "promotions": build_promotions(), "sales": build_sales()}
    for name, df in frames.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    return frames


if __name__ == "__main__":
    result = generate(Path("data"))
    print({name: len(df) for name, df in result.items()})
