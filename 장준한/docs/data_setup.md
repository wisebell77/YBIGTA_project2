# 데이터 준비 (Data Setup)

원본 데이터는 **저장소에 포함하지 않는다.**

1. dunnhumby *The Complete Journey* 는 이용약관 동의 후 배포되는 데이터라 재배포하지 않는다
2. `causal_data.csv` 하나가 약 664MB 로 GitHub 파일 제한(100MB)을 초과한다

받은 CSV 를 아래처럼 **`data/raw/`** 에 그대로 두면 된다.
`data/raw/*` 는 `.gitignore` 에 등록되어 있어 커밋되지 않는다.

```
data/
├─ raw/          ← 여기에 원본 CSV 를 둔다 (git 제외)
├─ interim/      ← Phase 0 이 생성 (git 제외)
└─ marts/        ← Phase 3A 이후가 생성 (git 제외)
```

## 필수 파일 (없으면 파이프라인이 실행되지 않음)

| 파일 | 목적 | 필수 column | 사용 Phase |
|---|---|---|---|
| `transaction_data.csv` | 거래 라인 | `household_key`, `DAY`, `WEEK_NO`, `STORE_ID`, `PRODUCT_ID`, `QUANTITY`, `SALES_VALUE`, `RETAIL_DISC`, `COUPON_DISC`, `COUPON_MATCH_DISC` | 0 이후 전 Phase |
| `product.csv` | 상품 마스터 | `PRODUCT_ID`, `COMMODITY_DESC` | 0 이후 전 Phase |
| `causal_data.csv` | 프로모션 노출 이벤트 로그 | `PRODUCT_ID`, `STORE_ID`, `WEEK_NO`, `mailer`, `display` | 2 이후 PART A 전체 |

## 선택 파일 (Phase 0 캐시에만 사용, 분석에는 미사용)

`hh_demographic.csv` · `campaign_desc.csv` · `campaign_table.csv` · `coupon.csv` · `coupon_redempt.csv`

없어도 파이프라인은 동작한다. Phase 0 이 존재하는 파일만 캐시한다.

## ⚠️ 데이터 규약 (반드시 숙지)

1. **`causal_data` 는 패널이 아니라 이벤트 로그다.** `display=0 & mailer=0` 인 행이 0건이다.
   조인 실패 = 데이터 손실이 아니라 **"미노출 = 대조군"** 이다. LEFT JOIN 후 NULL→0.
2. **`causal_data` 커버리지가 표본 범위를 결정한다.** 점포 115개 / `WEEK_NO` 9–101 만 존재한다.
   이 범위 밖은 "노출 여부 unknown" 이지 "미노출" 이 아니므로 표본을 명시 한정한다.
3. **할인 컬럼은 전부 음수로 저장돼 있다.**
   `정가 = SALES_VALUE − RETAIL_DISC − COUPON_DISC − COUPON_MATCH_DISC`
4. **`RETAIL_DISC` 는 판촉이 아니라 로열티카드 할인이다** (전체 라인의 약 50%).
5. **`QUANTITY` 오염** — `COUPON/MISC ITEMS` 카테고리가 전체 수량의 98.7% 를 차지한다.
   이 카테고리를 제외하면 표본 내 최댓값이 144 로 정상화된다.

## 출처

`docs/reproducibility.md` 참조. 데이터 출처 URL 은 배포처 약관을 확인한 뒤 이용한다.
