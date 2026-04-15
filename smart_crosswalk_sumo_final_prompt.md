# Codex Prompt: 서울 중구 스마트 횡단보도 SUMO 시뮬레이션 최종 설계

## 프로젝트 개요

서울 중구 횡단보도 데이터와 OpenStreetMap 실제 도로망을 활용해 일반 횡단보도와 스마트 횡단보도를 SUMO로 비교 시뮬레이션한다.

비교 시나리오:

- `baseline`: 일반 횡단보도, 고정 신호
- `smart`: 보행자 감지 기반 보행 신호 자동 연장

분석 목표:

- 횡단보도별 사고 proxy 지표 산출
- 횡단보도별 차량 교통량/지체 지표 산출
- 일반 횡단보도와 스마트 횡단보도의 안전-교통 트레이드오프 비교
- 결과 보고서 4종 생성

중요한 용어:

- 여기서 산출하는 PET 계열 지표는 엄밀한 trajectory 기반 PET가 아니라 SUMO TraCI 이벤트를 활용한 `PET proxy` 또는 `surrogate PET`이다.
- 보고서에는 반드시 “근사 지표” 또는 “surrogate”라고 명시한다.

## 입력 데이터

### T2_crosswalk_features.csv

횡단보도 674개 행을 가진 메인 입력 파일이다.

| 컬럼 | 설명 | 처리 |
|---|---|---|
| `횡단보도ID` | 고유 ID | 후보 식별자 |
| `lon`, `lat` | WGS84 좌표 | OSM 네트워크 중심좌표 |
| `읍면동명`, `행정동` | 행정구역 | 보고서 그룹화 |
| `LANES` | 차선수 | NaN이면 2.0 |
| `ROAD_RANK` | 도로등급 | 보조 컬럼 |
| `MAX_SPD` | 제한속도 km/h | NaN이면 50.0 |
| `사고건수` | 과거 사고 건수 | 위험점수 |
| `추정AADT` | 추정 일평균교통량 | 차량 수요 |
| `노인비율` | 행정동 65세 이상 비율 | 위험점수, 보행자 타입 비율 |

### T1_accident_crosswalk.csv

사고-횡단보도 매칭 결과 296건이다.

| 컬럼 | 설명 |
|---|---|
| `사고ID` | 사고 고유 ID |
| `횡단보도ID` | 매칭된 횡단보도 |
| `매칭거리` | 사고-횡단보도 간 거리(m) |

## 실행 시간 제약

총 실행 시간은 4시간 이내를 목표로 한다.

기본 설계:

- 후보 횡단보도: 20개
- 시나리오: 2개, `baseline`과 `smart`
- seed 반복: 3회, `42`, `43`, `44`
- 시뮬레이션 시간: 1800초
- 워밍업: 300초
- 총 실행 수: 20개 횡단보도 × 2개 시나리오 × 3개 seed = 120회

## 최종 파일 구조

```text
smart_crosswalk_sumo/
├── data/
│   ├── T1_accident_crosswalk.csv
│   └── T2_crosswalk_features.csv
├── sumo_nets/
│   └── cw_{ID}/
│       ├── map.osm
│       ├── network.net.xml
│       ├── routes_seed{N}.rou.xml
│       ├── peds_seed{N}.rou.xml
│       ├── baseline_seed{N}.sumocfg
│       └── smart_seed{N}.sumocfg
├── outputs/
│   ├── candidates.csv
│   ├── simulation_results_seed.csv
│   ├── simulation_results.csv
│   ├── failed_cases.csv
│   ├── report_1_simulation_results.csv
│   ├── report_2_comparison.md
│   ├── report_3_tradeoff.md
│   └── report_4_methodology.md
├── figures/
│   ├── tradeoff_scatter.png
│   ├── pet_comparison_bar.png
│   └── crosswalk_map.html
├── preprocess.py
├── build_networks.py
├── generate_demand.py
├── run_simulations.py
├── collect_metrics.py
├── generate_reports.py
└── main.py
```

## 파이프라인

```text
Step 1: preprocess.py       -> 후보 20개 선정, 위험점수 산정
Step 2: build_networks.py   -> OSM 기반 SUMO 네트워크 생성
Step 3: generate_demand.py  -> 차량/보행자 수요 XML 생성
Step 4: run_simulations.py  -> TraCI 시뮬레이션 실행
Step 5: collect_metrics.py  -> PET proxy와 교통량 지표 집계
Step 6: generate_reports.py -> 보고서 4종 생성
main.py                     -> 전체 순서 실행
```

## Step 1: preprocess.py

### 데이터 전처리

주의: `nan_flag`는 결측치 대체 전에 계산한다.

```python
import numpy as np
import pandas as pd


def preprocess_inputs(t1_path, t2_path, output_dir, top_n=20):
    t1 = pd.read_csv(t1_path)
    t2 = pd.read_csv(t2_path)

    t2["nan_flag"] = t2["LANES"].isna() | t2["MAX_SPD"].isna()

    t2["LANES"] = t2["LANES"].fillna(2.0)
    t2["MAX_SPD"] = t2["MAX_SPD"].fillna(50.0)
    t2["사고건수"] = t2["사고건수"].fillna(0)
    t2["추정AADT"] = t2["추정AADT"].fillna(t2["추정AADT"].median())
    t2["노인비율"] = t2["노인비율"].fillna(t2["노인비율"].median())

    # 국내 차선폭 3.5m 가정
    t2["crossing_length_m"] = t2["LANES"] * 3.5

    # 경찰청 보행신호 산정식 형태: 진입시간 7초 + 길이 / 설계속도
    t2["ped_green_base"] = (t2["crossing_length_m"] / 1.0 + 7).clip(lower=10.0)
    t2["ped_green_elderly"] = (t2["crossing_length_m"] / 0.8 + 7).clip(lower=10.0)

    # 위험점수: 과거 사고, 노인비율, 차선수, 제한속도 반영
    t2["risk_score"] = (
        t2["사고건수"] * 0.5
        + t2["노인비율"] * 10
        + t2["LANES"] * 0.3
        + (t2["MAX_SPD"] / 50) * 0.2
    )

    candidates = t2.nlargest(top_n, "risk_score").copy()
    candidates.to_csv(f"{output_dir}/candidates.csv", index=False)
    return candidates, t1, t2
```

## Step 2: build_networks.py

각 후보 횡단보도의 `(lat, lon)`을 중심으로 반경 약 200m OSM 네트워크를 추출한다.

OSM 다운로드:

- 1차: `python3 -m sumolib.net.osmget`
- 2차 fallback: Overpass API 직접 호출

SUMO 네트워크 변환:

- `netconvert`
- `--crossings.guess`
- `--sidewalks.guess`
- `--keep-edges.by-vclass passenger pedestrian`

```python
import os
import subprocess
from pathlib import Path

import requests


def download_osm_bbox(bbox, osm_file):
    cmd = [
        "python3",
        "-m",
        "sumolib.net.osmget",
        "--bbox",
        bbox,
        "--output",
        str(osm_file),
    ]
    try:
        subprocess.run(cmd, check=True)
        return
    except subprocess.CalledProcessError:
        url = f"https://overpass-api.de/api/map?bbox={bbox}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        osm_file.write_bytes(response.content)


def build_network(cw_id, lat, lon, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bbox_margin = 0.002
    bbox = f"{lon - bbox_margin},{lat - bbox_margin},{lon + bbox_margin},{lat + bbox_margin}"

    osm_file = output_dir / "map.osm"
    net_file = output_dir / "network.net.xml"

    download_osm_bbox(bbox, osm_file)

    subprocess.run(
        [
            "netconvert",
            "--osm-files",
            str(osm_file),
            "--output-file",
            str(net_file),
            "--geometry.remove",
            "--roundabouts.guess",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess",
            "--tls.guess-signals",
            "--crossings.guess",
            "--sidewalks.guess",
            "--sidewalks.guess.max-speed",
            "13.89",
            "--no-turnarounds",
            "--keep-edges.by-vclass",
            "passenger pedestrian",
            "--verbose",
        ],
        check=True,
    )

    return net_file
```

구현 주의:

- `sumolib.net.readNet(net_file)`로 `edge.getFunction() == "crossing"`인 edge를 탐색한다.
- crossing edge가 없으면 `--sidewalks.guess` 조건을 완화하거나 해당 후보를 실패 케이스로 기록한다.
- 보행자 경로 생성을 위해 crossing 주변 pedestrian 허용 edge를 찾아야 한다.

## Step 3: generate_demand.py

### 수요 파라미터

```python
import numpy as np


def get_demand_params(row, seed):
    rng = np.random.default_rng(seed)

    aadt_noisy = max(1000, row["추정AADT"] + rng.integers(-3000, 3001))
    hourly_veh = aadt_noisy / 24 / max(row["LANES"], 1)
    peak_factor = 1.8
    veh_per_hour = hourly_veh * peak_factor

    ped_lambda = int(rng.integers(100, 601))
    ped_mean_gap = 3600 / ped_lambda

    return {
        "veh_per_hour": float(veh_per_hour),
        "ped_mean_gap_sec": float(ped_mean_gap),
        "elderly_ratio": float(row["노인비율"]),
        "ped_lambda": ped_lambda,
    }
```

### 차량 route 생성

```python
import os
import subprocess


def generate_vehicle_routes(params, net_file, output_file, sim_duration=1800, seed=42):
    period = max(0.1, 3600 / max(params["veh_per_hour"], 1))
    random_trips = os.path.join(os.environ["SUMO_HOME"], "tools", "randomTrips.py")

    subprocess.run(
        [
            "python3",
            random_trips,
            "-n",
            str(net_file),
            "-o",
            str(output_file),
            "--period",
            str(period),
            "--seed",
            str(seed),
            "--begin",
            "0",
            "--end",
            str(sim_duration),
            "--vehicle-class",
            "passenger",
            "--validate",
        ],
        check=True,
    )
```

### 보행자 demand 생성

`sidewalk_start`, `sidewalk_end` 같은 placeholder를 쓰면 안 된다. `sumolib.net.readNet(net_file)`로 실제 보행 가능 edge를 찾아 넣는다.

```python
import xml.etree.ElementTree as ET


def generate_pedestrian_demand(params, ped_route, output_file, sim_duration=1800, seed=42):
    rng = np.random.default_rng(seed + 1000)
    elderly_ratio = params["elderly_ratio"]
    mean_gap = params["ped_mean_gap_sec"]

    root = ET.Element("routes")

    ET.SubElement(
        root,
        "vType",
        {
            "id": "adult",
            "vClass": "pedestrian",
            "minGap": "0.25",
            "width": "0.5",
            "length": "0.25",
            "maxSpeed": "1.5",
            "speedDev": "0.1",
        },
    )
    ET.SubElement(
        root,
        "vType",
        {
            "id": "elderly",
            "vClass": "pedestrian",
            "minGap": "0.25",
            "width": "0.5",
            "length": "0.25",
            "maxSpeed": "1.13",
            "speedDev": "0.15",
            "color": "255,0,0",
        },
    )

    t = float(rng.exponential(mean_gap))
    ped_id = 0
    while t < sim_duration:
        is_elderly = rng.random() < elderly_ratio
        vtype = "elderly" if is_elderly else "adult"

        person = ET.SubElement(
            root,
            "person",
            {
                "id": f"ped_{ped_id}",
                "depart": f"{t:.2f}",
                "type": vtype,
            },
        )
        ET.SubElement(
            person,
            "walk",
            {
                "from": ped_route["from_edge"],
                "to": ped_route["to_edge"],
            },
        )

        t += float(rng.exponential(mean_gap))
        ped_id += 1

    ET.ElementTree(root).write(output_file, encoding="utf-8", xml_declaration=True)
    return ped_id
```

## Step 4: run_simulations.py

### 신호 파라미터

```python
SIGNAL_PARAMS = {
    "cycle_time": 120,
    "yellow_time": 4,
    "all_red_time": 3,
    "ped_entry_time": 7,
    "extension_increment": 5,
    "max_extensions": 1,
    "trigger_remaining": 10,
    "clearance_time": 2,
    "sensor_fn_rate": 0.05,
}
```

### 신호 타이밍

```python
def compute_signal_timing(row):
    ped_green = float(row["ped_green_base"])
    vehicle_green = 120 - 4 - 3 * 2 - ped_green
    vehicle_green = max(vehicle_green, 20)
    return {
        "ped_green": ped_green,
        "vehicle_green": vehicle_green,
    }
```

### PET proxy Method A: Position-based temporal gap

목표:

- 차량이 crossing conflict zone 근처를 벗어난 마지막 시각을 기록한다.
- 보행자가 crossing에 처음 진입한 시각과 가장 가까운 차량 통과 시각의 차이를 계산한다.
- 진짜 PET라고 단정하지 않고 `PET_A_proxy`로 저장한다.

핵심 조건:

- 0.1초 step length 사용
- 이벤트 간격 30초 초과는 무관한 이벤트로 제외
- 차량 통과 시간은 너무 오래된 값을 계속 누적하지 않도록 30초 window로 관리한다.

### PET proxy Method B: Clearance-based surrogate PET

목표:

- 보행 녹색에서 전적색으로 전환되는 순간에 아직 crossing 위에 남아있는 보행자를 찾는다.
- 남은 거리와 현재 속도로 횡단 완료 필요 시간을 추정한다.
- 전적색 시간 3초에서 필요 시간을 뺀 값을 `PET_B_surrogate`로 저장한다.

공식:

```text
PET_B_surrogate = all_red_time - remaining_distance / current_ped_speed
```

해석:

- `< 0`: 전적색 시간 안에 못 나감, 고위험
- `0 <= value < 1.34`: 낮은 안전 여유, 고위험
- `1.34 <= value < 2.88`: 중위험
- `>= 2.88`: 저위험

### 시뮬레이션 루프 스케치

```python
import random
from collections import deque

import numpy as np
import traci


def run_simulation(
    net_file,
    route_file,
    ped_file,
    sumocfg,
    scenario,
    signal_timing,
    cw_params,
    sim_duration=1800,
    warmup=300,
    seed=42,
):
    random.seed(seed)

    traci.start(
        [
            "sumo",
            "-c",
            str(sumocfg),
            "--seed",
            str(seed),
            "--step-length",
            "0.1",
            "--time-to-teleport",
            "300",
            "--no-warnings",
            "--no-step-log",
        ]
    )

    crossing_edge = find_crossing_edge(net_file)
    vehicle_conflict_edges = find_vehicle_conflict_edges_at_crossing(net_file, crossing_edge)
    approach_lanes = find_vehicle_lanes_at_crossing(net_file, crossing_edge)
    tl_id = find_tl_id(net_file, crossing_edge)

    PED_GREEN_PHASE = 2
    ALL_RED_PHASE = 3

    veh_exit_times = deque(maxlen=500)
    ped_entered_crossing = set()
    pet_a_records = []
    pet_b_records = []
    elderly_incomplete = 0

    veh_wait_times = []
    queue_lengths = []

    extension_count = 0
    prev_phase = None

    step_length = 0.1
    end_time = sim_duration + warmup

    while traci.simulation.getTime() < end_time and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        t = float(traci.simulation.getTime())
        collect = t > warmup

        current_phase = traci.trafficlight.getPhase(tl_id)
        next_switch = traci.trafficlight.getNextSwitch(tl_id)
        remaining = next_switch - t
        phase_changed = current_phase != prev_phase

        # Method B는 prev_phase 갱신 전에 phase 전환을 판정해야 한다.
        if collect and phase_changed and prev_phase == PED_GREEN_PHASE and current_phase == ALL_RED_PHASE:
            peds_still = traci.edge.getLastStepPersonIDs(crossing_edge)
            for ped_id in peds_still:
                try:
                    pos = traci.person.getLanePosition(ped_id)
                    spd = traci.person.getSpeed(ped_id)
                    if spd <= 0:
                        spd = 0.5
                    remaining_dist = max(0.0, cw_params["crossing_length_m"] - pos)
                    time_to_clear = remaining_dist / spd
                    surr_pet = SIGNAL_PARAMS["all_red_time"] - time_to_clear
                    pet_b_records.append(surr_pet)

                    vtype = traci.person.getTypeID(ped_id)
                    if "elderly" in vtype:
                        elderly_incomplete += 1
                except traci.TraCIException:
                    continue

        if phase_changed:
            if current_phase == PED_GREEN_PHASE:
                extension_count = 0
            prev_phase = current_phase

        if scenario == "smart" and current_phase == PED_GREEN_PHASE:
            if (
                remaining <= SIGNAL_PARAMS["trigger_remaining"]
                and extension_count < SIGNAL_PARAMS["max_extensions"]
            ):
                peds_on = traci.edge.getLastStepPersonIDs(crossing_edge)
                if peds_on and random.random() > SIGNAL_PARAMS["sensor_fn_rate"]:
                    ext = SIGNAL_PARAMS["extension_increment"]
                    traci.trafficlight.setPhaseDuration(tl_id, remaining + ext)
                    extension_count += 1

        if collect:
            for veh_id in traci.vehicle.getIDList():
                road = traci.vehicle.getRoadID(veh_id)
                if road in vehicle_conflict_edges:
                    veh_exit_times.append(t)

            peds_on_crossing = set(traci.edge.getLastStepPersonIDs(crossing_edge))
            new_entries = peds_on_crossing - ped_entered_crossing
            for ped_id in new_entries:
                recent_vehicle_times = [vt for vt in veh_exit_times if abs(t - vt) < 30]
                if recent_vehicle_times:
                    last_exit = max(vt for vt in recent_vehicle_times if vt <= t)
                    pet_a = t - last_exit
                    pet_a_records.append(pet_a)
            ped_entered_crossing |= peds_on_crossing

            for veh_id in traci.vehicle.getIDList():
                veh_wait_times.append(traci.vehicle.getAccumulatedWaitingTime(veh_id))

            for lane in approach_lanes:
                try:
                    queue_lengths.append(traci.lane.getLastStepHaltingNumber(lane))
                except traci.TraCIException:
                    continue

    traci.close()

    return aggregate_metrics(
        pet_a_records,
        pet_b_records,
        elderly_incomplete,
        veh_wait_times,
        queue_lengths,
        sim_duration,
    )
```

### 지표 집계

```python
def aggregate_metrics(pet_a, pet_b, elderly_inc, veh_waits, queues, duration):
    import numpy as np

    def pet_stats(records, label):
        arr = np.asarray(records, dtype=float)
        if arr.size == 0:
            return {
                f"{label}_count": 0,
                f"{label}_mean": np.nan,
                f"{label}_severe": 0,
                f"{label}_moderate": 0,
                f"{label}_safe": 0,
            }
        return {
            f"{label}_count": int(arr.size),
            f"{label}_mean": float(np.mean(arr)),
            f"{label}_severe": int(np.sum(arr < 1.34)),
            f"{label}_moderate": int(np.sum((arr >= 1.34) & (arr < 2.88))),
            f"{label}_safe": int(np.sum(arr >= 2.88)),
        }

    metrics = {}
    metrics.update(pet_stats(pet_a, "PET_A_proxy"))
    metrics.update(pet_stats(pet_b, "PET_B_surrogate"))

    veh_arr = np.asarray(veh_waits, dtype=float)
    queue_arr = np.asarray(queues, dtype=float)

    metrics["elderly_incomplete_cross"] = int(elderly_inc)
    metrics["veh_avg_delay_sec"] = float(np.mean(veh_arr)) if veh_arr.size else 0.0
    metrics["veh_max_delay_sec"] = float(np.max(veh_arr)) if veh_arr.size else 0.0
    metrics["queue_avg"] = float(np.mean(queue_arr)) if queue_arr.size else 0.0
    metrics["queue_max"] = int(np.max(queue_arr)) if queue_arr.size else 0
    return metrics
```

## Step 5: collect_metrics.py

seed별 결과와 평균 결과를 모두 저장한다.

```python
import numpy as np
import pandas as pd


def collect_all(candidates_df, sim_duration=1800, warmup=300, seeds=(42, 43, 44)):
    seed_rows = []
    avg_rows = []

    for _, row in candidates_df.iterrows():
        cw_id = row["횡단보도ID"]
        cw_dir = f"sumo_nets/cw_{cw_id}"
        signal_timing = compute_signal_timing(row)
        cw_params = {"crossing_length_m": row["crossing_length_m"]}

        for scenario in ["baseline", "smart"]:
            seed_metrics = []
            for seed in seeds:
                m = run_simulation(
                    net_file=f"{cw_dir}/network.net.xml",
                    route_file=f"{cw_dir}/routes_seed{seed}.rou.xml",
                    ped_file=f"{cw_dir}/peds_seed{seed}.rou.xml",
                    sumocfg=f"{cw_dir}/{scenario}_seed{seed}.sumocfg",
                    scenario=scenario,
                    signal_timing=signal_timing,
                    cw_params=cw_params,
                    sim_duration=sim_duration,
                    warmup=warmup,
                    seed=seed,
                )
                seed_row = {
                    "횡단보도ID": cw_id,
                    "seed": seed,
                    "행정동": row["행정동"],
                    "읍면동명": row["읍면동명"],
                    "시나리오": scenario,
                    "사고건수_원본": row["사고건수"],
                    "노인비율": row["노인비율"],
                    "LANES": row["LANES"],
                    "MAX_SPD": row["MAX_SPD"],
                    "crossing_length_m": row["crossing_length_m"],
                    "ped_green_base_sec": signal_timing["ped_green"],
                    "risk_score": row["risk_score"],
                    **m,
                }
                seed_rows.append(seed_row)
                seed_metrics.append(m)

            metric_keys = sorted({key for metric in seed_metrics for key in metric})
            avg = {
                key: float(np.nanmean([metric.get(key, np.nan) for metric in seed_metrics]))
                for key in metric_keys
            }
            avg_rows.append(
                {
                    "횡단보도ID": cw_id,
                    "행정동": row["행정동"],
                    "읍면동명": row["읍면동명"],
                    "시나리오": scenario,
                    "사고건수_원본": row["사고건수"],
                    "노인비율": row["노인비율"],
                    "LANES": row["LANES"],
                    "MAX_SPD": row["MAX_SPD"],
                    "crossing_length_m": row["crossing_length_m"],
                    "ped_green_base_sec": signal_timing["ped_green"],
                    "risk_score": row["risk_score"],
                    **avg,
                }
            )

    seed_df = pd.DataFrame(seed_rows)
    avg_df = pd.DataFrame(avg_rows)
    seed_df.to_csv("outputs/simulation_results_seed.csv", index=False)
    avg_df.to_csv("outputs/simulation_results.csv", index=False)
    return seed_df, avg_df
```

## Step 6: generate_reports.py

### 보고서 1: report_1_simulation_results.csv

`simulation_results.csv`를 바탕으로 발표용 컬럼명으로 정리한다.

권장 컬럼:

```text
횡단보도ID
위치
시나리오
PET_A_proxy_severe
PET_B_surrogate_severe
고령자미완료횡단
차량평균지체(초)
차량최대지체(초)
평균대기행렬(대)
최대대기행렬(대)
PET_A_proxy_mean
PET_B_surrogate_mean
```

### 보고서 2: report_2_comparison.md

```markdown
# 일반 횡단보도 vs 스마트 횡단보도 시뮬레이션 비교 보고서

## 1. 전체 요약
- 분석 대상: 서울 중구 위험도 상위 20개 횡단보도
- 시뮬레이션: 1800초 + 워밍업 300초
- 반복 실행: seed 42, 43, 44

## 2. 횡단보도별 결과
| 횡단보도ID | 위치 | PET_B 고위험 baseline | PET_B 고위험 smart | 변화율 | 차량지체 증가(초) |

## 3. 주요 발견
- 스마트 도입 시 전체 평균 PET_B 고위험 상충 변화
- 고령자 보행 미완료 횡단 변화
- 차량 평균 지체 변화

## 4. 노인비율 높은 횡단보도 집중 분석
- 노인비율 상위 5개소 별도 분석
```

### 보고서 3: report_3_tradeoff.md

```markdown
# 노인 보행 안전 vs 차량 지체 트레이드오프 분석

## 1. 지표 정의
- 안전 효과: PET_B 고위험 감소율, 고령자 미완료횡단 감소율
- 비용: 차량 평균 지체 증가량, 최대 대기행렬 증가량

## 2. 횡단보도별 트레이드오프 산점도
- x축: 차량지체 증가량
- y축: PET_B 고위험 감소율
- 점 크기: 노인비율

## 3. 노인비율 구간별 분석
- 저: < 0.17
- 중: 0.17 ~ 0.20
- 고: > 0.20

## 4. 교통량 수준별 분석
- AADT 기반 저/중/고 구분

## 5. 결론
- 노인 보행 안전 향상을 위해 수용 가능한 차량 지체 증가량을 정리한다.
```

### 보고서 4: report_4_methodology.md

```markdown
# 시뮬레이션 방법론 보고서

## 1. SUMO 선택 근거
- 위경도 기반 OSM 실제 도로망 활용 가능
- 보행자-차량 통합 미시 시뮬레이션 가능
- TraCI Python API로 스마트 신호 제어 구현 가능

## 2. PET proxy 정의 및 계산

### 2-1. 학술적 PET 정의
PET는 첫 번째 도로 이용자가 상충구역을 벗어난 시각과 두 번째 도로 이용자가 동일 구역에 진입한 시각의 차이다.

보행자-차량 상충에서는 보통 다음 두 variant를 생각할 수 있다.

- PET_VF = T_ped_enter - T_veh_leave
- PET_PF = T_veh_enter - T_ped_leave

### 2-2. Method A: TraCI position-based PET proxy
SUMO TraCI API로 매 0.1초마다 차량과 보행자의 crossing 주변 점유 시각을 추적해 시간 차이를 산출한다.

이 방식은 차량-보행자 trajectory pair를 정밀하게 구성한 실제 PET가 아니라, 실험 목적의 근사 temporal gap 지표다.

### 2-3. Method B: Clearance-based surrogate PET
보행 녹색에서 전적색으로 넘어가는 순간, 아직 crossing에 남아있는 보행자의 잔여 횡단 소요시간과 전적색 시간을 비교한다.

```text
surrogate_PET = 전적색 시간 - 잔여횡단거리 / 현재보행속도
```

- surrogate_PET < 0: 전적색 시간 안에 횡단 완료 불가
- 0 <= surrogate_PET < 1.34: 고위험
- 1.34 <= surrogate_PET < 2.88: 중위험
- surrogate_PET >= 2.88: 저위험

### 2-4. 한계
- 실제 충돌 영역에서 두 객체의 진입/이탈 시각을 pair 단위로 추적한 PET가 아니다.
- Method B는 실제 차량 접근 여부보다 신호 비움시간과 보행자 잔여시간에 초점을 둔 surrogate 지표다.
- 따라서 보고서에서는 PET가 아니라 PET proxy 또는 surrogate PET로 표현한다.

## 3. 스마트 횡단보도 신호 연장 로직
- 연장 단위: 5초
- 최대 연장: 1회
- 트리거: 잔여 보행 녹색 <= 10초, crossing 위 보행자 감지
- 센서 false negative: 5%
- 전적색 시간: 3초

## 4. 실험 설계
- 반복 실행: 3회, seed 42/43/44
- 시뮬레이션 시간: 1800초
- 워밍업: 300초
- 차량 수요: AADT 기반, seed별 노이즈 적용
- 보행자 수요: 지수분포, lambda 100~600명/시

## 5. 교통량 지표
| 지표 | 정의 | TraCI 함수 |
|---|---|---|
| 차량 평균 지체 | 누적 대기시간 평균 | `vehicle.getAccumulatedWaitingTime()` |
| 차량 최대 지체 | 누적 대기시간 최대 | 동일 |
| 평균 대기행렬 | 접근 차선 정지 차량 수 평균 | `lane.getLastStepHaltingNumber()` |
| 최대 대기행렬 | 접근 차선 정지 차량 수 최대 | 동일 |

## 6. 데이터 한계 및 가정
- AADT는 추정값이므로 실제 관측 교통량이 아니다.
- 횡단보도 길이는 LANES × 3.5m로 추정했다.
- 보행자 수요는 유동인구 데이터가 없어서 지수분포로 가정했다.
- OSM 보행자 인프라 자동 생성 결과는 지점별로 실패할 수 있으므로 실패 케이스를 별도 기록한다.
```

## 실행 환경

Ubuntu 기준:

```bash
sudo add-apt-repository ppa:sumo/stable
sudo apt-get update
sudo apt-get install sumo sumo-tools sumo-doc
export SUMO_HOME=/usr/share/sumo
pip install sumolib traci pandas numpy scipy matplotlib folium requests
```

macOS 환경에서는 설치 경로에 맞게 `SUMO_HOME`을 조정한다.

## main.py 실행 예시

```bash
python main.py \
  --t1 data/T1_accident_crosswalk.csv \
  --t2 data/T2_crosswalk_features.csv \
  --top_n 20 \
  --seeds 42 43 44 \
  --sim_duration 1800 \
  --warmup 300 \
  --output_dir outputs/
```

## 구현 주의사항

1. `sumolib.net.readNet()`으로 `edge.getFunction() == "crossing"`인 crossing edge를 자동 탐색한다.
2. 보행자 route는 실제 pedestrian 허용 edge를 사용한다. placeholder edge ID는 금지한다.
3. sidewalk edge가 없으면 `--sidewalks.guess` 조건을 조정하고, 그래도 실패하면 해당 횡단보도를 `failed_cases.csv`에 기록한다.
4. TraCI step length는 0.1초를 기본으로 한다. 병목이 크면 0.25초를 옵션으로 허용한다.
5. `--time-to-teleport 300`으로 무한 정체를 방지한다.
6. OSM 다운로드 실패, 보행자 인프라 미생성, TraCIException은 모두 try-except로 처리하고 실패 케이스를 기록한다.
7. 병렬 실행 시 프로세스별 TraCI 포트를 분리한다.
8. 결과는 seed별 raw 결과와 seed 평균 결과를 모두 저장한다.
9. PET 관련 용어는 반드시 `PET proxy` 또는 `surrogate PET`로 표기한다.
