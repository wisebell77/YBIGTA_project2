# 데이터 사전 (Data Dictionary)

## 원본 (data/raw)

| dataset | grain (한 행의 의미) | 주요 column |
|---|---|---|
| `transaction_data.csv` | 거래 **라인** (바스켓 × 상품) | `household_key`, `BASKET_ID`, `DAY`, `WEEK_NO`, `STORE_ID`, `PRODUCT_ID`, `QUANTITY`, `SALES_VALUE`, `RETAIL_DISC`, `COUPON_DISC`, `COUPON_MATCH_DISC` |
| `product.csv` | 상품 | `PRODUCT_ID`, `COMMODITY_DESC`, `SUB_COMMODITY_DESC`, `BRAND`, `DEPARTMENT` |
| `causal_data.csv` | **프로모션 노출 이벤트** (상품 × 점포 × 주차) | `PRODUCT_ID`, `STORE_ID`, `WEEK_NO`, `display`, `mailer` |

`hh_demographic.csv`, `campaign_*.csv`, `coupon*.csv` 는 Phase 0 캐시에만 쓰이며 분석에는 사용하지 않는다.

## 파생 (data/interim, data/marts)

| 파일 | grain | 생성 Phase |
|---|---|---|
| `interim/*.parquet` | 원본과 동일 | 0 |
| `marts/occasion.parquet` | household × COMMODITY_DESC × DAY (**구매 발생분만**) | 3A |
| `marts/opportunity.parquet` | household × STORE_ID × DAY × COMMODITY_DESC (**0구매 포함**, 46.7M) | 3B-0 |
| `marts/phase3b1_*.parquet` | anchor 별 미래창 집계 | 3B-1 |
| `marts/phase4b_anchor_future28.parquet` | 딥할인/정가 anchor + 28일 미래 매장활동 | 4B |
| `marts/phase5b_anchors.parquet` | 평가기간 anchor + 세그먼트 + 미래 28일 | 5B |

## 핵심 파생 변수

| 변수 | 정의 |
|---|---|
| `reg_value` (정가환산) | `SALES_VALUE − RETAIL_DISC − COUPON_DISC − COUPON_MATCH_DISC` (할인은 음수 저장) |
| `rate` (실현 할인율) | `−RETAIL_DISC / (SALES_VALUE − RETAIL_DISC)` |
| `D` (딥할인 분류) | `rate ≥ 0.30` → 1, `rate ≤ 0.02` → 0, 그 사이는 제외 |
| `exp_any` (전단지 노출) | 해당 `COMMODITY_DESC × STORE_ID × WEEK_NO` 에 `mailer <> '0'` 존재 여부 |
| `purchase` | 그 기회에서 해당 카테고리 구매 발생 여부 (0/1) |

## 표본 필터 (전 Phase 공통)

```sql
WEEK_NO BETWEEN 9 AND 101
STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)   -- 115개 점포
COMMODITY_DESC <> 'COUPON/MISC ITEMS'
SALES_VALUE > 0                                           -- 반품·조정 라인 제외
```
