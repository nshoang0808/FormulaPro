CREATE OR REPLACE VIEW `{dataset}.v_promo_daily` AS
SELECT
  pp.promo_id,
  d.date,
  d.units,
  d.net_revenue,
  d.gross_profit,
  pp.baseline_daily_units,
  d.date BETWEEN pp.start_date AND pp.end_date AS is_promo_day
FROM `{dataset}.v_promo_performance` pp
JOIN `{dataset}.v_product_daily` d
  ON d.product_id = pp.product_id
 AND d.date BETWEEN DATE_SUB(pp.start_date, INTERVAL 14 DAY)
                AND DATE_ADD(pp.end_date, INTERVAL 14 DAY)
