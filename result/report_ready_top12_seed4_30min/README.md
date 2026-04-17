# 보고서용 스마트 횡단보도 시뮬레이션 결과

## 실행 개요

- 실행 폴더: `result/report_ready_top12_seed4_30min`
- 목적: 서울 중구 위험도 상위 횡단보도에 대한 baseline/smart 비교 결과 생성
- 분석 대상: 위험도 상위 12개 횡단보도
- seed: 42, 43, 44, 45
- 시나리오: baseline, smart
- SUMO 실행 수: 12개 지점 x 4개 seed x 2개 시나리오 = 96회
- 분석 구간: 30분(`sim_duration=1800`)
- 워밍업: 5분(`warmup=300`)
- TraCI step length: 0.5초
- 네트워크: 기존 OSM/SUMO 네트워크를 실행 폴더 내부 `sumo_nets/`로 복사해 사용

## 생성 파일

### 핵심 결과

- `outputs/simulation_results_seed.csv`: 지점/seed/시나리오별 원시 결과
- `outputs/simulation_results.csv`: 지점/시나리오별 seed 평균 결과
- `outputs/comparison_table.csv`: baseline 대비 smart 비교표
- `outputs/report_1_simulation_results.csv`: 보고서용 결과표
- `outputs/report_2_comparison.md`: 일반 횡단보도 vs 스마트 횡단보도 비교 보고서
- `outputs/report_3_tradeoff.md`: 보행 안전 vs 차량 지체 트레이드오프 보고서
- `outputs/report_4_methodology.md`: 방법론 보고서

### 그림

- `figures/tradeoff_scatter.png`: 안전 개선율과 차량 지체 증가량 산점도
- `figures/pet_comparison_bar.png`: PET_B surrogate 고위험 건수 비교 막대그래프
- `figures/crosswalk_map.html`: 후보 횡단보도 지도

### 실행 재현 정보

- `run_metadata.json`: 파이프라인 실행 인자
- `report_preset.json`: 보고서용 프리셋 설정
- `sumo_nets/`: 이번 보고서용 실행에 사용한 SUMO 네트워크, route, sumocfg 사본

## 검증 결과

- `simulation_results_seed.csv`: 96행 생성 완료
- `simulation_results.csv`: 24행 생성 완료
- 실패 케이스: 없음
- baseline/smart 두 시나리오 모두 12개 지점에 대해 생성됨

## 주요 수치

시나리오 평균 기준:

| 시나리오 | PET_B surrogate 고위험 평균 | 고령자 미완료 횡단 평균 | 차량 평균 지체 평균(초) | 최대 대기행렬 평균 |
|---|---:|---:|---:|---:|
| baseline | 4.312 | 1.438 | 15.975 | 2.062 |
| smart | 1.646 | 0.396 | 15.967 | 2.146 |

baseline 대비 smart 개선이 관측된 주요 지점:

| 횡단보도ID | 행정동 | PET_B 고위험 감소율 | 고령자 미완료 감소율 | 차량 평균 지체 증가 |
|---:|---|---:|---:|---:|
| 8430 | 신당동 | 73.404% | 76.471% | +0.090초 |
| 71666 | 장충동 | 56.322% | 77.778% | -0.008초 |
| 9494 | 신당동 | 38.462% | 37.500% | -0.182초 |

## 해석 주의

- PET는 실제 trajectory pair 기반 PET가 아니라 `PET_A_proxy`, `PET_B_surrogate`이다.
- 차량 수요는 추정 AADT 기반이고, 보행자 수요는 지수분포 기반 생성값이다.
- `proj.db` 관련 경고가 실행 로그에 반복되었으나, 96회 실행은 모두 완료되었고 실패 케이스는 발생하지 않았다.
- 본 결과는 보고서 및 발표용 비교 결과로 적합하며, 정책 결론을 위해서는 실제 수요 보정과 seed 수 확대가 추가로 필요하다.

## 재실행 명령

```bash
python3 scripts/run_report_simulation.py
```

기본 프리셋은 `top_n=12`, `seeds=42 43 44 45`, `sim_duration=1800`, `warmup=300`, `traci_step_length=0.5`이다.
