# 서울 중구 스마트 횡단보도 SUMO 모델

이 디렉터리는 기존 `sumo_2d` 모델을 수정하지 않고 새로 만든 OSM 기반 SUMO 파이프라인이다.

## 실행 흐름

```text
preprocess.py       -> 위험도 상위 후보 선정
build_networks.py   -> 후보별 OSM 네트워크 생성
generate_demand.py  -> 차량/보행자 수요 생성
run_simulations.py  -> baseline/smart TraCI 실행
collect_metrics.py  -> seed별 및 평균 지표 저장
generate_reports.py -> 보고서와 그림 생성
main.py             -> 전체 실행
```

## 기본 실행

```bash
python3 smart_crosswalk_sumo/main.py \
  --top_n 20 \
  --seeds 42 43 44 \
  --sim_duration 1800 \
  --warmup 300
```

실행할 때마다 기본적으로 아래처럼 시행별 폴더가 만들어진다.

```text
result/YYYY-MM-DD_HH-MM-SS/
├── run_metadata.json
├── outputs/
├── figures/
└── sumo_nets/
```

폴더명을 직접 정하고 싶으면:

```bash
python3 smart_crosswalk_sumo/main.py --run_name test_01 --top_n 1 --seeds 42
```

기본 입력은 새 모델 안에 복사된 정제 데이터다.

```text
smart_crosswalk_sumo/data/T1_accident_crosswalk.csv
smart_crosswalk_sumo/data/T2_crosswalk_features.csv
```

## 빠른 전처리 확인

SUMO나 OSM 다운로드 없이 후보 선정만 확인하려면:

```bash
python3 smart_crosswalk_sumo/main.py --preprocess_only --top_n 20
```

## 주요 출력

```text
result/YYYY-MM-DD_HH-MM-SS/outputs/candidates.csv
result/YYYY-MM-DD_HH-MM-SS/outputs/demand_params.csv
result/YYYY-MM-DD_HH-MM-SS/outputs/simulation_results_seed.csv
result/YYYY-MM-DD_HH-MM-SS/outputs/simulation_results.csv
result/YYYY-MM-DD_HH-MM-SS/outputs/report_1_simulation_results.csv
result/YYYY-MM-DD_HH-MM-SS/outputs/report_2_comparison.md
result/YYYY-MM-DD_HH-MM-SS/outputs/report_3_tradeoff.md
result/YYYY-MM-DD_HH-MM-SS/outputs/report_4_methodology.md
result/YYYY-MM-DD_HH-MM-SS/figures/tradeoff_scatter.png
result/YYYY-MM-DD_HH-MM-SS/figures/pet_comparison_bar.png
result/YYYY-MM-DD_HH-MM-SS/figures/crosswalk_map.html
```

## PET 관련 주의

이 모델은 실제 trajectory pair 기반 PET를 직접 계산하지 않는다.

- `PET_A_proxy`: 차량이 crossing 주변 차량 edge를 벗어난 시각과 보행자 crossing 진입 시각의 차이
- `PET_B_surrogate`: 보행 녹색 종료 시점의 전적색 시간과 보행자 잔여 횡단시간의 차이

보고서에서는 PET가 아니라 `PET proxy` 또는 `surrogate PET`로 표기해야 한다.

## 환경

```bash
export SUMO_HOME=/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO
python3 -m pip install pandas numpy scipy matplotlib requests
```

`sumolib`과 `traci`는 SUMO Python tools 경로에서 로드되어야 한다. 이 워크스페이스 환경에서는 둘 다 import 가능하다.
