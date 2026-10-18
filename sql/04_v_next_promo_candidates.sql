CREATE OR REPLACE VIEW `{dataset}.v_next_promo_candidates` AS
WITH bounds AS (
  SELECT MAX(date) AS last_date FROM `{dataset}.v_product_daily`
),
cat_lift AS (
  SELECT category, GREATEST(AVG(lift_pct), 0) AS category_avg_lift
  FROM `{dataset}.v_promo_performance`
  GROUP BY category
),
recent AS (
  SELECT DISTINCT pr.product_id
  FROM `{dataset}.promotions` pr, bounds
  WHERE pr.end_date > DATE_SUB(bounds.last_date, INTERVAL 60 DAY)
),
base AS (
  SELECT d.product_id, AVG(d.units) AS baseline_daily_units
  FROM `{dataset}.v_product_daily` d, bounds
  WHERE d.date > DATE_SUB(bounds.last_date, INTERVAL 28 DAY)
  GROUP BY 1
),
cands AS (
  SELECT
    p.product_id,
    p.name AS product_name,
    p.category,
    p.list_price,
    p.unit_cost,
    (p.list_price - p.unit_cost) / p.list_price AS margin_pct,
    COALESCE(cl.category_avg_lift, 0) AS category_avg_lift,
    b.baseline_daily_units
  FROM `{dataset}.products` p
  JOIN base b USING (product_id)
  LEFT JOIN cat_lift cl USING (category)
  LEFT JOIN recent r USING (product_id)
  WHERE r.product_id IS NULL
),
safe_steps AS (
  SELECT c.product_id, MAX(d) AS suggested_discount_pct
  FROM cands c
  CROSS JOIN UNNEST([0.05, 0.10, 0.15, 0.20, 0.25]) AS d
  WHERE d < c.margin_pct
    AND 1.5 * d / (c.margin_pct - d) <= c.category_avg_lift
  GROUP BY 1
),
scored AS (
  SELECT
    c.*,
    c.margin_pct * c.category_avg_lift AS score,
    s.suggested_discount_pct
  FROM cands c
  LEFT JOIN safe_steps s USING (product_id)
)
SELECT
  *,
  IF(suggested_discount_pct IS NULL, 0,
     baseline_daily_units * 14 * (
       (1 + category_avg_lift) * list_price * (margin_pct - suggested_discount_pct)
       - list_price * margin_pct)) AS projected_incremental_profit
FROM scored
