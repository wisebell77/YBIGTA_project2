# YBIGTA DA 26-2 · Project 2 — Business Insight

dunnhumby **The Complete Journey** 데이터로 *"이탈 방지 및 마케팅 효율 최적화 전략"* 을 제안하는 팀 프로젝트.

**팀원별로 폴더를 나누어 각자의 분석을 관리한다.**

```
├─ 남궁현종/     판촉의 인과 효과와 마진 누수 진단 (분석 완료)
├─ 장준한/
├─ 전영찬/
├─ 배순은/
└─ data/        원본 CSV 8종 (저장소에 포함하지 않음 — 아래 참조)
```

각자 자기 폴더 안에 자유롭게 구성하면 된다. 폴더 안에 `README.md`를 두면
GitHub에서 해당 폴더를 열었을 때 바로 표시되므로, 분석 요약을 그곳에 적어두길 권한다.

---

## 데이터

원본 데이터는 **저장소에 포함하지 않는다.** 두 가지 이유다.

1. dunnhumby는 이용약관 동의 후 배포하는 데이터라 재배포하지 않는 것이 안전하다
2. `causal_data.csv` 하나가 664MB로 GitHub 파일 제한(100MB)을 넘는다

[dunnhumby 공식 배포처](https://www.dunnhumby.com/source-files/)에서 받아
**저장소 최상위의 `data/`** 에 8개 CSV를 그대로 두면 된다. `.gitignore`에 등록되어 있다.

```
data/
├─ transaction_data.csv    거래 라인 259만
├─ product.csv             상품 9.2만
├─ causal_data.csv         프로모션 노출 3,680만 (664MB)
├─ hh_demographic.csv      가구 인구통계 801
├─ campaign_desc.csv / campaign_table.csv
└─ coupon.csv / coupon_redempt.csv
```

## 분석 환경

- **BigQuery** 프로젝트 `ybigta-505002` — 원본 `sql_study.*`, 마트 `dunnhumby_mart.*` (리전 `asia-northeast3`)
- **로컬 DuckDB** — BigQuery 없이 원본 CSV만으로 재현 가능
- **Tableau Public** — 대시보드

## 데이터 규약 (공통, 틀리기 쉬운 것)

전원이 같은 데이터를 다루므로 아래는 공유해둔다. 자세한 근거는
[남궁현종/docs/bigquery_tables.md](남궁현종/docs/bigquery_tables.md) 참조.

1. **할인 컬럼은 음수다.** 정가 = `SALES_VALUE − RETAIL_DISC − COUPON_MATCH_DISC`
   (`COUPON_DISC`는 제조사 보전분이라 빼지 않는다)
2. **`RETAIL_DISC`는 로열티카드 할인**이지 판촉 할인이 아니다 — 전 라인의 50.2%에 붙어 있다
3. **`QUANTITY`에 계량상품의 그램 값이 섞여 있다** (최댓값 89,638) → winsorize 하거나 금액 지표 사용
4. **`causal_data`는 이벤트 로그다** — `display=0 & mailer=0` 행이 0건이라,
   조인 실패는 결측이 아니라 "프로모션 없음"을 뜻한다.
   단 이 해석은 **매장 115개 · causal 상품 · WEEK 9~101** 범위에서만 유효하다
5. **mailer는 단일 처치가 아니다** — 광고(A,C,D,F,H,L) / 쿠폰(J,P) / 무료 증정(X,Z)이 섞여 있다
6. **TypeA 캠페인은 쿠폰 pool 중 16개만 발송**되고 어느 것인지 데이터에 없다 → 쿠폰 단위 분석은 TypeB/C만

## 남궁현종 폴더 요약

관통 서사는 **"횡단면으로 재면 네 번 다 틀린다"** 이다.

| 축 | 횡단면의 결론 | 인과 추정의 결론 |
|---|---|---|
| 카테고리 | SOFT DRINKS = 최대 누수원 | **최대 수익원** (+31.4%) |
| 고객 | Q5 = 할인 낭비 고객 | **판촉 수익이 나는 유일한 군** (+11.7%) |
| 매장 | 진열 리프트 1.96배 | **1.29~1.42배** (격차의 70%가 선택편의) |
| 측정 | 프로모션 상품 매출은 항상 증가 | 가구 지출은 절반이 감소 |

전문은 [남궁현종/README.md](남궁현종/README.md).
