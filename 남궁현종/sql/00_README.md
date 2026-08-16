# 분석 소스코드 (BigQuery SQL)

프로젝트 `ybigta-505002` 기준. 원본 데이터는 `sql_study.*`(CSV 8종 업로드본), 모든 산출 테이블은 `dunnhumby_mart.*`에 생성된다.
실행: `bq query --use_legacy_sql=false < 파일.sql` (Windows에서 멀티라인은 `cmd /c "bq.cmd query ... < 파일.sql"` 리다이렉션 사용. CREATE+SELECT가 한 파일에 있으면 CLI가 출력에서 죽을 수 있으니 분리 실행 권장).

폴더 번호 = 분석 진행 순서. 각 단계의 배경·결과 해석은 `../산출물/분석여정_전체흐름.md` 해당 절 참조.

## 10_mart — 기반 마트 구축 (여정 §1~2)
BigQuery 작업 이력에서 복원한 초기 세션 코드. 파일명 = 생성 테이블명.
- `fct_transaction.sql` — 정제 팩트 테이블. **정가/할인 분해의 기준 구현**(정가 = sales_value − retail_disc − coupon_match_disc; coupon_disc는 vendor_funded로 분리). 이상치 플래그(is_bulk_outlier 등) 포함
- `dim_household / dim_product / mart_household_week / mart_basket` — 차원·주간 패널(0 채움)
- `mart_campaign_exposure / mart_household_treatment` — 캠페인 노출 창
- `mart_household_churn / mart_household_rfm` — 초기 이탈·RFM 정의 (이후 이탈 측정 불가 판정의 대상)
- `mart_causal_psw / mart_causal_product_week` — causal_data 집계 초기 버전

## 20_segmentation — 할인의존도 세그먼트와 이탈 검증 (여정 §3)
- `q_quintile.sql` → `mart_household_disc_quintile` (금액 기준 할인의존도 5분위)
- `q_dd_churn.sql` → `mart_hh_dd_churn` (**누출 차단**: 의존도는 DAY≤547, 이탈은 DAY 548~711 홀드아웃)
- `q_churn_def.sql / q_ret.sql / q_ret2.sql` — 이탈 측정 불가 판정(재구매율 96~98%), 리텐션 null 확인
- `q_dec.sql / q_shape.sql` — 10분위·2%p 구간 곡선(역U자), `q_margin.sql` — 분위별 할인/매출 비중, `q_hist.sql` — 분포 추출

## 30_screening — 카테고리 스크리닝 (여정 §4)
- `q_cat.sql` — Q5−Q1 회수율 스크리닝. **인과 아님**, 후보 선별용 (이후 인과와 2/3 불일치 확인됨)

## 40_mailer_causal — 전단지 준실험 (여정 §5~7)
- `q_causal_clean.sql` → `mart_causal_clean` — **mailer 코드 분리**(광고 A,C,D,F,H,L / 쿠폰 J,P / 무료 X,Z), dedup
- `q_occ.sql` → `mart_occ_3cat` (3개 카테고리 구매기회), `q_main1.sql / q_cann.sql` — 당일 효과·56일 잠식
- `q_strat0.sql / q_pure.sql / q_pure1.sql / q_cann2.sql` — **진열 오염 발견·분리** (display=0 한정 재추정)
- `q_occ_all.sql` → `mart_occ_all` (전 카테고리 140만 구매기회), `q_ball.sql / q_bcann.sql / q_final.sql` → `mart_cat_matrix` (72개 판정. ⚠️ net_total 분류는 이후 70_validation/q_fix로 당일 기준 수정됨)
- `q_dose.sql` — 지면 위치 용량반응(1면 vs 내지), `q_het1.sql / q_split.sql` — 5분위 이질성 + 분할표본 검증
- `q_dept.sql / q_sc.sql / q_export.sql` — 부서 집계·추출

## 50_display_panel — 진열 점포×주차 패널 (여정 §8)
- `q_ident.sql` — 식별 진단(진열 18.0% vs mailer 0.22%), `q_panel.sql` → `mart_psw_panel` (534만 행 균형 패널)
- `q_fe2.sql / q_twoway.sql` — 상품-주차 FE(1.69배) / 완전 DiD(1.42배), 반복 demeaning + 상품 클러스터 SE
- `q_price2.sql` — 가격 교란 소멸(10.58%p→0.10%p), `q_plac2.sql` — lead 플라시보
- `q_event.sql / q_mailfe.sql` — 진열·전단지 개시 이벤트 스터디 (편의 10.5% 정정, mailer 교차상품 식별)

## 60_coupon — 쿠폰 staggered DiD (여정 §10.1)
- `q_gap.sql / q_wkmap.sql / q_cpanel.sql` — 설계 진단, `q_cdid.sql` → `mart_coupon_did`
- `q_cev.sql` — 전체 지출 이벤트 스터디, `q_csel.sql` — 선택 진단(4배)·퍼널·이질성
- `q_ctgt.sql / q_ctgt2a / q_ctgt2b` — 표적상품 ITT(null) + 사용 분해

## 70_validation — 자체 감사·강건성 (여정 §9, §10.2~3)
- `q_audit1/2b.sql` — causal 커버리지 감사(0.002%), `q_audit3.sql` — 공통 카테고리 재가중, `q_audit4.sql` — SKU 믹스
- `q_fix.sql` — **분류 오류 수정**(BH FDR + 당일 기준; "49% 손실" 철회의 근거), `q_wins.sql` — winsorize 민감도
- `q_size/q_parse/q_sdunit/q_vol.sql` — 규격 파싱(67.5%)·용량 기준 재추정, `q_xval*.sql` — 설계 교차검증(부호 반전 #4)
- `q_synth*.sql / q_mech.sql` — 팀원 결과 재검증(처치 교체 시 −$1.53→−$0.44), `q_halo.sql` — 바스켓 halo(통합)
- `q_halo_cat.sql` — **halo 카테고리·부서 분해**(여정 §10.4). 농산물 집객 가설 기각(PRODUCE halo +$0.83 t=1.83로 식품 부서 최저), 확대 명단은 focal이 5배 과소평가

## 80_python_local — 로컬 재현 (BigQuery 무관, `data/` 필요)
- `verify_*.py` (canniv/mailer/t2) — DuckDB로 원본 CSV에서 DA 아이디어 PDF 수치를 재현 (여정 §1.3)
- `build_local_duckdb.py` — **BigQuery 마트 전체를 로컬 재구축** (`fct_transaction`·`mart_causal_clean`·`mart_occ_all`). BigQuery 결과와 완전 일치 검증됨: 금액 합계(net 8,057,463 / gross 9,463,374 / 할인 1,405,911), 구매기회 1,405,014건
- `verify_halo_cat.py` — 위 로컬 DB에서 halo 분해 재현. BigQuery `q_halo_cat.sql` 결과와 72개 카테고리 6개 지표 **최대절대차 0.000000**

## Windows에서 파일 SQL 실행 (2026-08-16 실측)
`cmd /c "bq.cmd query ... < file.sql"`은 SQL이 `cmd` stdin으로 들어가 대화형 셸로 멈춘다. PowerShell 파이프는 BOM이 붙어 `Illegal input character "\357"`로 실패한다. **Git Bash 리다이렉션만 정상 동작**한다.
```bash
export PATH="/c/Users/<user>/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin:$PATH"
bq.cmd --location=asia-northeast3 query --use_legacy_sql=false --format=csv < 파일.sql
```
