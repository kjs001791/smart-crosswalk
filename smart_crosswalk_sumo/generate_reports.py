from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def df_to_markdown(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return "```text\n" + df.to_csv(index=False) + "```"


def mean_or_nan(series: pd.Series) -> float:
    arr = series.to_numpy(dtype=float)
    if arr.size == 0 or np.all(np.isnan(arr)):
        return float("nan")
    return float(np.nanmean(arr))


def pct_reduction(baseline: pd.Series, smart: pd.Series) -> pd.Series:
    denom = baseline.replace(0, np.nan)
    return (baseline - smart) / denom * 100


def comparison_table(avg_df: pd.DataFrame) -> pd.DataFrame:
    baseline = avg_df[avg_df["시나리오"] == "baseline"].set_index("횡단보도ID")
    smart = avg_df[avg_df["시나리오"] == "smart"].set_index("횡단보도ID")
    common = baseline.index.intersection(smart.index)
    baseline = baseline.loc[common]
    smart = smart.loc[common]

    table = pd.DataFrame(
        {
            "횡단보도ID": common,
            "행정동": baseline["행정동"].values,
            "읍면동명": baseline["읍면동명"].values,
            "노인비율": baseline.get("노인비율", pd.Series(index=common, dtype=float)).values,
            "baseline_PET_B_고위험": baseline.get("PET_B_surrogate_severe", pd.Series(index=common, dtype=float)).values,
            "smart_PET_B_고위험": smart.get("PET_B_surrogate_severe", pd.Series(index=common, dtype=float)).values,
            "PET_B_고위험_감소율_pct": pct_reduction(
                baseline.get("PET_B_surrogate_severe", pd.Series(index=common, dtype=float)),
                smart.get("PET_B_surrogate_severe", pd.Series(index=common, dtype=float)),
            ).values,
            "baseline_고령자미완료": baseline.get("elderly_incomplete_cross", pd.Series(index=common, dtype=float)).values,
            "smart_고령자미완료": smart.get("elderly_incomplete_cross", pd.Series(index=common, dtype=float)).values,
            "고령자미완료_감소율_pct": pct_reduction(
                baseline.get("elderly_incomplete_cross", pd.Series(index=common, dtype=float)),
                smart.get("elderly_incomplete_cross", pd.Series(index=common, dtype=float)),
            ).values,
            "baseline_차량평균지체_sec": baseline.get("veh_avg_delay_sec", pd.Series(index=common, dtype=float)).values,
            "smart_차량평균지체_sec": smart.get("veh_avg_delay_sec", pd.Series(index=common, dtype=float)).values,
            "차량평균지체_증가_sec": (
                smart.get("veh_avg_delay_sec", pd.Series(index=common, dtype=float))
                - baseline.get("veh_avg_delay_sec", pd.Series(index=common, dtype=float))
            ).values,
            "baseline_최대대기행렬": baseline.get("queue_max", pd.Series(index=common, dtype=float)).values,
            "smart_최대대기행렬": smart.get("queue_max", pd.Series(index=common, dtype=float)).values,
            "최대대기행렬_증가": (
                smart.get("queue_max", pd.Series(index=common, dtype=float))
                - baseline.get("queue_max", pd.Series(index=common, dtype=float))
            ).values,
        }
    )
    return table.sort_values("PET_B_고위험_감소율_pct", ascending=False, na_position="last")


def report_1(avg_df: pd.DataFrame, seed_df: pd.DataFrame | None, output_dir: Path) -> pd.DataFrame:
    report = avg_df.rename(
        columns={
            "PET_A_proxy_severe": "PET_A_proxy_고위험",
            "PET_B_surrogate_severe": "PET_B_surrogate_고위험",
            "elderly_incomplete_cross": "고령자미완료횡단",
            "veh_avg_delay_sec": "차량평균지체_초",
            "veh_max_delay_sec": "차량최대지체_초",
            "queue_avg": "평균대기행렬_대",
            "queue_max": "최대대기행렬_대",
            "PET_A_proxy_mean": "PET_A_proxy_평균",
            "PET_B_surrogate_mean": "PET_B_surrogate_평균",
        }
    ).copy()

    preferred = [
        "횡단보도ID",
        "행정동",
        "읍면동명",
        "시나리오",
        "PET_A_proxy_고위험",
        "PET_B_surrogate_고위험",
        "고령자미완료횡단",
        "차량평균지체_초",
        "차량최대지체_초",
        "평균대기행렬_대",
        "최대대기행렬_대",
        "PET_A_proxy_평균",
        "PET_B_surrogate_평균",
    ]
    cols = [col for col in preferred if col in report.columns]
    report = report[cols + [col for col in report.columns if col not in cols]]
    report.to_csv(output_dir / "report_1_simulation_results.csv", index=False)
    return report


def write_comparison_report(comp: pd.DataFrame, output_dir: Path) -> None:
    if comp.empty:
        body = "비교 가능한 baseline/smart 결과가 없습니다.\n"
    else:
        pet_reduction = mean_or_nan(comp["PET_B_고위험_감소율_pct"])
        incomplete_reduction = mean_or_nan(comp["고령자미완료_감소율_pct"])
        delay_delta = mean_or_nan(comp["차량평균지체_증가_sec"])
        top_rows = comp.head(20)[
            [
                "횡단보도ID",
                "행정동",
                "PET_B_고위험_감소율_pct",
                "고령자미완료_감소율_pct",
                "차량평균지체_증가_sec",
            ]
        ]
        body = f"""# 일반 횡단보도 vs 스마트 횡단보도 시뮬레이션 비교 보고서

## 1. 전체 요약

- 분석 대상: 서울 중구 위험도 상위 {len(comp)}개 횡단보도
- 시나리오: baseline / smart
- PET 표기: 실제 trajectory PET가 아니라 `PET_B_surrogate` 중심의 근사 지표
- 전체 평균 PET_B 고위험 감소율: {pet_reduction:.2f}%
- 전체 평균 고령자 미완료횡단 감소율: {incomplete_reduction:.2f}%
- 전체 평균 차량 지체 증가량: {delay_delta:.2f}초

## 2. 횡단보도별 결과

{df_to_markdown(top_rows)}

## 3. 주요 발견

- `PET_B_surrogate`는 보행 녹색 종료 시점의 잔여 횡단시간과 전적색 시간을 비교한 안전 여유 지표다.
- 스마트 신호의 이득은 PET_B 고위험 및 고령자 미완료 횡단 감소로 확인한다.
- 교통 비용은 차량 평균 지체 증가량과 최대 대기행렬 증가량으로 확인한다.

## 4. 노인비율 높은 횡단보도

{df_to_markdown(comp.sort_values("노인비율", ascending=False).head(5))}
"""
    (output_dir / "report_2_comparison.md").write_text(body, encoding="utf-8")


def write_tradeoff_report(comp: pd.DataFrame, output_dir: Path) -> None:
    if comp.empty:
        body = "# 노인 보행 안전 vs 차량 지체 트레이드오프 분석\n\n비교 가능한 결과가 없습니다.\n"
    else:
        body = f"""# 노인 보행 안전 vs 차량 지체 트레이드오프 분석

## 1. 지표 정의

- 안전 효과: `PET_B_surrogate` 고위험 감소율, 고령자 미완료횡단 감소율
- 비용: 차량 평균 지체 증가량, 최대 대기행렬 증가량
- PET 주의: 실제 PET가 아니라 신호 전환 시점 기반 surrogate 지표

## 2. 횡단보도별 트레이드오프

{df_to_markdown(comp[["횡단보도ID", "행정동", "PET_B_고위험_감소율_pct", "차량평균지체_증가_sec", "최대대기행렬_증가", "노인비율"]])}

## 3. 노인비율 구간별 분석

{df_to_markdown(elderly_band_summary(comp))}

## 4. 결론

스마트 횡단보도 효과는 안전 proxy 개선과 차량 지체 증가를 함께 봐야 한다. 정책 후보는 `PET_B_surrogate` 고위험 감소율이 크고 차량 지체 증가가 작거나 음수인 지점을 우선 검토한다.
"""
    (output_dir / "report_3_tradeoff.md").write_text(body, encoding="utf-8")


def elderly_band_summary(comp: pd.DataFrame) -> pd.DataFrame:
    bins = [-np.inf, 0.17, 0.20, np.inf]
    labels = ["저(<0.17)", "중(0.17~0.20)", "고(>0.20)"]
    work = comp.copy()
    work["노인비율구간"] = pd.cut(work["노인비율"], bins=bins, labels=labels)
    return (
        work.groupby("노인비율구간", observed=False)
        .agg(
            횡단보도수=("횡단보도ID", "count"),
            PET_B_고위험_감소율_평균=("PET_B_고위험_감소율_pct", "mean"),
            차량평균지체_증가_평균=("차량평균지체_증가_sec", "mean"),
            최대대기행렬_증가_평균=("최대대기행렬_증가", "mean"),
        )
        .reset_index()
    )


def write_methodology_report(output_dir: Path) -> None:
    body = """# 시뮬레이션 방법론 보고서

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
"""
    (output_dir / "report_4_methodology.md").write_text(body, encoding="utf-8")


def write_figures(comp: pd.DataFrame, candidates: pd.DataFrame | None, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    if not comp.empty:
        plt.figure(figsize=(8, 5))
        sizes = (comp["노인비율"].fillna(0.15) * 800).clip(lower=50)
        plt.scatter(comp["차량평균지체_증가_sec"], comp["PET_B_고위험_감소율_pct"], s=sizes, alpha=0.7)
        plt.axhline(0, color="gray", linewidth=1)
        plt.axvline(0, color="gray", linewidth=1)
        plt.xlabel("Vehicle delay increase (sec)")
        plt.ylabel("PET_B surrogate severe reduction (%)")
        plt.title("Safety vs Traffic Delay Tradeoff")
        plt.tight_layout()
        plt.savefig(figures_dir / "tradeoff_scatter.png", dpi=160)
        plt.close()

        plt.figure(figsize=(9, 5))
        x = np.arange(len(comp))
        plt.bar(x - 0.2, comp["baseline_PET_B_고위험"], width=0.4, label="baseline")
        plt.bar(x + 0.2, comp["smart_PET_B_고위험"], width=0.4, label="smart")
        plt.xticks(x, comp["횡단보도ID"].astype(str), rotation=90)
        plt.ylabel("PET_B surrogate severe count")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figures_dir / "pet_comparison_bar.png", dpi=160)
        plt.close()

    if candidates is not None and {"lat", "lon"}.issubset(candidates.columns):
        markers = candidates[["횡단보도ID", "lat", "lon", "risk_score"]].to_dict(orient="records")
        center_lat = float(candidates["lat"].mean())
        center_lon = float(candidates["lon"].mean())
        html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>중구 스마트 횡단보도 후보 지도</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>#map {{ height: 92vh; }} body {{ margin: 0; font-family: sans-serif; }}</style>
</head>
<body>
<div id="map"></div>
<script>
const map = L.map('map').setView([{center_lat}, {center_lon}], 14);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(map);
const markers = {json.dumps(markers, ensure_ascii=False)};
for (const item of markers) {{
  L.circleMarker([item.lat, item.lon], {{radius: 6, color: '#b30000'}})
    .bindPopup(`횡단보도ID: ${{item["횡단보도ID"]}}<br>risk_score: ${{Number(item.risk_score).toFixed(3)}}`)
    .addTo(map);
}}
</script>
</body>
</html>
"""
        (figures_dir / "crosswalk_map.html").write_text(html, encoding="utf-8")


def generate_all_reports(
    output_dir: str | Path = "outputs",
    figures_dir: str | Path = "figures",
    candidates_csv: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    output_dir = Path(output_dir)
    figures_dir = Path(figures_dir)
    avg_path = output_dir / "simulation_results.csv"
    seed_path = output_dir / "simulation_results_seed.csv"
    if not avg_path.exists():
        raise FileNotFoundError(f"{avg_path}가 없습니다. 먼저 시뮬레이션을 실행하세요.")

    avg_df = pd.read_csv(avg_path)
    seed_df = pd.read_csv(seed_path) if seed_path.exists() else None
    candidates = pd.read_csv(candidates_csv) if candidates_csv and Path(candidates_csv).exists() else None

    r1 = report_1(avg_df, seed_df, output_dir)
    comp = comparison_table(avg_df)
    comp.to_csv(output_dir / "comparison_table.csv", index=False)
    write_comparison_report(comp, output_dir)
    write_tradeoff_report(comp, output_dir)
    write_methodology_report(output_dir)
    write_figures(comp, candidates, figures_dir)
    return {"report_1": r1, "comparison": comp}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="outputs")
    parser.add_argument("--figures_dir", default="figures")
    parser.add_argument("--candidates", default="outputs/candidates.csv")
    args = parser.parse_args()
    generate_all_reports(args.output_dir, args.figures_dir, args.candidates)


if __name__ == "__main__":
    main()
