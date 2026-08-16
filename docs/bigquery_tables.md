# BigQuery 테이블 명세

분석은 BigQuery 프로젝트 `ybigta-505002`에서 수행했다.
**테이블 자체는 이 저장소에 포함하지 않는다** — 전체 8.5GB이고(최대 `mart_causal_clean` 2.5GB),
`sql/` 의 코드로 원본 CSV에서 전부 재생성할 수 있기 때문이다.

- 원본: `sql_study.*` (dunnhumby CSV 8종 업로드본)
- 마트: `dunnhumby_mart.*`
- 리전: `asia-northeast3`

분석 결과 수치는 `산출물/tableau/*.csv` 에 추출본으로 들어 있다.

---

## 재생성 방법

### A. BigQuery (원 분석 환경)

`sql/` 폴더의 번호 순서대로 실행한다. 폴더 번호가 곧 분석 진행 순서다.

```bash
bq --location=asia-northeast3 query --use_legacy_sql=false --format=csv < sql/10_mart/fct_transaction.sql
```

> Windows에서는 **Git Bash의 stdin 리다이렉션만** 작동한다.
> PowerShell 파이프는 BOM이 붙어 `Illegal input character "\357"` 로 실패하고,
> `cmd /c "bq.cmd ... < file.sql"` 은 SQL이 cmd 자신의 stdin으로 들어가 멈춘다.

### B. 로컬 DuckDB (BigQuery 없이)

```bash
python sql/80_python_local/build_local_duckdb.py
```

원본 CSV에서 핵심 마트를 재구축한다. BigQuery 결과와 수치가 완전히 일치하는 것을 검증했다
(금액 합계 net 8,057,463 / gross 9,463,374 / 할인 1,405,911, 구매기회 1,405,014건,
72개 카테고리 27,625쌍 — 6개 지표 최대절대차 0.000000).

---

## 테이블 목록

### 기반 마트 (`sql/10_mart/`)

| 테이블 | 행수 | 생성 SQL | 내용 |
|---|---:|---|---|
| `fct_transaction` | 2,595,732 | `fct_transaction.sql` | 정제 팩트. **정가·할인 분해의 기준 구현** |
| `dim_product` | 92,353 | `dim_product.sql` | 상품 차원 (부서/카테고리/브랜드, 쿠폰 대상 플래그) |
| `dim_household` | 2,500 | `dim_household.sql` | 가구 차원 |
| `mart_household_week` | 255,000 | `mart_household_week.sql` | 가구×주 패널 (0 채움) |
| `mart_basket` | 263,660 | `mart_basket.sql` | 장바구니 집계 |
| `mart_campaign_exposure` | 7,208 | `mart_campaign_exposure.sql` | 캠페인 노출 창 |
| `mart_household_treatment` | 2,500 | `mart_household_treatment.sql` | 가구 처치 배정 |
| `mart_household_churn` | 2,500 | `mart_household_churn.sql` | 초기 이탈 정의 (이후 측정 불가 판정) |
| `mart_household_rfm` | 2,500 | `mart_household_rfm.sql` | RFM |
| `mart_causal_psw` | 36,771,279 | `mart_causal_psw.sql` | causal_data 상품×매장×주 집계 |
| `mart_causal_product_week` | 2,049,187 | `mart_causal_product_week.sql` | 상품×주 집계 |

### 세그먼트 (`sql/20_segmentation/`)

| 테이블 | 행수 | 생성 SQL | 내용 |
|---|---:|---|---|
| `mart_household_disc_quintile` | 2,500 | `q_quintile.sql` | 금액 기준 할인의존도 5분위 |
| `mart_hh_dd_churn` | 2,498 | `q_dd_churn.sql` | 의존도(DAY≤547) + 홀드아웃(548~711) **누출 차단** |

### 전단지 준실험 (`sql/40_mailer_causal/`)

| 테이블 | 행수 | 생성 SQL | 내용 |
|---|---:|---|---|
| `mart_causal_clean` | 36,771,279 | `q_causal_clean.sql` | **mailer 코드 분리** (광고 A,C,D,F,H,L / 쿠폰 J,P / 무료 X,Z) |
| `mart_occ_all` | 1,405,014 | `q_occ_all.sql` | 전 카테고리 구매기회 (진열 동반 제외) |
| `mart_occ_3cat` | 99,958 | `q_occ.sql` | 3개 카테고리 구매기회 |
| `mart_occ_pos` | 1,405,014 | `q_dose.sql` | 지면 위치(1면/내지) 구분 |
| `mart_occ_vol` | 71,370 | `q_sdunit.sql` | 용량(oz) 기준 |
| `mart_cat_effect` | 72 | `q_ball.sql` | 카테고리별 당일 효과 |
| `mart_cat_cann` | 72 | `q_bcann.sql` | 카테고리별 56일 잠식 |
| `mart_cat_matrix` | 72 | `q_final.sql` | **최종 판정** (확대 19 / 축소 25 / 판정불가 28) |
| `mart_fwd28` | 556,672 | `q_cann.sql` | 사후 28일 창 |

### 진열 패널 (`sql/50_display_panel/`)

| 테이블 | 행수 | 생성 SQL | 내용 |
|---|---:|---|---|
| `mart_psw_panel` | 5,347,500 | `q_panel.sql` | 상품500 × 매장115 × 주93 균형 패널 |

### 쿠폰 (`sql/60_coupon/`)

| 테이블 | 행수 | 생성 SQL | 내용 |
|---|---:|---|---|
| `mart_coupon_did` | 255,000 | `q_cdid.sql` | staggered DiD 패널 |

### 중간 산출물

`tmp_mev`, `tmp_event`, `tmp_xval`, `tmp_dm`, `tmp_dd`, `tmp_ctgt` 는 개별 쿼리의
중간 결과다. 해당 SQL을 실행하면 다시 만들어지므로 별도 관리하지 않는다.

---

## 데이터 규약 (재현 시 주의)

1. **할인 컬럼은 음수다.** 정가 = `SALES_VALUE − RETAIL_DISC − COUPON_MATCH_DISC`
   (`COUPON_DISC`는 제조사 보전분이라 빼지 않는다)
2. **`RETAIL_DISC`는 로열티카드 할인**이지 판촉 할인이 아니다 (전 라인의 50.2%에 부착)
3. **`QUANTITY`에 계량상품의 그램 값이 섞여 있다** → 상한 20으로 winsorize하거나 금액 지표 사용
4. **`causal_data`는 이벤트 로그다** (`display=0 & mailer=0` 행이 0건).
   조인 실패 = "프로모션 없음"이며, 이 해석은 **매장 115개 · causal 상품 · WEEK 9~101** 범위에서만 유효
5. **mailer 처치는 광고 코드(A,C,D,F,H,L)만.** J/P는 쿠폰, X/Z는 무료 증정이라 제외
6. **TypeA 캠페인은 쿠폰 16개만 발송되고 어느 것인지 데이터에 없다** → 쿠폰 분석은 TypeB/C만
