# data/processed/ 전처리 결과

> 생성 스크립트: `notebooks/02_preprocessing.ipynb`
> 최종 갱신: 2026-04-16

## 전처리 파이프라인

```text
[Step A] 횡단보도 필터링
  crosswalk_seoul.csv (31,080) → 중구 1,098개 (NODE 674 + LINK 424)
  LINK는 LINESTRING 중점(centroid)을 위치 좌표로 산출

[Step B] 사고 필터링
  accidents_with_coords.csv → 65세↑ + 횡단중 + 중구 → 342건

[Step C] 사고↔횡단보도 매칭 → T1 생성
  342건을 가장 가까운 횡단보도에 매칭 (100m 이내)
  → 296건 성공 (87%), 46건 탈락. 평균 매칭 거리 30.6m

[Step D] 횡단보도↔노드링크 매칭
  1,098개를 가장 가까운 도로 링크에 매칭 (30m 이내)
  → 1,062개 성공 (97%), LANES/ROAD_RANK/MAX_SPD 획득

[Step E] 보조 데이터 산출
  ① 동별 고령인구 → 중구 15개 행정동 노인비율
  ② 도로등급별 AADT → 교통량 147개 지점에서 등급별 평균
  ③ 법정동→행정동 매핑 (73개 법정동 → 15개 행정동)

[Step F] T2 조립
  위 결과를 횡단보도ID 기준으로 전부 합침 → 1,098행 × 11열
```