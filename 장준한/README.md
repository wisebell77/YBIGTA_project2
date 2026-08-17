# Dunnhumby Promotion Incrementality Analysis

dunnhumby *The Complete Journey* (2,485 households × ~2 years × 2.59M transaction lines)
로 전단지 판촉의 **증분성(incrementality)** 을 추정한 재현 가능한 분석 파이프라인.

---

## Project Question

> **Do promotions create incremental demand, or simply pull future demand forward?**
>
> 판촉은 새로운 수요를 만드는가, 아니면 미래 수요를 앞당겨 쓰는 것뿐인가?
> 그리고 만들어낸 수요에 비해 내준 할인은 얼마나 되는가?

---

## Key Findings

**PART A — 전단지 노출 ITT (주 인과추정 설계)**

- 카테고리 **구매확률 +24.3%** (95% CI [23.25, 25.37])
- 0구매 포함 **총수량 +34.4%** (95% CI [32.74, 36.09])
- 강한 시간통제(`cat×month` + `WEEK`) 적용 시에도 **수량효과 +27.0%** 유지
- **56일 이내 통계적으로 유의한 future payback이 관측되지 않았다**
  (M3 ΔQ56 = +0.000158, t = 0.16, 95% CI [−0.001764, +0.002079])
- 정가환산 **REG +39.5%** vs 실제 **SALES +26.1%**
  → 두 상대효과 추정치 사이 **value-to-revenue gap 13.4%p**

**PART B — 실현 딥할인 (관측적/탐색적)**

- 카테고리 이질성은 **다중검정(BH-FDR) 보정 후 robust한 차이 0/83**
- 일부 **High 고객특성 비교**(17개 비교 중 6개)에서 FDR 보정 후에도 음(−)의 관측적 연관 유지
- **할인 깊이(discount depth)가 다음 실험 레버** — 깊은 할인은 더 많은 물량과 함께
  낮은 realized revenue 및 낮은 정상가 전환과 연관

### ⚠️ 수치 해석 시 주의

- **13.4%p는 두 상대효과 추정치의 차이이며, 이에 대한 정식 difference test는 수행하지 않았다.**
  두 상대효과는 서로 다른 control mean을 분모로 계산된다.
- **High 고객 결과는 서로 배타적인 6개 세그먼트가 아니다.** 동일 household가 여러 High 특성을
  동시에 가질 수 있어 비교군끼리 중첩된다.
- 점추정 기준 cumulative ratio(≈101.5%)와 CI 환산 payback bound(≈17.1%)는 **참고값**이며,
  후자는 **formal equivalence test가 아니다.**

---

## Analysis Design — PART A / PART B

이 저장소에는 **성격이 다른 두 분석**이 있다. 절대 같은 표에서 직접 비교하지 않는다.

| | **PART A** | **PART B** |
|---|---|---|
| Phase | 0 – 4A | 4B – 5C |
| 처치 | 전단지 노출 (`mailer <> '0'`, category×store×week) | 실현 딥할인 (할인율 ≥ 30%) |
| 성격 | **주 인과추정 설계 (ITT, 식별가정 필요)** | **관측적 / 탐색적** |
| 처치 할당 | 구매자가 실제 할인상품을 고른 결과가 아니라 **사전에 존재한 노출기회**를 사용. realized-discount 설계보다 자기선택 위험은 낮지만 **category/time-specific confounding 가능성은 남는다.** | **가구가 스스로 딥할인을 선택** — 선택편의 미제거 |
| 쓸 수 있는 표현 | "효과", "증분" | **"차이", "연관", "패턴"만** |

핵심 식별 전략은 **`household_key × COMMODITY_DESC` 고정효과** — *가구가 스스로의 대조군*.
SE는 `household_key` 클러스터.

---

## Repository Structure

```
├── run_pipeline.py           단일 엔트리포인트
├── requirements.txt
├── config/config.example.yaml
├── data/raw/                 원본 CSV 를 여기에 (git 제외 — 없으면 --check 가 만들어 준다)
├── src/
│   ├── common/               paths · config · utils · fe_estimator
│   ├── phase0_prepare/       raw → parquet 캐시
│   ├── phase1_validation/    원자료 사실 재현
│   ├── phase2_design/        전단지 처치 정의
│   ├── phase3a_conditional/  occasion 조건부 효과
│   ├── phase3b0_total_demand/ 기회패널 · 총수요 (PART A 주 결과)
│   ├── phase3b1_incrementality/ 56일 future payback
│   ├── phase4a_robustness/   robustness 통합 + 95% CI
│   ├── phase4b_relationship/ 딥할인 후 매장활동 (PART B)
│   ├── phase5a_category/     카테고리 포트폴리오 + FDR
│   ├── phase5b_crm/          period-split RFM + FE + FDR
│   ├── phase5c_conversion/   전환 · 할인깊이 · 마진 시나리오
│   └── phase8_finalize/      최종 표 · Tableau
├── reports/                  최종 보고서 (한국어)
├── docs/                     데이터 준비 · 방법론 · 데이터 사전 · 재현 가이드
├── reference_results/        원 full run 의 확정 결과 (파이프라인 입력 아님)
├── outputs/                  실행 산출물 (git 제외)
└── tests/
```

---

## Data Setup

원본 데이터는 저장소에 포함하지 않는다 (이용약관 + `causal_data.csv` 약 664MB).
받은 CSV 를 `data/raw/` 에 그대로 두면 된다. 필수 3종:

`transaction_data.csv` · `product.csv` · `causal_data.csv`

컬럼 요구사항과 데이터 규약은 **[`docs/data_setup.md`](docs/data_setup.md)** 참조.

---

## Installation

**Windows**
```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux**
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Python 3.9+ 필요. Windows 전용 의존성은 없다. 46.7M 행 패널을 다루므로 **RAM 16GB 이상 권장**
(적으면 `config/config.yaml` 의 `duckdb_memory_limit` 을 낮출 것).

---

## Quick Start

```bash
python run_pipeline.py --check     # 환경·데이터 점검 (분석 미실행)
python run_pipeline.py --all       # 전체 파이프라인
```

기타: `--phase phase3b0` (단일) · `--from phase3b0` (이후 전부) · `--force` (재실행)
· `--smoke` (소표본 점검)

---

## Pipeline

| Phase | 내용 | PART |
|---|---|---|
| `phase0` | raw CSV → parquet 캐시, DuckDB 뷰 | — |
| `phase1` | 원자료 사실 재현 게이트 (라인 수·할인 밀도 등) | — |
| `phase2` | 전단지 ITT 처치 정의, 대조군 병존 셀 확인 | A |
| `phase3a` | occasion 마트 + 조건부 효과 + 딥할인 참조설계 | A |
| `phase3b0` | 46.7M shopping-opportunity 패널 + 총수요 효과 + 시간통제 | A |
| `phase3b1` | 미래창(7/14/28/56일) 생성 + payback 추정 + 증분성 곡선 | A |
| `phase4a` | 저장 결과만으로 robustness 통합 + 95% CI (신규 회귀 없음) | A |
| `phase4b` | 딥할인 anchor + 28일 매장활동 | B |
| `phase5a` | 카테고리 포트폴리오 + BH-FDR | B |
| `phase5b` | period-split RFM + hh×cat FE + BH-FDR | B |
| `phase5c` | trial 전환 · 할인깊이 밴드 · 마진 시나리오 | B |
| `phase8` | 최종 핵심수치표 · Decision Matrix · Tableau 산출 | — |

각 phase 완료 시 `outputs/checkpoints/<phase>.done` 생성.
재실행 시 **체크포인트와 실제 산출물이 모두 정상일 때만** skip 한다.

---

## Outputs

- `outputs/tables/` — 단계별 결과 CSV, `FINAL_key_results.csv`
- `outputs/tableau/` — 대시보드용 tidy 데이터셋, `07_final_decision_matrix.csv`
- `reports/` — 최종 통합 보고서 · 한 장 요약

`reference_results/FINAL_key_results.csv` 는 **원 full run 의 확정 결과**다.
**파이프라인 입력이 아니며**, 재현 결과와 비교하는 용도로만 쓴다.

---

## Reproducibility

새 PC 기준 절차는 **[`docs/reproducibility.md`](docs/reproducibility.md)** 참조.
방법론 상세는 [`docs/methodology.md`](docs/methodology.md),
분석 흐름은 [`docs/analysis_flow.md`](docs/analysis_flow.md).

---

## Limitations

1. **표본 범위** — `causal_data` 커버리지 때문에 **115개 점포 / WEEK 9–101** 로 한정된다.
   점포 수로는 전체의 19.8% 지만 매출 기준으로는 98.49% 다. (점포 수가 아니라 매출 비중으로 제시할 것)
2. **`causal_data` 는 이벤트 로그다** — 미노출 행이 존재하지 않는다. 조인 실패를 "미노출(대조군)"
   으로 처리하는 가정 위에 전체 설계가 서 있다.
3. **후속 전단지 노출을 통제하지 않았다** (post-treatment 변수). 노출 anchor 의 28일 내 재노출률은
   86.9%, 미노출은 41.7% 로 크게 다르다. 주 결과는 natural-course ITT 이며, 이 교란은 시간통제로 다뤘다.
4. **`category × week` FE 는 사용할 수 없다** — 처치 변동의 97.8% 를 흡수해 식별이 붕괴한다.
   최대 통제는 `cat×month` + `WEEK` 이며, 이조차 처치변동의 약 52.9% 를 함께 제거한다(하한으로 읽을 것).
5. **PART B 전체가 관측적이다** — 딥할인은 가구의 자기선택이며 인과로 읽을 수 없다.
6. **Phase 5A 의 FDR 은 근사 p-value 기반** — 원 CSV 에 p 가 저장되지 않아 공표 CI
   (`beta ± 1.96·SE`)에서 SE 를 역산하고 정규근사로 p 를 계산했다. 원 회귀 p 와 완전히 동일하지 않다.
7. **gross margin 은 가정이다** — 원가·vendor funding·rebate·프로모션 운영비 정보가 없다.
   break-even ≈40.34% 는 **시나리오 임계값이지 실측 ROI 가 아니다.**
8. **용량(pack size) 정보 부재** — "수량 증가가 대용량팩 선택 아닌가"에 직접 답할 수 없어
   정가환산액을 병기했다.
9. **원본 데이터는 저장소에 없다** — 직접 받아 `data/raw/` 에 두어야 한다.
10. **미실행 robustness** — Phase 3B-1 의 28일 M3, Cox/AFT 생존분석,
    `store×cat + WEEK` 장시간 회귀, 시간통제 하 SALES beta, formal equivalence test 는
    실행하지 않았다. 56일 주결론에 필요하지는 않지만, **결론을 바꾸지 않는다고 입증된 것은 아니다.**

---

## License

**License to be determined by repository owner.** — [`LICENSE_NOTE.md`](LICENSE_NOTE.md) 참조.
데이터는 저장소 라이선스와 무관하게 dunnhumby 이용약관을 따른다.
