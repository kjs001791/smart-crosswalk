# data/raw/ 원본 데이터 목록

> ⚠️ 이 폴더의 파일은 절대 수정하지 마세요.
> 전처리 결과는 `data/processed/`에 저장합니다.

## 데이터 목록

| 파일명 | 출처 | 역할 | 비고 |
|--------|------|------|------|
| `taas_raw.xlsx` | TAAS 교통사고분석시스템 | 사고 원본 (07~24년) | 좌표 없음 |
| `accidents_with_coords.csv` | 위 파일 가공 | 사고 + 좌표 | lon/lat 추가 |
| `crosswalk_seoul.csv` | [서울열린데이터](https://data.seoul.go.kr/dataList/OA-21209/S/1/datasetView.do) | 횡단보도 위치 | NODE + LINK |
| `ped_signal.csv` | [공공데이터포털](https://www.data.go.kr/data/15124211/fileData.do) | 보행자 신호등 위치 | 미사용 (보강용) |
| `elderly_pop_dong.csv` | [서울열린데이터](https://data.seoul.go.kr/dataList/10730/S/2/datasetView.do) | 동별 고령인구 | UTF-8 BOM, skiprows=4 |
| `node_link/` | [공공데이터포털](https://www.data.go.kr/data/15025526/fileData.do) | 도로 특성 (SHP) | MOCT_LINK.shp 핵심 |
| `traffic_volume/` | [서울열린데이터](https://data.seoul.go.kr/dataList/OA-22819/L/1/datasetView.do) | 월별 교통량 | 2025_01~12.xlsx |

## 파일명 변경 이력

| 원본 파일명 | 변경 후 |
|------------|--------|
| 사고분석-지역별_07~24_(...).xlsx | taas_raw.xlsx |
| 1.1.좌표포함_사고데이터.csv | accidents_with_coords.csv |
| 01월 서울시 교통량 조사자료(2025).xlsx | 2025_01.xlsx |
| ... (02~12월 동일 패턴) | 2025_02~12.xlsx |

## 읽기 참고

- `elderly_pop_dong.csv`: `pd.read_csv(path, encoding='utf-8-sig', skiprows=4)`
- `node_link/MOCT_LINK.shp`: `gpd.read_file(path, encoding='cp949')` → `.to_crs('EPSG:4326')`
- `traffic_volume/*.xlsx`: sheet 0=범례, sheet 1=데이터, sheet 2=지점 좌표