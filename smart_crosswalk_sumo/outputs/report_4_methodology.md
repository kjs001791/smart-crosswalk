# 시뮬레이션 방법론 보고서

## 1. SUMO 선택 근거

SUMO는 OpenStreetMap 기반 실제 도로망 생성, 보행자-차량 통합 미시 시뮬레이션, TraCI Python API 기반 실시간 신호 제어가 가능하므로 스마트 횡단보도 실험에 적합하다.

## 2. PET Proxy 정의 및 계산

학술적 PET는 첫 번째 도로 이용자가 상충구역을 벗어난 시각과 두 번째 도로 이용자가 동일 구역에 진입한 시각의 차이다. 이 모델은 실제 trajectory pair를 완전히 구성하지 않으므로 PET를 단정하지 않고 proxy/surrogate로 표기한다.

### Method A: TraCI Position-Based PET Proxy

차량이 crossing 주변 차량 edge를 벗어나는 시각을 기록하고, 보행자가 crossing edge에 처음 진입한 시각과 비교한다.

```text
PET_A_proxy = T_ped_enter - max(T_vehicle_exit_before_ped_enter)
```

30초보다 오래 떨어진 이벤트는 무관한 이벤트로 제외한다.

### Method B: Clearance-Based Surrogate PET

보행 녹색에서 비보행 현시로 전환되는 순간, crossing에 남아있는 보행자의 잔여 횡단시간과 전적색 시간을 비교한다.

```text
PET_B_surrogate = all_red_time - remaining_distance / current_ped_speed
```

- `< 0`: 전적색 시간 안에 횡단 완료 불가
- `< 1.34`: 고위험
- `1.34 ~ 2.88`: 중위험
- `>= 2.88`: 저위험

## 3. 스마트 횡단보도 신호 연장 로직

- 연장 단위: 5초
- 최대 연장: 1회
- 트리거: 잔여 보행 녹색 10초 이하, crossing 위 보행자 감지
- 센서 false negative: 5%
- 전적색 시간: 3초

## 4. 실험 설계

- 후보 횡단보도: 위험도 상위 20개
- 시나리오: baseline / smart
- seed: 42, 43, 44
- 시뮬레이션 시간: 1800초
- 워밍업: 300초
- 차량 수요: AADT 기반 seed별 노이즈
- 보행자 수요: 지수분포, lambda 100~600명/시

## 5. 교통량 지표

| 지표 | 정의 | TraCI 함수 |
|---|---|---|
| 차량 평균 지체 | 차량별 누적 대기시간 평균 | `vehicle.getAccumulatedWaitingTime()` |
| 차량 최대 지체 | 차량별 누적 대기시간 최대 | 동일 |
| 평균 대기행렬 | 접근 차선 정지 차량 수 평균 | `lane.getLastStepHaltingNumber()` |
| 최대 대기행렬 | 접근 차선 정지 차량 수 최대 | 동일 |

## 6. 데이터 한계 및 가정

- AADT는 추정값이므로 실제 관측 교통량이 아니다.
- 횡단보도 길이는 `LANES * 3.5m`로 추정했다.
- 보행자 수요는 유동인구 데이터 부재로 지수분포를 가정했다.
- OSM의 보행자 인프라 자동 생성은 지점별로 실패할 수 있으므로 실패 케이스를 별도 기록한다.
- PET 계열 값은 실제 PET가 아니라 proxy/surrogate 지표다.
