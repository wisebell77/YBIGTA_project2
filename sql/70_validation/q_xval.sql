-- 공백 3: 패널 설계(점포×주차 FE + 상품×점포 FE)로 카테고리별 mailer 효과 → 가구 설계와 대조
CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.tmp_xval` AS
WITH pc AS (SELECT PRODUCT_ID AS product_id, COMMODITY_DESC AS category
            FROM `ybigta-505002.sql_study.product`),
i1 AS (SELECT p.product_id, p.store_id, p.week_no, pc.category, p.net, p.mail,
        p.net  - AVG(p.net)  OVER (PARTITION BY p.store_id, p.week_no) AS y1,
        p.mail - AVG(p.mail) OVER (PARTITION BY p.store_id, p.week_no) AS x1
       FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel` p JOIN pc USING (product_id)),
i2 AS (SELECT *, y1-AVG(y1) OVER (PARTITION BY product_id,store_id) AS y2,
                 x1-AVG(x1) OVER (PARTITION BY product_id,store_id) AS x2 FROM i1),
i3 AS (SELECT *, y2-AVG(y2) OVER (PARTITION BY store_id,week_no) AS y3,
                 x2-AVG(x2) OVER (PARTITION BY store_id,week_no) AS x3 FROM i2),
i4 AS (SELECT *, y3-AVG(y3) OVER (PARTITION BY product_id,store_id) AS y4,
                 x3-AVG(x3) OVER (PARTITION BY product_id,store_id) AS x4 FROM i3)
SELECT category, product_id, net, mail, y4 AS yd, x4 AS xd FROM i4;
