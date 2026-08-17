# 재현 가이드 (Reproducibility)

완전히 새 PC 기준 절차.

## 1. clone

```bash
git clone <repository-url>
cd dunnhumby-promotion-analysis
```

## 2. 가상환경 + 설치

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

Python 3.9 이상. RAM 16GB 이상 권장.

## 3. 원본 데이터 배치

dunnhumby *The Complete Journey* CSV 를 받아 **`data/raw/`** 에 둔다.
필수: `transaction_data.csv`, `product.csv`, `causal_data.csv`
(선택: `hh_demographic.csv`, `campaign_*.csv`, `coupon*.csv`)

컬럼 요구사항은 [`data_setup.md`](data_setup.md) 참조.
데이터는 `.gitignore` 로 차단되어 커밋되지 않는다.

## 4. 사전 점검

```bash
python run_pipeline.py --check
```

Python 버전 · 패키지 · config · **raw 파일 존재 여부** · 쓰기 권한 · 체크포인트를 확인한다.
파일이 없으면 `Missing required data files:` 목록으로 정확히 알려준다 (traceback 아님).

## 5. 실행

```bash
python run_pipeline.py --all
```

옵션:

| 명령 | 의미 |
|---|---|
| `--phase phase3b0` | 해당 phase 만 |
| `--from phase3b0` | 해당 phase 부터 끝까지 |
| `--force` | 체크포인트 무시하고 재실행 |
| `--smoke` | 소표본으로 코드 동작만 빠르게 확인 |

### 체크포인트

각 phase 완료 시 `outputs/checkpoints/<phase>.done` 이 생성된다.
재실행 시 **`.done` 이 있고 동시에 필수 산출물이 실제로 존재·비어있지 않을 때만** skip 한다.
산출물이 사라졌으면 자동으로 재실행한다.

## 6. 검증

```bash
python -m pytest -q
```

원본 데이터가 없으면 data-dependent 테스트는 자동 skip 된다.

## 7. 결과 확인

- `outputs/tables/FINAL_key_results.csv` — 최종 핵심수치
- `outputs/tableau/07_final_decision_matrix.csv` — Decision Matrix
- `reports/FINAL_integrated_report.md` — 최종 통합 보고서

`reference_results/FINAL_key_results.csv` 는 **원 full run 의 확정 결과**다.
파이프라인이 읽지 않으며, 재현 결과와 대조하고 싶을 때만 수동으로 비교한다.

## 예상 소요시간

전체 실행은 수 시간 규모다. 특히 다음이 오래 걸린다.

- Phase 3B-0 `opportunity.parquet` 생성 (46.7M 행)
- Phase 3B-0 시간통제 (3중 FE 반복 demeaning — 1건에 30분 이상 가능)
- Phase 3B-1 미래창 생성 및 추정

⚠️ 동시에 heavy Python 프로세스를 2개 넘게 띄우지 말 것. 16GB RAM 에서 페이징이 발생하면
1건 처리 시간이 3~5배로 늘어난다.
