# data/processed/ 전처리 결과

> 생성 스크립트: `scripts/preprocess/build_features.py`
> 최종 실행: 2026-05-05

---

## 전처리 파이프라인 및 실행 결과

```
[Step A] 횡단보도 로드
  crosswalk_seoul.csv → 서울 전체 31,080개 (NODE 19,518 + LINK 11,562)
  NODE: POINT 좌표 그대로 사용
  LINK: LINESTRING 중점(centroid)을 위치 좌표로 산출
  좌표 누락: 0개

[Step B] 사고 필터링
  accidents_with_coords.csv (139,829건) + taas_raw.xlsx join → 나이 획득 (51,418건 매칭)
  65세↑ + 횡단중 필터 → 10,847건

[Step C] 사고↔횡단보도 매칭 → T1 생성
  10,847건 → 가장 가까운 횡단보도에 매칭 (100m 이내)
  → 8,775건 성공 (80.9%), 2,072건 탈락. 평균 매칭 거리 27.5m

[Step D] 횡단보도↔MOCT_LINK 매칭
  crosswalk_id 유니크 수: 30,224 (NODE ID + LINK ID 일부 중복 856개)
  1차: 30m 이내 매칭 → 30,037 / 30,224 유니크 ID 성공, 187개 실패
  2차: 35m fallback (실패 187개 대상)
  최종: 30,919 / 31,080 (99.5%) lanes notna, 미매칭 161개
  미매칭 161개 → lanes / max_spd / road_rank / is_oneway = NaN

[Step E] 법정동→행정동 매핑
  1차: (gu_name + dong_name) join → 39개 조합(199개 행) 실패
  2차: dong_name만으로 fallback → 잔여 미매핑 0개 (100% 해결)
  → elderly_ratio join: 31,080 / 31,080

[Step F] accident_count 집계
  0건: 24,437개 (78.6%), 1건↑: 6,643개 (21.4%)

[Step G] crosswalk_length
  LINK 타입: 링크 길이 실측값 사용
  NODE 타입: lanes × 10.57m (LINK 기준 차선당 중앙폭 중앙값)
  잔여 결측 102개: lanes NaN인 NODE 타입 (MOCT_LINK 미매칭 161개 중 NODE 타입)

[Step H] has_signal
  BallTree(haversine), 반경 30m → has_signal=1: 26,489 / 31,080 (85.2%)

[Step I] accident_count_Nm + night_accident_ratio
  accident_count_100m > 0: 29,737 / 31,080 (95.7%)

[Step J] link_count
  NODE 타입만 MOCT_NODE sjoin (50m 이내) → 18,132 / 19,518 매칭, NaN: 1,386
  LINK 타입 → link_count=0 (도로 구간 위, 교차로 아님): 11,562개
  분포: {0: 11,562, 1: 33, 2: 5,630, 3: 3,276, 4: 9,125, 5: 68}

[Step K] time_gap_basic
  NaN 102개 (crosswalk_length NaN과 동일)
```

---

## 생성 파일

| 파일 | 행 수 | 열 수 | 설명 |
|------|-------|-------|------|
| T1_accident_crosswalk.csv | 8,775 | 3 | 사고↔횡단보도 매칭 결과 |
| T2_crosswalk_features.csv | 31,080 | 19 | 횡단보도별 피처 테이블 (ML 입력) |

---

## T1 메타데이터

사고 1건이 어느 횡단보도에서 발생했는지 연결.
T2의 accident_count는 T1.groupby('crosswalk_id').size()로 집계.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| accident_id | str | TAAS 사고 구분번호 |
| crosswalk_id | int | 매칭된 횡단보도 ID |
| match_dist_m | float | 사고지점↔횡단보도 거리 (m) |

매칭 기준:
- 방법: GeoPandas sjoin_nearest (EPSG:5179)
- 최대 허용 거리: 100m (FHWA-HRT-17-106: 76~91m 권장; Hu et al. 2021 동일 기준 적용)
- 매칭률 80.9%, 평균 27.5m

참고문헌:
- Hu, W. et al. (2021). Spatial Econometric Analysis of Road Traffic Crashes. *Sustainability*, 13(5), 2492. https://www.mdpi.com/2071-1050/13/5/2492

---

## T2 메타데이터 (31,080행 × 19열)

횡단보도 1개 = 1행. ML 학습의 입력 테이블.

| 컬럼 | 타입 | 출처 | 설명 | 결측 | Spearman r |
|------|------|------|------|------|------------|
| crosswalk_id | int | crosswalk_seoul.csv | NODE: 노드ID / LINK: 링크ID (PK) | 0% | - |
| lon | float | 좌표 추출 | 경도 (WGS84) | 0% | - |
| lat | float | 좌표 추출 | 위도 (WGS84) | 0% | - |
| dong_name | str | crosswalk_seoul.csv | 법정동명 | 0% | - |
| admin_dong | str | dong_mapping.csv | 행정동명 | 0% | - |
| lanes | float | MOCT_LINK 매칭 | 차로수 | 0.5% | 0.042 |
| road_rank | float | MOCT_LINK 매칭 | 도로등급 (변별력 낮음, ML 제외 검토) | 0.5% | -0.027 |
| max_spd | float | MOCT_LINK 매칭 | 제한속도 (km/h) | 0.5% | 0.055 |
| elderly_ratio | float | elderly_pop_dong.csv | 행정동 65세↑ 인구 비율 | 0% | 0.103 |
| accident_count | int | T1 집계 | 65세↑ 횡단중 사고 수 (종속변수) | 0% | 1.000 |
| crosswalk_length | float | crosswalk_seoul.csv + 추정 | 횡단보도 길이 (m) | 0.3% | 0.060 |
| has_signal | int | ped_signal.csv | 반경 30m 내 보행자 신호등 유무 (0/1) | 0% | 0.073 |
| accident_count_50m | int | accidents_with_coords.csv | 반경 50m 전연령 사고건수 | 0% | 0.295 |
| accident_count_100m | int | accidents_with_coords.csv | 반경 100m 전연령 사고건수 | 0% | 0.273 |
| accident_count_200m | int | accidents_with_coords.csv | 반경 200m 전연령 사고건수 | 0% | 0.247 |
| night_accident_ratio | float | accidents_with_coords.csv | 반경 100m 내 야간(tmzon=야간) 사고 비율 | 0% | 0.035 |
| link_count | float | MOCT_LINK + MOCT_NODE | 교차로 연결 링크 수 (LINK 타입=0, 삼거리=3, 사거리=4 등) | 4.5% | -0.016 |
| is_oneway | int | MOCT_LINK ROAD_USE | 인접 도로 일방통행 여부 (0=양방, 1=일방) | 0.5% | -0.021 |
| time_gap_basic | float | crosswalk_length 파생 | 고령자(0.8m/s) 필요시간 - 설계기준(1.0m/s) 시간 (초) | 0.3% | 0.060 |

---

## 결측치 발생 원인

| 변수 | 결측 수 | 결측률 | 원인 | 추가 해결 가능 여부 |
|------|--------|--------|------|-------------------|
| link_count | 1,386 | 4.5% | NODE 타입이지만 50m 내 MOCT_NODE 없음. crosswalk_seoul과 MOCT_NODE 간 좌표 불일치 추정 | 불가 (거리 늘려도 인접 노드가 없음) |
| lanes / max_spd / road_rank / is_oneway | 161 | 0.5% | 35m 내 MOCT_LINK 없음. 보행자 전용도로, 사유지 접도, 노드링크 미등록 구간 추정 | 불가 (거리 늘리면 근거 없어짐) |
| crosswalk_length / time_gap_basic | 102 | 0.3% | lanes NaN인 NODE 타입 → 차선폭 추정 불가. MOCT_LINK 미매칭 161개 중 NODE 타입에만 해당 (LINK 타입은 링크 길이 직접 보유) | 불가 (lanes 없으면 추정 불가) |

> **모델 처리**: XGBoost / LightGBM / RandomForest는 결측값을 자체 분기 처리하므로 별도 imputation 없이 학습 가능.

---

## 전처리 주요 결정 사항

### MOCT_LINK 매칭 기준: 30m → 35m fallback

임용빈 외(2024)는 L-function과 KDE로 서울시 보행사고의 공간 군집 범위를 분석한 결과 보행자 사고 30.7m, 차량 사고 35.7m를 제시. 1차 30m 기준으로 187개 미매칭 발생 → 35m fallback 적용.

- 1차(30m): 30,037 / 30,224 유니크 ID 성공, 187개 실패
- 2차(35m fallback): 최종 30,919 / 31,080 (99.5%), 미매칭 161개

참고문헌:
- 임용빈 외(2024). L-function과 KDE를 이용한 서울시 보행교통사고 잦은 곳의 공간적 범위 설정과 특성 분석. *교통연구*. https://www.jkst.or.kr/articles/article/X8PY/

### crosswalk_length: NODE 타입 추정

crosswalk_seoul.csv에서 LINK 타입은 `링크 길이` 실측값이 있지만, NODE 타입(POINT geometry)은 길이 개념이 없어 NaN. LINK 타입 실측값에서 차선당 중앙폭을 계산해 NODE에 적용.

```
median_width = median(crosswalk_length / lanes)  ← LINK 타입에서만 계산 (10.57m)
crosswalk_length(NODE) = lanes × median_width
```

### 법정동→행정동 매핑: dong_name fallback

dong_mapping.csv(국가데이터처 2025.07)와 crosswalk_seoul.csv(서울시 2026.05)의 시군구명이 39개 조합(199개 행)에서 불일치. 두 데이터의 행정경계 기준 차이로 추정. (gu_name + dong_name) 1차 매칭 실패 시 dong_name만으로 2차 매칭 → 199개 전부 해결.

### accident_count_Nm 반경 선택 방법

50m / 100m / 200m 세 반경으로 컬럼을 모두 생성하고, ML 모델 학습 후 accident_count와의 Spearman 상관계수가 가장 높은 반경을 최종 채택. 현재 전처리 결과에서는 50m(r=0.295) > 100m(r=0.273) > 200m(r=0.247) 순.

### 공간 매칭 근거

| 매칭 | 거리 | 근거 |
|------|------|------|
| 사고↔횡단보도 | 100m | FHWA-HRT-17-106 (76~91m 권장); Hu et al. (2021) 동일 기준 |
| 횡단보도↔MOCT_LINK (1차) | 30m | 임용빈 외(2024) — 보행자 사고 군집화 30.7m |
| 횡단보도↔MOCT_LINK (2차) | 35m | 임용빈 외(2024) — 차량사고 군집화 35.7m (fallback) |
| 횡단보도↔MOCT_NODE | 50m | NODE 미매칭 시 link_count=NaN |
| 보행자신호등↔횡단보도 | 30m | 신호등이 횡단보도 바로 옆에 설치되는 기준 |

---

## 변수 한계 및 생성 불가 변수

### 생성 불가 변수

| 컬럼 | 이유 | 검토한 데이터 |
|------|------|------|
| has_median | MOCT_LINK에 중앙분리대 전용 컬럼 없음. 서울시 중앙분리대 현황(2018) 데이터는 좌표 없이 도로 이름만 있어 공간 매칭 불가 | 서울시 중앙분리대 및 무단횡단방지시설 현황(20181231) — 9개 도로사업소별 xlsx, 좌표 없음 |
| time_gap_actual | 횡단보도별 실제 녹색시간 데이터 없음. 신호등 표준데이터(data.go.kr 15113147)는 신호등 위치·광원·부착방식만 있고 녹색시간 없음. V2X API는 실시간이라 과거 분석 불가 | 서울시 신호등 표준데이터 |

### time_gap_basic 한계

time_gap_basic은 설계 기준(1.0m/s)으로 녹색시간을 역산하여 계산한 **추정값**이다. 실제 신호 운영 데이터가 없어서 생기는 한계가 두 가지다.

**과대추정 가능성**: 노인보호구역이나 사고 다발 지역은 이미 녹색시간을 연장하여 운영하는 경우가 있다. 이런 구간은 time_gap_basic이 위험하다고 계산해도 실제로는 덜 위험할 수 있다.

**과소추정 가능성**: 일부 구간은 설계 기준보다 짧은 녹색시간으로 운영될 수도 있다.

다만 서울시 일반 횡단보도 대다수는 설계 기준 그대로 운영되며, 연구의 핵심 문제 제기(설계 기준 1.0m/s가 고령자에게 부족하다는 것) 자체가 이 가정에 기반하므로 완전히 틀린 전제는 아니다. 논문 한계 절에 "실제 신호 운영 데이터 미확보로 인한 추정값이며, 노인보호구역·사고 다발 구간 등 예외 구간에서 오차 가능성 있음"으로 명시한다.
