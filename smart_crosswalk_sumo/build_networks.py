from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

import pandas as pd
import requests

try:
    from .network_utils import discover_network_metadata, save_metadata, sumo_env
except ImportError:
    from network_utils import discover_network_metadata, save_metadata, sumo_env


def sumo_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    raise RuntimeError(f"{name} 실행 파일을 찾지 못했습니다. SUMO 설치와 PATH를 확인하세요.")


def download_osm_bbox(bbox: str, osm_file: Path) -> None:
    endpoints = [
        "https://overpass-api.de/api/map?bbox={bbox}",
        "https://overpass.kumi.systems/api/map?bbox={bbox}",
        "https://overpass.openstreetmap.ru/api/map?bbox={bbox}",
    ]
    last_error = None
    for attempt in range(3):
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint.format(bbox=bbox), timeout=90)
                response.raise_for_status()
                if b"<osm" not in response.content[:200]:
                    raise RuntimeError("Overpass 응답이 OSM XML이 아닙니다.")
                osm_file.write_bytes(response.content)
                return
            except Exception as exc:
                last_error = exc
        time.sleep(2 + attempt)
    raise RuntimeError(f"OSM 다운로드 실패: {last_error}")


def build_network(
    cw_id: str | int,
    lat: float,
    lon: float,
    output_dir: str | Path,
    bbox_margin: float = 0.002,
    force: bool = False,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    osm_file = output_dir / "map.osm"
    net_file = output_dir / "network.net.xml"
    metadata_file = output_dir / "metadata.json"

    if force or not osm_file.exists():
        bbox = f"{lon - bbox_margin},{lat - bbox_margin},{lon + bbox_margin},{lat + bbox_margin}"
        download_osm_bbox(bbox, osm_file)

    if force or not net_file.exists():
        with (output_dir / "netconvert.log").open("w", encoding="utf-8") as log_file:
            subprocess.run(
                [
                    sumo_tool("netconvert"),
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
                    "passenger,pedestrian",
                    "--verbose",
                ],
                check=True,
                env=sumo_env(),
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

    metadata = discover_network_metadata(net_file, lon=lon, lat=lat, cw_id=cw_id)
    save_metadata(metadata_file, metadata)
    return metadata


def build_all_networks(
    candidates_csv: str | Path,
    nets_dir: str | Path = "sumo_nets",
    output_dir: str | Path = "outputs",
    force: bool = False,
) -> pd.DataFrame:
    candidates = pd.read_csv(candidates_csv)
    nets_dir = Path(nets_dir)
    nets_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = []

    for row in candidates.itertuples(index=False):
        cw_id = getattr(row, "횡단보도ID")
        cw_dir = nets_dir / f"cw_{cw_id}"
        try:
            print(f"[net] building cw_{cw_id}", flush=True)
            build_network(cw_id, float(getattr(row, "lat")), float(getattr(row, "lon")), cw_dir, force=force)
        except Exception as exc:
            failures.append({"횡단보도ID": cw_id, "step": "build_network", "error": str(exc)})

    failure_df = pd.DataFrame(failures)
    if failures:
        failed_path = output_dir / "failed_cases.csv"
        failure_df.to_csv(
            failed_path,
            mode="a",
            header=not failed_path.exists(),
            index=False,
        )
    return failure_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="outputs/candidates.csv")
    parser.add_argument("--nets_dir", default="sumo_nets")
    parser.add_argument("--output_dir", default="outputs")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    build_all_networks(args.candidates, args.nets_dir, args.output_dir, args.force)


if __name__ == "__main__":
    main()
