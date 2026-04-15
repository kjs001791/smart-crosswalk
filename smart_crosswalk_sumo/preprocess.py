from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def preprocess_inputs(
    t1_path: str | Path,
    t2_path: str | Path,
    output_dir: str | Path,
    top_n: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t1 = pd.read_csv(t1_path)
    t2 = pd.read_csv(t2_path)

    t2["nan_flag"] = t2["LANES"].isna() | t2["MAX_SPD"].isna()
    t2["LANES"] = t2["LANES"].fillna(2.0).astype(float)
    t2["MAX_SPD"] = t2["MAX_SPD"].fillna(50.0).astype(float)
    t2["사고건수"] = t2["사고건수"].fillna(0).astype(float)
    t2["추정AADT"] = t2["추정AADT"].fillna(t2["추정AADT"].median()).astype(float)
    t2["노인비율"] = t2["노인비율"].fillna(t2["노인비율"].median()).astype(float)

    t2["crossing_length_m"] = t2["LANES"] * 3.5
    t2["ped_green_base"] = (t2["crossing_length_m"] / 1.0 + 7).clip(lower=10.0)
    t2["ped_green_elderly"] = (t2["crossing_length_m"] / 0.8 + 7).clip(lower=10.0)

    t2["risk_score"] = (
        t2["사고건수"] * 0.5
        + t2["노인비율"] * 10
        + t2["LANES"] * 0.3
        + (t2["MAX_SPD"] / 50) * 0.2
    )

    candidates = t2.nlargest(top_n, "risk_score").copy()
    candidates.to_csv(output_dir / "candidates.csv", index=False)
    t2.to_csv(output_dir / "preprocessed_crosswalks.csv", index=False)

    return candidates, t1, t2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", default="data/processed/T1_accident_crosswalk.csv")
    parser.add_argument("--t2", default="data/processed/T2_crosswalk_features.csv")
    parser.add_argument("--top_n", type=int, default=20)
    parser.add_argument("--output_dir", default="outputs")
    args = parser.parse_args()
    preprocess_inputs(args.t1, args.t2, args.output_dir, args.top_n)


if __name__ == "__main__":
    main()
