-- Transaction-line base for the promotion analysis.
-- causal_data is not unique on PRODUCT_ID/STORE_ID/WEEK_NO, so it must be
-- collapsed before joining. Exposure is defined as any non-zero code.

WITH causal_exposure AS (
  SELECT
    PRODUCT_ID,
    STORE_ID,
    WEEK_NO,
    LOGICAL_OR(display != '0') AS is_display_exposed,
    LOGICAL_OR(mailer != '0') AS is_mailer_exposed,
    STRING_AGG(DISTINCT display, '|' ORDER BY display) AS display_codes,
    STRING_AGG(DISTINCT mailer, '|' ORDER BY mailer) AS mailer_codes,
    COUNT(*) AS causal_source_rows
  FROM `crucial-axon-503903-k2.dunnhumby.causal_data`
  GROUP BY 1, 2, 3
),

transaction_base AS (
  SELECT
    t.household_key,
    t.BASKET_ID,
    t.DAY,
    t.WEEK_NO,
    t.STORE_ID,
    t.PRODUCT_ID,
    p.DEPARTMENT,
    p.COMMODITY_DESC,
    p.SUB_COMMODITY_DESC,
    p.BRAND,
    p.CURR_SIZE_OF_PRODUCT,
    t.QUANTITY,
    t.SALES_VALUE AS actual_spend,
    t.RETAIL_DISC,
    t.COUPON_DISC,
    t.COUPON_MATCH_DISC,
    t.SALES_VALUE - t.RETAIL_DISC AS regular_price_value,
    SAFE_DIVIDE(-t.RETAIL_DISC, t.SALES_VALUE - t.RETAIL_DISC) AS retail_discount_rate,
    COALESCE(c.is_display_exposed, FALSE) AS is_display_exposed,
    COALESCE(c.is_mailer_exposed, FALSE) AS is_mailer_exposed,
    COALESCE(c.is_display_exposed OR c.is_mailer_exposed, FALSE) AS is_any_causal_exposed,
    c.display_codes,
    c.mailer_codes,
    COALESCE(c.causal_source_rows, 0) AS causal_source_rows
  FROM `crucial-axon-503903-k2.dunnhumby.transaction_data` AS t
  JOIN `crucial-axon-503903-k2.dunnhumby.product` AS p
    ON t.PRODUCT_ID = p.PRODUCT_ID
  LEFT JOIN causal_exposure AS c
    ON t.PRODUCT_ID = c.PRODUCT_ID
   AND t.STORE_ID = c.STORE_ID
   AND t.WEEK_NO = c.WEEK_NO
  WHERE p.COMMODITY_DESC != 'COUPON/MISC ITEMS'
)

SELECT *
FROM transaction_base;
