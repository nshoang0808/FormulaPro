CREATE OR REPLACE VIEW `{dataset}.v_product_daily` AS
WITH calendar AS (
  SELECT d AS date
  FROM UNNEST(GENERATE_DATE_ARRAY(
    (SELECT MIN(order_date) FROM `{dataset}.sales`),
    (SELECT MAX(order_date) FROM `{dataset}.sales`))) AS d
),
agg AS (
  SELECT
    s.product_id,
    s.order_date AS date,
    SUM(s.quantity) AS units,
    SUM(s.quantity * s.unit_price - s.discount_amount) AS net_revenue,
    SUM(s.quantity * s.unit_price - s.discount_amount - s.quantity * p.unit_cost) AS gross_profit,
    SUM(s.discount_amount) AS discount_amount
  FROM `{dataset}.sales` s
  JOIN `{dataset}.products` p USING (product_id)
  GROUP BY 1, 2
)
SELECT
  p.product_id,
  p.name AS product_name,
  p.category,
  p.list_price,
  p.unit_cost,
  c.date,
  COALESCE(a.units, 0) AS units,
  COALESCE(a.net_revenue, 0) AS net_revenue,
  COALESCE(a.gross_profit, 0) AS gross_profit,
  COALESCE(a.discount_amount, 0) AS discount_amount
FROM `{dataset}.products` p
CROSS JOIN calendar c
LEFT JOIN agg a ON a.product_id = p.product_id AND a.date = c.date
