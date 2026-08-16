CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_causal_psw`
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(0, 110, 1))
CLUSTER BY product_id, store_id
AS
WITH deduped AS (
  -- 조인 키에 중복이 있을 수 있으므로 먼저 유일하게 만든다.
  -- 같은 키에 코드가 여러 개면 '노출된 쪽'을 우선한다(MAX: '0'보다 문자/숫자코드가 큼).
  SELECT
    PRODUCT_ID                        AS product_id,
    STORE_ID                          AS store_id,
    WEEK_NO                           AS week_no,
    MAX(CAST(display AS STRING))      AS display_code,
    MAX(CAST(mailer  AS STRING))      AS mailer_code
  FROM `ybigta-505002.sql_study.causal_data`
  GROUP BY product_id, store_id, week_no
)
SELECT
  product_id,
  store_id,
  week_no,
  display_code,
  mailer_code,

  -- ---- 핵심 플래그 (코드 해석과 무관하게 안전) ----
  display_code != '0'                             AS is_on_display,
  mailer_code  != '0'                             AS is_on_mailer,
  display_code != '0' AND mailer_code != '0'      AS is_both,

  -- ---- 진열 위치 (공식 User Guide 코드표) ----
  CASE display_code
    WHEN '0' THEN 'Not on Display'
    WHEN '1' THEN 'Store Front'
    WHEN '2' THEN 'Store Rear'
    WHEN '3' THEN 'Front End Cap'
    WHEN '4' THEN 'Mid-Aisle End Cap'
    WHEN '5' THEN 'Rear End Cap'
    WHEN '6' THEN 'Side-Aisle End Cap'
    WHEN '7' THEN 'In-Aisle'
    WHEN '9' THEN 'Secondary Location Display'
    WHEN 'A' THEN 'In-Shelf'
    ELSE CONCAT('Unknown:', display_code)
  END                                             AS display_desc,

  -- 엔드캡/매장 전면 = 고가치 진열. 전략 제안에서 '비용 대비 효과'를 가르는 축.
  display_code IN ('1', '3', '4', '5', '6')       AS is_premium_display,

  -- ---- 전단지 지면 (공식 User Guide 코드표) ----
  -- 주의: 최초 작성 시 통용 매핑을 썼다가 F·H·J·L·P 5개가 틀린 것을 공식 문서로 확인해 교정했다.
  --       ('Front Page Line Item'이라는 존재하지 않는 항목을 F에 넣어 이후가 한 칸씩 밀렸음)
  CASE mailer_code
    WHEN '0' THEN 'Not on Ad'
    WHEN 'A' THEN 'Interior Page Feature'
    WHEN 'C' THEN 'Interior Page Line Item'
    WHEN 'D' THEN 'Front Page Feature'
    WHEN 'F' THEN 'Back Page Feature'
    WHEN 'H' THEN 'Wrap Front Feature'
    WHEN 'J' THEN 'Wrap Interior Coupon'
    WHEN 'L' THEN 'Wrap Back Feature'
    WHEN 'P' THEN 'Interior Page Coupon'
    WHEN 'X' THEN 'Free on Interior Page'
    WHEN 'Z' THEN 'Free on Front Page, Back Page or Wrap'
    ELSE CONCAT('Unknown:', mailer_code)
  END                                             AS mailer_desc,

  -- 표지·랩 외면 = 최고 노출 지면 (D 앞면 / F 뒷면 / H 랩앞 / L 랩뒤 / Z 무료제공)
  -- J(Wrap Interior Coupon)는 랩 '내부'이므로 제외한다. 최초 정의에서 잘못 포함했던 것을 교정.
  mailer_code IN ('D', 'F', 'H', 'L', 'Z')        AS is_cover_page,

  -- 피처(큰 지면 노출) vs 라인아이템(작은 목록 게재) — 노출 강도가 다르다
  mailer_code IN ('A', 'D', 'F', 'H', 'L')        AS is_feature_ad,
  -- 전단지에 실린 쿠폰 (지면 광고와 성격이 다름)
  mailer_code IN ('J', 'P')                       AS is_mailer_coupon

FROM deduped