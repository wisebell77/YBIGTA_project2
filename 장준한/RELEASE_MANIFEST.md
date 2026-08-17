# RELEASE MANIFEST

> `dunnhumby-promotion-analysis` — GitHub 공개용 reproducible release
> 원본 프로젝트는 그대로 보존되며, 이 폴더는 **COPY / REFACTOR** 산출물이다.

---

## 1. 최종 디렉터리 트리

```
dunnhumby-promotion-analysis/
├── config/
│   └── config.example.yaml
├── data/
│   ├── interim/
│   ├── marts/
│   ├── raw/
│   │   ├── .gitkeep
│   │   ├── causal_data.csv
│   │   ├── hh_demographic.csv
│   │   ├── product.csv
│   │   └── transaction_data.csv
│   └── README.md
├── docs/
│   ├── analysis_flow.md
│   ├── data_dictionary.md
│   ├── methodology.md
│   └── reproducibility.md
├── outputs/
│   ├── checkpoints/
│   ├── figures/
│   │   └── .gitkeep
│   ├── tableau/
│   │   └── .gitkeep
│   └── tables/
│       └── .gitkeep
├── reference_results/
│   └── FINAL_key_results.csv
├── reports/
│   ├── FINAL_integrated_report.md
│   └── FINAL_onepage_summary.md
├── src/
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── fe_estimator.py
│   │   ├── paths.py
│   │   └── utils.py
│   ├── phase0_prepare/
│   │   ├── __init__.py
│   │   └── prepare_data.py
│   ├── phase1_validation/
│   │   ├── __init__.py
│   │   └── validate_data.py
│   ├── phase2_design/
│   │   ├── __init__.py
│   │   └── build_mailer_treatment.py
│   ├── phase3a_conditional/
│   │   ├── __init__.py
│   │   ├── build_occasion_mart.py
│   │   ├── deep_discount_reference.py
│   │   └── estimate_conditional_effects.py
│   ├── phase3b0_total_demand/
│   │   ├── __init__.py
│   │   ├── build_opportunity_panel.py
│   │   ├── estimate_total_demand.py
│   │   ├── mailer_definition_robustness.py
│   │   ├── time_control_robustness.py
│   │   └── validate_panel.py
│   ├── phase3b1_incrementality/
│   │   ├── __init__.py
│   │   ├── build_future_windows.py
│   │   ├── build_incrementality_curve.py
│   │   ├── estimate_payback.py
│   │   └── selftest_future_windows.py
│   ├── phase4a_robustness/
│   │   ├── __init__.py
│   │   └── summarize_robustness.py
│   ├── phase4b_relationship/
│   │   ├── __init__.py
│   │   └── estimate_future_store_activity.py
│   ├── phase5a_category/
│   │   ├── __init__.py
│   │   ├── category_portfolio.py
│   │   └── fdr_category.py
│   ├── phase5b_crm/
│   │   ├── __init__.py
│   │   ├── build_rfm_features.py
│   │   ├── estimate_segment_associations.py
│   │   └── fdr_segments.py
│   ├── phase5c_conversion/
│   │   ├── __init__.py
│   │   ├── discount_depth.py
│   │   ├── margin_scenario.py
│   │   └── trial_conversion.py
│   ├── phase8_finalize/
│   │   ├── __init__.py
│   │   ├── build_final_tables.py
│   │   └── build_tableau_outputs.py
│   └── __init__.py
├── tests/
│   ├── test_data_schema.py
│   ├── test_environment.py
│   ├── test_outputs.py
│   └── test_paths.py
├── .gitignore
├── _build_map.json
├── LICENSE_NOTE.md
├── pytest.ini
├── README.md
├── requirements.txt
└── run_pipeline.py
```

생성 디렉터리(`data/interim`, `data/marts`, `outputs/*`, `.smoke_run/`)는 실행 중 만들어지며 `.gitignore` 로 제외된다.

---

## 2. Source script mapping (KEEP / MERGE)

| 원본 | → release | 분류 | 사유 |
|---|---|---|---|
| `src/fe_estimator.py` | `src/common/fe_estimator.py` | **KEEP** | 대규모 다중 FE 추정 엔진. 전 Phase 공용 |
| `src/phase0_cache.py` | `src/phase0_prepare/prepare_data.py` | **KEEP** | raw CSV → parquet 캐시 + DuckDB 뷰 |
| `src/phase1_reproduce.py` | `src/phase1_validation/validate_data.py` | **KEEP** | 원자료 사실 재현 게이트 |
| `src/phase2_feasibility.py` | `src/phase2_design/build_mailer_treatment.py` | **KEEP** | 전단지 ITT 처치 정의 · 대조군 병존 확인 |
| `src/phase3a_02_build_mart.py` | `src/phase3a_conditional/build_occasion_mart.py` | **KEEP** | occasion 마트 생성 |
| `src/phase3a_03_estimate.py` | `src/phase3a_conditional/estimate_conditional_effects.py` | **KEEP** | 조건부 효과 + cluster SE (phase3a_clusterse.csv 생성 — 4A 입력) |
| `src/phase3a_07_pdfcompare.py` | `src/phase3a_conditional/deep_discount_reference.py` | **KEEP** | 딥할인 보조설계. anchor SQL 을 Phase 4B 가 재사용 |
| `src/phase3b0_01_build_panel.py` | `src/phase3b0_total_demand/build_opportunity_panel.py` | **KEEP** | 46.7M shopping opportunity 패널 |
| `src/phase3b0_02_validate.py` | `src/phase3b0_total_demand/validate_panel.py` | **KEEP** | 패널 정합성 자가검증 |
| `src/phase3b0_03_main.py` | `src/phase3b0_total_demand/estimate_total_demand.py` | **KEEP** | 주 결과. 단일쿼리 적재 + self-check 포함된 수정본 |
| `src/phase3b0_04_robust.py` | `src/phase3b0_total_demand/mailer_definition_robustness.py` | **KEEP** | mailer 정의 강건성 |
| `src/phase3b0_06_resume.py` | `src/phase3b0_total_demand/time_control_robustness.py` | **MERGE** | 05_timecontrol 의 스펙목록 + 06_resume 의 skip/append 로직 통합. 05 는 CSV 전체 덮어쓰기 + 이전 결과 하드코딩 문제로 제외 |
| `src/phase3b1_00_selftest.py` | `src/phase3b1_incrementality/selftest_future_windows.py` | **KEEP** | prefix-sum 로직 브루트포스 대조 검증 |
| `src/phase3b1_01_postwindow.py` | `src/phase3b1_incrementality/build_future_windows.py` | **KEEP** | 미래창 마트 생성 |
| `src/phase3b1_02_estimate.py` | `src/phase3b1_incrementality/estimate_payback.py` | **KEEP** | 56일 payback ITT 추정 |
| `src/phase3b1_03_curve.py` | `src/phase3b1_incrementality/build_incrementality_curve.py` | **KEEP** | 증분성 곡선 표 |
| `src/phase4a_robustness.py` | `src/phase4a_robustness/summarize_robustness.py` | **KEEP** | 저장 결과만 읽어 CI 통합 (신규 회귀 없음) |
| `src/phase4b_deepdisc_future.py` | `src/phase4b_relationship/estimate_future_store_activity.py` | **KEEP** | 딥할인 anchor 생성 + 28일 매장활동 추정 (anchor parquet 도 생성) |
| `src/phase5a_category_matrix.py` | `src/phase5a_category/category_portfolio.py` | **KEEP** | 카테고리별 visits×spend 매트릭스 |
| `src/phase5b_01_build.py` | `src/phase5b_crm/build_rfm_features.py` | **KEEP** | period-split RFM 프로필 + anchor |
| `src/phase5b_02_estimate.py` | `src/phase5b_crm/estimate_segment_associations.py` | **KEEP** | 세그먼트별 naive + hh×cat FE 추정 |
| `src/phase5c_step3_simple.py` | `src/phase5c_conversion/trial_conversion.py` | **KEEP** | 최종 CSV 를 실제 생성한 버전 (타임스탬프 대조 확인) |
| `src/phase5c_step4_simple.py` | `src/phase5c_conversion/discount_depth.py` | **KEEP** | 최종 CSV 를 실제 생성한 버전 (타임스탬프 대조 확인) |
| `step1_margin_sensitivity.py` | `src/phase5c_conversion/margin_scenario.py` | **KEEP** | 마진 시나리오. 원본은 프로젝트 루트에 있어 src 로 이동 |
| `src/phase8_final_tables.py` | `src/phase8_finalize/build_final_tables.py` | **KEEP** | 최종 핵심수치표 + Decision Matrix + 교차검증 |
| `src/phase7_tableau_build.py` | `src/phase8_finalize/build_tableau_outputs.py` | **KEEP** | Tableau 데이터셋 생성 |

### SPLIT

| 원본 | → release | 사유 |
|---|---|---|
| `src/phase8_fdr_correction.py` | `src/phase5a_category/fdr_category.py`<br>`src/phase5b_crm/fdr_segments.py` | 5A/5B 두 독립 블록을 phase 별로 분리 |

### EXCLUDE

| 원본 | 분류 | 사유 |
|---|---|---|
| `src/phase3a_01_diagnose.py` | EXCLUDE | 탐색·진단 전용. 최종 산출물 없음 |
| `src/phase3a_04_fe_diag.py` | EXCLUDE | FE 진단 전용. 최종 산출물 없음 |
| `src/phase3a_05_altspec.py` | EXCLUDE | 대안 스펙 탐색. 최종 표에 미사용 |
| `src/phase3a_06_final.py` | EXCLUDE | phase3a_03 과 clusterse.csv 중복 생성. 03 을 source of truth 로 채택 |
| `src/phase3b0_05_timecontrol.py` | EXCLUDE | ⚠️ 저장 시 CSV 전체를 자기 rows 로 덮어써 append 결과를 지운다. 이전 결과가 코드에 하드코딩돼 있음. 로직은 time_control_robustness.py 로 통합 |
| `src/phase5c_step3_trial_to_conversion.py` | EXCLUDE | 동일 산출물의 이전 시도본. _simple 버전이 최종 CSV 생성 |
| `src/phase5c_step4_discount_bands.py` | EXCLUDE | 동일 산출물의 이전 시도본. _simple 버전이 최종 CSV 생성 |
| `src/phase8_wording_fix.py` | EXCLUDE | 일회성 문서 문자열 치환 |
| `src/phase9_final_wording.py` | EXCLUDE | 일회성 문서 문자열 치환 |
| `src/build_release.py` | EXCLUDE | release 빌드 도구 자체 |

> ⚠️ **DuckDB row-order 버그가 있던 초기 Phase 3B-0 코드는 release 에 포함하지 않았다.**
> release 의 `estimate_total_demand.py` 는 **모든 컬럼을 단일 쿼리로 동시에 읽고**
> `purchase=0` 인데 `sales>0` 인 행이 0건인지 self-check 하는 수정본이다.

---

## 3. Raw data policy

- 원본 CSV 는 **저장소에 포함하지 않는다** (dunnhumby 이용약관 + `causal_data.csv` 약 664MB).
- `data/raw/*` 는 `.gitignore` 로 차단하고 `data/raw/.gitkeep` 만 커밋한다.
- 필수: `transaction_data.csv`, `product.csv`, `causal_data.csv`
- 선택(Phase 0 캐시 전용): `hh_demographic.csv`, `campaign_*.csv`, `coupon*.csv`
  — 없으면 Phase 0 이 건너뛴다.
- 상세 스키마·데이터 규약은 `docs/data_setup.md`.

---

## 4. Requirements

`pip freeze` 가 아니라 release 코드의 **실제 import 를 전수 스캔**해 작성했다.

```
# Dunnhumby Promotion Incrementality — 실행에 필요한 패키지만 포함
# (pip freeze 전체가 아니라, release 코드의 실제 import 를 전수 스캔해 작성)
# 버전은 원 분석이 정상 실행된 환경 기준으로 pin 했다.

duckdb==1.5.1          # 전 Phase 의 SQL 엔진
numpy==1.26.4          # fe_estimator 의 bincount 기반 demeaning
pandas==3.0.0          # 표 조작 · CSV I/O
pyarrow==15.0.2        # pandas 의 parquet 읽기/쓰기 백엔드 (직접 import 하지 않음)
scipy==1.16.2          # t/정규 분포 (p-value, FDR)
PyYAML==6.0.1          # config 로더

# 회귀 (Phase 3A / 4B / 5A / 5B 에서 사용)
pyfixest==0.60.0

# 테스트
pytest==7.4.4

# ── 참고 ──────────────────────────────────────────────────────────────
# * Windows 전용 의존성은 없다. macOS/Linux 에서도 동작한다.
#   단 Windows 콘솔의 cp949 인코딩 때문에 각 스크립트가
#   sys.stdout.reconfigure(encoding="utf-8") 를 호출한다 (타 OS 에서는 무해).
# * 46.7M 행 패널을 다루므로 RAM 16GB 이상을 권장한다.
#   메모리가 적으면 config 의 duckdb_memory_limit 을 낮출 것.
```

Windows 전용 의존성 없음. Python 3.9+, RAM 16GB 이상 권장.

---

## 5. Pipeline order

```
phase0 → phase1 → phase2 → phase3a → phase3b0 → phase3b1 → phase4a
       → phase4b → phase5a → phase5b → phase5c → phase8
```

- `phase0~4a` = **PART A** (전단지 노출 ITT, 주 인과추정 설계)
- `phase4b~5c` = **PART B** (실현 딥할인, observational/exploratory)
- 각 phase 완료 시 `outputs/checkpoints/<phase>.done` 생성.
  재실행 시 **체크포인트와 실제 산출물이 모두 정상일 때만** skip 한다(`.done` 만으로 skip 하지 않는다). `--force` 로 무시 가능.
- smoke 실행은 체크포인트를 기록하지 않는다.

---

## 6. File-size scan

- 배포 대상 파일 수: **69개**
- 배포 대상 총 용량: **0.29 MB**
- 50MB 초과: **0개**
- 100MB 초과: **0개**

가장 큰 파일 5개:

| 파일 | 크기 |
|---|---|
| `reports/FINAL_integrated_report.md` | 22 KB |
| `run_pipeline.py` | 14 KB |
| `src/phase3b1_incrementality/estimate_payback.py` | 13 KB |
| `src/phase8_finalize/build_final_tables.py` | 12 KB |
| `src/phase3b1_incrementality/build_future_windows.py` | 12 KB |

raw CSV · parquet mart · duckdb DB 는 배포 대상에 포함되지 않는다(.gitignore).

---

## 7. Static path / credential scan

| 검사 | 결과 |
|---|---|
| 드라이브 절대경로 (`C:\Users`, `C:/Users`) | 코드·문서에 없음 |
| 개인 계정 문자열 | 없음 |
| `OneDrive` | 없음 |
| 상위 원 프로젝트 참조 | 없음 (`tests/test_paths.py` 가 자동 검사) |
| `api_key` / `token` / `password` / `secret` | 실제 credential 없음 |
| `.env` 파일 | 없음 |

경로는 전부 `src/common/paths.py` 의 `PROJECT_ROOT` 에서 파생된다.
`PROJECT_ROOT` 는 `src/common/paths.py` 위치 기준으로 자동 계산하며, 환경변수 `DUNNHUMBY_ROOT` 로 override 할 수 있다.

---

## 8. Test results

release 폴더 내부에서 실행 (원본 프로젝트 디렉터리 참조 없음).

| 검사 | 명령 | 결과 |
|---|---|---|
| 문법 컴파일 | `python -m compileall src run_pipeline.py` | ✅ 통과 |
| 단위 테스트 | `python -m pytest -q` | ✅ **13 passed, 9 skipped** (skip = raw 데이터 미배치로 data-dependent 검사) |
| CLI | `python run_pipeline.py --help` | ✅ 정상 |
| 사전점검 (데이터 없음) | `python run_pipeline.py --check` | ✅ `Missing required data files:` 목록 출력 후 non-zero (traceback 아님) |
| 사전점검 (데이터 있음) | `python run_pipeline.py --check` | ✅ `실행 준비 완료` |

---

## 9. Full-run / Smoke-run 여부 ⚠️ 정확히 기록

> **Full pipeline was originally executed in the source project.**
> **The release refactor passed smoke/schema/static checks.**
> **A full clean rerun after refactoring was NOT completed.**

### 실제로 수행한 것 — smoke run (전체 12 phase)

검증을 위해 원본 CSV 를 **하드링크**로 `data/raw/` 에 잠시 연결한 뒤
`--smoke` (가구 300개 표본, 샌드박스 `.smoke_run/` 격리) 로 **12개 phase 전부**를 실행했다.
검증 후 하드링크와 샌드박스는 제거했다.

| phase | smoke 결과 | 소요 |
|---|---|---|
| phase0 | ✅ | 56s (거래 290,070행 / 가구 300) |
| phase1 | ✅ | 0s |
| phase2 | ✅ | 9s |
| phase3a | ✅ | 324s |
| phase3b0 | ✅ | 846s (**MERGE 산출물 `time_control_robustness.py` 포함**) |
| phase3b1 | ✅ | 1,545s (prefix-sum → M1/M2/M3 전 경로) |
| phase4a | ✅ | 1s |
| phase4b / phase5a / phase5b / phase5c / phase8 | ✅ | 6s / 6s / 11s / 4s / 2s |

**smoke 의 목적은 코드 동작·스키마·제어흐름 확인이며, 산출 추정치를 원 full-run 결과와
비교하지 않는다.** smoke 표본은 300가구·카테고리 7개 수준이라 추정치가 다른 것이 정상이다.

### 수행하지 않은 것

- **리팩터 후 full clean rerun (전체 46.7M 행)** — 미실행.
  사유: 원 프로젝트에서 이미 수 시간 규모로 완료된 계산이며, 이번 작업 범위가
  "새 대규모 분석 금지 / 검수·릴리스 정리"로 한정되었다.
  따라서 **"fully reproduced from clean clone" 이라고 주장하지 않는다.**

### 리팩터 중 발견해 수정한 문제 (smoke 덕분에 드러남)

| 문제 | 조치 |
|---|---|
| Phase 0 이 optional raw 파일 누락 시 크래시 | 필수 3종만 강제, 나머지는 건너뛰도록 수정 |
| Phase 2 가 빈 결과에서 `NULL` 로 `TypeError` | 방어 코드 추가 |
| `validate_panel` 의 허용오차가 **절대 1e-6** 이라 소표본에서 SE 가 커지면 오탐 | 절대 1e-6 **또는** 상대 1e-5 (OR) 로 변경 — full run 판정은 종전과 동일하게 유지 |
| 2-way cluster SE 가 소표본에서 상대 1.3e-4 로 갈림 | 기준을 더 낮추지 않고, **smoke 에서만 경고로 강등**. full run 은 엄격 유지 |
| Phase 8 교차검증이 불일치인데도 **exit 0** | full run 에서 불일치 시 **non-zero 종료**하도록 게이트 추가. smoke 는 비교 자체를 건너뜀 |

---

## 10. Known limitations

1. **표본 범위** — `causal_data` 커버리지 때문에 점포 115개 / `WEEK_NO` 9–101 로 한정.
   점포 수로는 19.8% 지만 매출 기준 98.49%.
2. **`causal_data` 는 이벤트 로그** — 미노출 행이 없으며, "조인 실패 = 미노출(대조군)" 가정 위에 설계가 선다.
3. **후속 전단지 노출 미통제** (post-treatment). 주 결과는 natural-course ITT.
4. **`category × week` FE 사용 불가** — 처치 변동의 97.8% 를 흡수해 식별 붕괴.
   최대 통제(`cat×month`+`WEEK`)도 처치변동 약 52.9% 를 함께 제거하므로 **하한**으로 읽는다.
5. **PART B 전체가 관측적** — 딥할인은 가구 자기선택. 인과 해석 금지.
6. **Phase 5A 의 FDR 은 근사 p-value 기반** — 공표 CI(`beta ± 1.96·SE`)에서 SE 를 역산한
   정규근사값이며 원 회귀 p 와 완전히 동일하지 않다.
7. **gross margin 은 가정** — 원가·vendor funding·rebate·운영비 없음. break-even ≈40.34% 는
   시나리오 임계값이지 실측 ROI 가 아니다.
8. **원본 데이터 미포함** — 직접 받아 `data/raw/` 에 두어야 한다.
9. **value-to-revenue gap 13.4%p 는 두 상대효과의 차이**이며, 이에 대한 정식 difference test 는 수행하지 않았다.
10. **Phase 5B 의 High 결과는 배타적 6개 고객군이 아니다** — 특성끼리 중첩된다.

---

## 11. Optional robustness not included

아래는 **보고된 56일 주결론에 필요하지 않지만, 확장 가능한 항목**이다
(*not required for the reported 56-day main conclusion, but available as potential extensions*).

| 항목 | 비고 |
|---|---|
| Cox / AFT 생존분석 (frailty) | 추가 timing robustness |
| Phase 3B-1 **28일 M3** | 28일 horizon 의 동일 강도 시간통제 결과는 **미확인** |
| `store×cat + WEEK` 장시간 회귀 (④) | 추가 FE robustness |
| 시간통제 하 **SALES beta (⑧)** | 시간통제 하 매출효과는 ⑤·⑥ 로만 확인됨 |
| formal equivalence test | payback 상한은 근사 CI 환산으로만 제시 |

⚠️ **이 항목들이 결론을 바꾸지 않는다고 입증된 것은 아니다.**

---

## 12. GitHub 업로드 전 남은 수동 작업

1. `LICENSE_NOTE.md` → 팀/과목 정책 확정 후 실제 `LICENSE` 로 교체
2. 이 폴더 전체를 대상 저장소의 원하는 위치로 복사
3. `git add` 전에 `git status` 로 `data/`, `outputs/` 가 제외되는지 확인
   (`data/raw/.gitkeep` 과 `outputs/*/.gitkeep` 만 포함되어야 한다)

### 12-1. 팀 저장소(YBIGTA_project2) 배치 시 확인된 사항

대상 저장소를 실제로 clone 해 `장준한/` 아래에 배치한 뒤 `git add -A` 로 검증했다.

- **커밋 대상 68개 파일** — src 45 / docs 5 / tests 4 / outputs .gitkeep 3 / reports 2 / 기타 9
- **제외되는 것: `장준한/data/` 전체**
  팀 저장소 루트 `.gitignore:5` 의 `data/` 패턴이 **모든 하위 경로의 `data/` 에 적용**되며,
  git 은 무시된 디렉터리 내부로 내려가지 않으므로 하위 `.gitignore` 의 negation(`!data/raw/.gitkeep`)이
  적용되지 않는다.
- 이 때문에 **데이터 준비 문서를 `data/README.md` → `docs/data_setup.md` 로 옮겼다.**
  `data/` 안에 두면 GitHub 에 올라가지 않기 때문이다.
- `data/raw/` 디렉터리가 저장소에 없어도 되도록 `common/paths.py` 의 `ensure_dirs()` 가
  `RAW_DIR` 를 생성한다(`--check` 실행 시 자동 생성).
- `outputs/*/.gitkeep` 은 정상 커밋된다(루트 `.gitignore` 에 `outputs/` 패턴이 없음).

### 12-2. 업로드 절차 (확정)

`github_release/` 는 빌드용 wrapper 이므로 올리지 않는다. **그 안의 프로젝트 폴더 내용**을 올린다.

```
github_release/dunnhumby-promotion-analysis/  의 내용물  →  <clone>/장준한/
```
