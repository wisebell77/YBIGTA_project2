# 분석 흐름 (Analysis Flow)

```
raw CSV (data/raw)
   │  Phase 0  prepare_data.py
   ▼  parquet 캐시 + DuckDB 뷰 (data/interim)
   │  Phase 1  validate_data.py         ← 게이트: 원자료 사실 재현
   ▼
   │  Phase 2  build_mailer_treatment.py ← 게이트: 대조군 병존 셀 확인
   ▼  전단지 ITT 처치 정의 확정
   │
   ├─ PART A (인과추정) ─────────────────────────────────────────────
   │   Phase 3A  build_occasion_mart → estimate_conditional_effects
   │      단위: household × COMMODITY_DESC × DAY (구매가 일어난 occasion)
   │      → 조건부 효과 (살 때 몇 개 더 사는가)
   │
   │   Phase 3B-0  build_opportunity_panel → validate_panel
   │                → estimate_total_demand → time_control_robustness
   │      단위: household × STORE_ID × DAY × COMMODITY_DESC (46.7M, 0구매 포함)
   │      → 총수요 효과 (구매확률 + 수량 + 매출 + 정가환산)
   │
   │   Phase 3B-1  selftest_future_windows → build_future_windows
   │                → estimate_payback → build_incrementality_curve
   │      각 anchor 의 t+1~t+H (7/14/28/56일) 미래구매 추적, 당일 제외
   │      → future payback 이 있는가
   │
   │   Phase 4A  summarize_robustness       (신규 회귀 없음, 저장 결과만 통합)
   │      → 스펙별 95% CI 통합표
   │
   └─ PART B (관측적/탐색적) ────────────────────────────────────────
       Phase 4B  estimate_future_store_activity
          딥할인 anchor vs 정가 anchor → 이후 28일 매장 전체 활동
       Phase 5A  category_portfolio → fdr_category
          카테고리별 visits×spend 매트릭스 → BH-FDR
       Phase 5B  build_rfm_features → estimate_segment_associations → fdr_segments
          평가기간 이전 84일 프로필(누수 방지) → 세그먼트별 비교 → BH-FDR
       Phase 5C  margin_scenario / trial_conversion / discount_depth
          마진 시나리오 · 첫 딥할인 후 전환 · 할인깊이 밴드

   Phase 8  build_final_tables → build_tableau_outputs
      → FINAL_key_results.csv, Decision Matrix, Tableau 데이터셋
```

## 의존관계 요약

- Phase 3B-1 은 Phase 3B-0 의 `opportunity.parquet` 을 필요로 한다.
- Phase 4A 는 3A·3B-0·3B-1 의 결과 CSV 를 읽는다 (**추정을 다시 하지 않는다**).
- Phase 5A 는 Phase 4B 가 만든 anchor parquet 을 재사용한다 (재계산하지 않는다).
- Phase 8 은 앞선 모든 Phase 의 결과 CSV 를 읽어 최종 표를 만들고 교차검증한다.
