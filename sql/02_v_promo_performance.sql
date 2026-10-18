CREATE OR REPLACE VIEW `{dataset}.v_promo_performance` AS
WITH promo AS (
  SELECT
    pr.promo_id, pr.promo_name, pr.product_id,
    p.name AS product_name, p.category, p.list_price, p.unit_cost,
    pr.discount_pct, pr.start_date, pr.end_date,
    DATE_DIFF(pr.end_date, pr.start_date, DAY) + 1 AS promo_days,
    (p.list_price - p.unit_cost) / p.list_price AS margin_pct
  FROM `{dataset}.promotions` pr
  JOIN `{dataset}.products` p USING (product_id)
),
own AS (
  SELECT
    pm.promo_id,
    AVG(IF(d.date BETWEEN DATE_SUB(pm.start_date, INTERVAL 28 DAY)
                      AND DATE_SUB(pm.start_date, INTERVAL 1 DAY), d.units, NULL)) AS baseline_daily_units,
    SUM(IF(d.date BETWEEN pm.start_date AND pm.end_date, d.units, 0)) AS actual_units,
    SUM(IF(d.date BETWEEN pm.start_date AND pm.end_date, d.net_revenue, 0)) AS actual_revenue,
    SUM(IF(d.date BETWEEN pm.start_date AND pm.end_date, d.gross_profit, 0)) AS actual_profit,
    SUM(IF(d.date BETWEEN pm.start_date AND pm.end_date, d.discount_amount, 0)) AS discount_spend
  FROM promo pm
  JOIN `{dataset}.v_product_daily` d ON d.product_id = pm.product_id
  GROUP BY pm.promo_id
),
siblings AS (
  SELECT
    pm.promo_id,
    d.product_id,
    AVG(IF(d.date BETWEEN DATE_SUB(pm.start_date, INTERVAL 28 DAY)
                      AND DATE_SUB(pm.start_date, INTERVAL 1 DAY), d.gross_profit, NULL)) AS pre_daily_profit,
    SUM(IF(d.date BETWEEN pm.start_date AND pm.end_date, d.gross_profit, 0)) AS promo_profit
  FROM promo pm
  JOIN `{dataset}.v_product_daily` d
    ON d.category = pm.category AND d.product_id != pm.product_id
  GROUP BY 1, 2
),
cannibal AS (
  SELECT s.promo_id, SUM(s.promo_profit - s.pre_daily_profit * pm.promo_days) AS cannibalization_profit
  FROM siblings s
  JOIN promo pm USING (promo_id)
  GROUP BY 1
),
metrics AS (
  SELECT
    pm.*,
    o.baseline_daily_units,
    o.baseline_daily_units * pm.promo_days AS expected_units,
    o.actual_units, o.actual_revenue, o.actual_profit, o.discount_spend,
    COALESCE(c.cannibalization_profit, 0) AS cannibalization_profit
  FROM promo pm
  JOIN own o USING (promo_id)
  LEFT JOIN cannibal c USING (promo_id)
),
calc AS (
  SELECT
    *,
    SAFE_DIVIDE(actual_units, expected_units) - 1 AS lift_pct,
    IF(discount_pct < margin_pct, discount_pct / (margin_pct - discount_pct), NULL) AS breakeven_lift_pct,
    actual_revenue - expected_units * list_price AS incremental_revenue,
    actual_profit - expected_units * (list_price - unit_cost) AS incremental_profit,
    LEAST(actual_units, expected_units) * list_price * discount_pct AS subsidy_cost
  FROM metrics
),
net AS (
  SELECT *, incremental_profit + cannibalization_profit AS net_incremental_profit
  FROM calc
)
SELECT
  *,
  SAFE_DIVIDE(net_incremental_profit, discount_spend) AS promo_roi,
  CASE
    WHEN net_incremental_profit > 0 THEN 'Winner'
    WHEN incremental_profit > 0 THEN 'Cannibalizer'
    WHEN lift_pct < 0.10 THEN 'Subsidy Dud'
    WHEN incremental_revenue > 0 THEN 'Margin Trap'
    ELSE 'Underperformer'
  END AS verdict
FROM net
