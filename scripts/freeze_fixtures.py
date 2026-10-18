"""Freeze live BigQuery (and optionally Gemini) outputs into promo_intel/fixtures/."""
import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["USE_FIXTURES"] = "0"

from promo_intel import ai, data  # noqa: E402
from promo_intel.rule_based import rule_insight, rule_next_recs  # noqa: E402

FIXTURES = ROOT / "promo_intel" / "fixtures"


def _write(name: str, obj) -> None:
    (FIXTURES / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print(f"wrote {name}")


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-ai", action="store_true", help="use Gemini for insights.json/next_recs.json")
    args = parser.parse_args()
    FIXTURES.mkdir(exist_ok=True)

    leaderboard = data.get_leaderboard()
    candidates = data.get_next_candidates()
    timeseries = pd.concat(data.get_promo_timeseries(pid) for pid in leaderboard["promo_id"])
    _write("kpis.json", data.get_kpis())
    _write("leaderboard.json", _records(leaderboard))
    _write("timeseries.json", _records(timeseries))
    _write("candidates.json", _records(candidates))

    if args.with_ai:
        insights = {pid: ai.analyze_promo(pid) for pid in leaderboard["promo_id"]}
        recs = ai.recommend_next()
        fallbacks = [pid for pid, i in insights.items() if i.source != "gemini"]
        if fallbacks or any(r.source != "gemini" for r in recs):
            print(f"WARNING: fallback used for insights {fallbacks} or next recs")
    else:
        insights = {row["promo_id"]: rule_insight(row) for row in leaderboard.to_dict("records")}
        recs = rule_next_recs(candidates)
    _write("insights.json", {pid: i.model_dump() for pid, i in insights.items()})
    _write("next_recs.json", [r.model_dump() for r in recs])


if __name__ == "__main__":
    main()
