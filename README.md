# data/raw/ 원본 데이터 목록

> ⚠️ 이 폴더의 파일은 **절대 수정하지 마세요.** 전처리 결과는 `data/processed/`에 저장합니다.
> 다운로드 기준일: 2025-04-XX (실제 날짜로 수정)

| 저장 파일명 | 원본 출처명 | 출처 사이트 | 다운로드 링크 | 비고 |
|------------|-----------|-----------|-------------|------|
| `taas_raw.xlsx` | TAAS 사고분석-지역별 (07~24년, 차대사람, 보행중) | TAAS GIS | [링크](https://taas.koroad.or.kr/gis/mcm/mcl/initMap.do?menuId=GIS_GMP_STS_RSN) | 태훈 다운로드. 좌표 없음 |
| `accidents_with_coords.csv` | 위 파일에 좌표 추가한 가공본 | - | - | lon/lat 추가. 원본은 taas_raw.xlsx |
| `crosswalk_seoul.csv` | 서울시 대로변 횡단보도 위치정보 | 서울열린데이터 | [링크](https://data.seoul.go.kr/dataList/OA-21209/S/1/datasetView.do) | 위경도 + 횡단보도 길이 포함 |
| `ped_signal.csv` | 전국 보행자 신호등 위치 | 공공데이터포털 | [링크](https://www.data.go.kr/data/15124211/fileData.do) | 횡단보도 위치 보완용 |
| `elderly_pop.csv` | 서울시 주민등록인구(연령별) | 서울열린데이터 | [링크](https://data.seoul.go.kr/dataList/10730/S/2/datasetView.do) | 구별 65세↑ 비율 산출용 |
| `node_link/` (폴더) | 전국표준노드링크 [2026-01-13] | 공공데이터포털 | [링크](https://www.data.go.kr/data/15025526/fileData.do) | SHP 형태. MOCT_LINK.shp가 핵심 (차선수/제한속도/도로등급) |
| `traffic_volume/` (폴더) | 서울시 지점별 일자별 교통량 (2024년) | 서울열린데이터 | [링크](https://data.seoul.go.kr/dataList/OA-22819/L/1/datasetView.do) | 월별 CSV. 140개 지점. 도로등급 캘리브레이션용 |

### traffic_volume/ 파일명 변경 이력
| 원본 파일명 | 변경 후 | 출처 |
|------------|--------|------|
| 01월 서울시 교통량 조사자료(2025).xlsx | 2025_01.xlsx | [서울열린데이터](https://data.seoul.go.kr/dataList/OA-22819/L/1/datasetView.do) |
| 02월 서울시 교통량 조사자료(2025).xlsx | 2025_02.xlsx | 〃 |
| ... | ... | 〃 |
| 12월 서울시 교통량 조사자료(2025).xlsx | 2025_12.xlsx | 〃 |

### 기타 파일명 변경 이력
| 원본 파일명 (출처 사이트 기준) | 변경 후 | 비고 |
|------------------------------|--------|------|
| 사고분석-지역별_07~24_(...).xlsx | taas_raw.xlsx | 원본 |
| 1.1.좌표포함_사고데이터.csv | accidents_with_coords.csv | 가공본 |
| (서울열린데이터 원본명 확인 필요) | crosswalk_seoul.csv | |
| (공공데이터포털 원본명 확인 필요) | ped_signal.csv | |
| (서울열린데이터 원본명 확인 필요) | elderly_pop.csv | |