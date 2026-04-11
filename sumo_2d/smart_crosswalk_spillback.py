import os
os.environ['SUMO_HOME'] = (
    '/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO'
)
os.environ['PATH'] = (
    '/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO/bin:'
    + os.environ['PATH']
)

import math
import random
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import traci
from scipy import stats

plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False


# 01. import 및 경로 상수 정의
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / 'results'
NODE_FILE = BASE_DIR / 'node.xml'
EDGE_FILE = BASE_DIR / 'edge.xml'
CONNECTION_FILE = BASE_DIR / 'connections.con.xml'
NET_FILE = BASE_DIR / 'net.xml'
TLL_FILE = BASE_DIR / 'tll.xml'
ROU_FILE = BASE_DIR / 'rou.xml'
ADD_FILE = BASE_DIR / 'add.xml'
CFG_FILE = BASE_DIR / 'simulation.sumocfg'
DET_OUTPUT_FILE = RESULTS_DIR / 'det.xml'
PARAMS_FILE = RESULTS_DIR / 'crosswalk_params.csv'
COMPARISON_FILE = RESULTS_DIR / 'scenario_comparison.csv'
RAW_FILE = RESULTS_DIR / 'raw_crosswalk_results.csv'
OVERALL_FILE = RESULTS_DIR / 'overall_results.csv'
EXTENSION_FILE = RESULTS_DIR / 'extension_events.csv'
SPILLOVER_FILE = RESULTS_DIR / 'spillover_timeseries.csv'
PET_FILE = RESULTS_DIR / 'pet_samples.csv'
EDGE_VOLUME_FILE = RESULTS_DIR / 'edge_volumes.csv'
FIGURE_FILE = RESULTS_DIR / 'simulation_results.png'

SUMO_HOME = Path(os.environ['SUMO_HOME'])
SUMO_BIN = (
    '/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO/bin'
)
NETCONVERT_BINARY = f'{SUMO_BIN}/netconvert'
SUMO_BINARY = f'{SUMO_BIN}/sumo'

SIM_DURATION = 3600
WARMUP_DURATION = 600
SEEDS = [42, 43, 44, 45, 46]
FLOW_WINDOWS = [
    ('offpeak_1', 0, 1200, 300),
    ('peak', 1200, 2400, 600),
    ('offpeak_2', 2400, 3600, 300),
]
SCENARIO_LABELS = {
    'baseline': 'S1',
    'smart_single': 'S2',
    'smart_multi': 'S3',
}
SCENARIO_SMART_TLS = {
    'baseline': [],
    'smart_single': ['N2'],
    'smart_multi': ['N2', 'N3', 'N6'],
}
ELDERLY_RISK_FACTOR = 2.5

ROUTE_DEFINITIONS = {
    'Route_A': ['N1_N2', 'N2_N3', 'N3_N4'],
    'Route_B': ['N1_N2', 'N2_N6', 'N6_N10', 'N10_N9'],
    'Route_C': ['N5_N6', 'N6_N7', 'N7_N8'],
    'Route_D': ['N4_N3', 'N3_N2', 'N2_N1'],
}
EDGE_ROUTE_WEIGHTS = Counter(
    edge_id
    for edge_list in ROUTE_DEFINITIONS.values()
    for edge_id in edge_list
)

NODE_COORDS = {
    'N1': (0.0, 300.0),
    'N2': (200.0, 300.0),
    'N3': (400.0, 300.0),
    'N4': (600.0, 300.0),
    'N5': (0.0, 150.0),
    'N6': (200.0, 150.0),
    'N7': (400.0, 150.0),
    'N8': (600.0, 150.0),
    'N9': (0.0, 0.0),
    'N10': (200.0, 0.0),
    'N11': (400.0, 0.0),
    'N12': (600.0, 0.0),
}

HORIZONTAL_LINKS = [
    ('N1', 'N2'),
    ('N2', 'N3'),
    ('N3', 'N4'),
    ('N5', 'N6'),
    ('N6', 'N7'),
    ('N7', 'N8'),
    ('N9', 'N10'),
    ('N10', 'N11'),
    ('N11', 'N12'),
]

VERTICAL_LINKS = [
    ('N1', 'N5'),
    ('N5', 'N9'),
    ('N2', 'N6'),
    ('N6', 'N10'),
    ('N3', 'N7'),
    ('N7', 'N11'),
    ('N4', 'N8'),
    ('N8', 'N12'),
]

CROSSWALK_LAYOUT = [
    {
        'cw_id': 'CW1',
        'node_id': 'N2',
        'crossing_edges': ('N2_N6', 'N6_N2'),
        'detector_in_edge': 'N6_N2',
        'detector_out_edge': 'N2_N6',
        'walk_from': 'N1_N2',
        'walk_to': 'N2_N3',
    },
    {
        'cw_id': 'CW2',
        'node_id': 'N3',
        'crossing_edges': ('N3_N7', 'N7_N3'),
        'detector_in_edge': 'N7_N3',
        'detector_out_edge': 'N3_N7',
        'walk_from': 'N2_N3',
        'walk_to': 'N3_N4',
    },
    {
        'cw_id': 'CW3',
        'node_id': 'N6',
        'crossing_edges': ('N6_N10', 'N10_N6'),
        'detector_in_edge': 'N10_N6',
        'detector_out_edge': 'N6_N10',
        'walk_from': 'N5_N6',
        'walk_to': 'N6_N7',
    },
    {
        'cw_id': 'CW4',
        'node_id': 'N7',
        'crossing_edges': ('N7_N11', 'N11_N7'),
        'detector_in_edge': 'N11_N7',
        'detector_out_edge': 'N7_N11',
        'walk_from': 'N6_N7',
        'walk_to': 'N7_N8',
    },
    {
        'cw_id': 'CW5',
        'node_id': 'N10',
        'crossing_edges': ('N6_N10', 'N10_N6'),
        'detector_in_edge': 'N6_N10',
        'detector_out_edge': 'N10_N6',
        'walk_from': 'N9_N10',
        'walk_to': 'N10_N11',
    },
    {
        'cw_id': 'CW6',
        'node_id': 'N11',
        'crossing_edges': ('N7_N11', 'N11_N7'),
        'detector_in_edge': 'N7_N11',
        'detector_out_edge': 'N11_N7',
        'walk_from': 'N10_N11',
        'walk_to': 'N11_N12',
    },
    {
        'cw_id': 'CW7',
        'node_id': 'N5',
        'crossing_edges': ('N5_N6', 'N6_N5'),
        'detector_in_edge': 'N6_N5',
        'detector_out_edge': 'N5_N6',
        'walk_from': 'N9_N5',
        'walk_to': 'N5_N1',
    },
    {
        'cw_id': 'CW8',
        'node_id': 'N8',
        'crossing_edges': ('N7_N8', 'N8_N7'),
        'detector_in_edge': 'N7_N8',
        'detector_out_edge': 'N8_N7',
        'walk_from': 'N12_N8',
        'walk_to': 'N8_N4',
    },
    {
        'cw_id': 'CW9',
        'node_id': 'N1',
        'crossing_edges': ('N1_N5', 'N5_N1'),
        'detector_in_edge': 'N5_N1',
        'detector_out_edge': 'N1_N5',
        'walk_from': 'N2_N1',
        'walk_to': 'N1_N2',
    },
    {
        'cw_id': 'CW10',
        'node_id': 'N12',
        'crossing_edges': ('N12_N8', 'N8_N12'),
        'detector_in_edge': 'N8_N12',
        'detector_out_edge': 'N12_N8',
        'walk_from': 'N11_N12',
        'walk_to': 'N12_N11',
    },
]

CW_TO_NODE = {item['cw_id']: item['node_id'] for item in CROSSWALK_LAYOUT}
TLS_TO_CW = {item['node_id']: item['cw_id'] for item in CROSSWALK_LAYOUT}


# 02. ./sumo_2d/results/ 디렉토리 생성
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def indent_xml(element, level=0):
    """XML 파일을 사람이 읽기 쉬운 형태로 정렬한다."""
    indent = '\n' + level * '  '
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + '  '
        for child in element:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indent


def safe_mean(values):
    """비어 있는 목록을 포함해 평균 계산을 안전하게 처리한다."""
    array = np.asarray(list(values), dtype=float)
    if array.size == 0 or np.all(np.isnan(array)):
        return np.nan
    return float(np.nanmean(array))


def safe_std(values):
    """비어 있는 목록을 포함해 표준편차 계산을 안전하게 처리한다."""
    array = np.asarray(list(values), dtype=float)
    if array.size == 0 or np.all(np.isnan(array)):
        return np.nan
    if array.size == 1:
        return 0.0
    return float(np.nanstd(array, ddof=1))


def scenario_name(scenario_key):
    """내부 시나리오 키를 표시용 이름으로 바꾼다."""
    return SCENARIO_LABELS[scenario_key]


def parse_person_crosswalk(person_id):
    """personFlow에서 생성된 보행자 ID로부터 횡단보도 ID를 복원한다."""
    match = re.search(r'ped_(cw\d+)_', person_id, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def confidence_interval(values):
    """평균 차이에 대한 95% 신뢰구간을 계산한다."""
    diff = np.asarray(values, dtype=float)
    diff = diff[~np.isnan(diff)]
    if diff.size == 0:
        return np.nan, np.nan
    if diff.size == 1:
        value = float(diff[0])
        return value, value
    mean_diff = float(np.mean(diff))
    sem = stats.sem(diff, nan_policy='omit')
    if np.isnan(sem):
        return mean_diff, mean_diff
    t_crit = stats.t.ppf(0.975, diff.size - 1)
    return mean_diff - t_crit * sem, mean_diff + t_crit * sem


def paired_test_stats(pre_values, post_values):
    """대응 표본 t-검정과 효과크기를 한 번에 계산한다."""
    pre = np.asarray(pre_values, dtype=float)
    post = np.asarray(post_values, dtype=float)
    mask = (~np.isnan(pre)) & (~np.isnan(post))
    pre = pre[mask]
    post = post[mask]
    if pre.size == 0:
        return np.nan, np.nan, np.nan, (np.nan, np.nan)
    diff = post - pre
    if pre.size == 1 or np.allclose(diff, diff[0]):
        t_stat = 0.0 if np.allclose(diff, 0.0) else np.nan
        p_value = 1.0 if np.allclose(diff, 0.0) else np.nan
    else:
        t_stat, p_value = stats.ttest_rel(post, pre, nan_policy='omit')
    diff_std = np.std(diff, ddof=1) if diff.size > 1 else 0.0
    effect_size = 0.0 if diff_std == 0 else float(np.mean(diff) / diff_std)
    return t_stat, p_value, effect_size, confidence_interval(diff)


def independent_test_stats(group_a, group_b):
    """독립 표본 t-검정과 효과크기, 평균 차이 신뢰구간을 계산한다."""
    sample_a = np.asarray(group_a, dtype=float)
    sample_b = np.asarray(group_b, dtype=float)
    sample_a = sample_a[~np.isnan(sample_a)]
    sample_b = sample_b[~np.isnan(sample_b)]
    if sample_a.size == 0 or sample_b.size == 0:
        return np.nan, np.nan, np.nan, (np.nan, np.nan)

    t_stat, p_value = stats.ttest_ind(
        sample_a,
        sample_b,
        equal_var=False,
        nan_policy='omit',
    )
    mean_diff = float(np.mean(sample_a) - np.mean(sample_b))

    if sample_a.size > 1 and sample_b.size > 1:
        var_a = np.var(sample_a, ddof=1)
        var_b = np.var(sample_b, ddof=1)
        pooled_sd = np.sqrt(
            ((sample_a.size - 1) * var_a + (sample_b.size - 1) * var_b)
            / (sample_a.size + sample_b.size - 2)
        )
        effect_size = 0.0 if pooled_sd == 0 else float(mean_diff / pooled_sd)
        se_diff = np.sqrt(var_a / sample_a.size + var_b / sample_b.size)
        if se_diff == 0:
            ci_low, ci_high = mean_diff, mean_diff
        else:
            numerator = (var_a / sample_a.size + var_b / sample_b.size) ** 2
            denominator = (
                ((var_a / sample_a.size) ** 2) / (sample_a.size - 1)
                + ((var_b / sample_b.size) ** 2) / (sample_b.size - 1)
            )
            dof = numerator / denominator if denominator > 0 else sample_a.size + sample_b.size - 2
            t_crit = stats.t.ppf(0.975, dof)
            ci_low = mean_diff - t_crit * se_diff
            ci_high = mean_diff + t_crit * se_diff
    else:
        effect_size = np.nan
        ci_low, ci_high = mean_diff, mean_diff
    return t_stat, p_value, effect_size, (ci_low, ci_high)


def compute_risk_score(conflicts, pedestrians, factor=1.0):
    """보행자 1인당 위험도를 계산한다."""
    if pedestrians <= 0:
        return np.nan
    return float(conflicts * factor / pedestrians)


# 03. 랜덤 파라미터 생성 함수 generate_params(seed)
def generate_params(seed):
    """횡단보도별 실험 파라미터를 난수로 생성한다."""
    np.random.seed(seed)
    records = []
    cw1_x, cw1_y = NODE_COORDS['N2']
    for item in CROSSWALK_LAYOUT:
        cycle_sec = int(np.round(np.random.uniform(90.0, 120.0)))
        ped_green_sec = int(np.round(np.random.uniform(20.0, 35.0)))
        vehicle_green_sec = int(cycle_sec - ped_green_sec - 9)
        node_x, node_y = NODE_COORDS[item['node_id']]
        records.append(
            {
                'cw_id': item['cw_id'],
                'node_id': item['node_id'],
                'node_x': node_x,
                'node_y': node_y,
                'vehicle_arrival_vph_per_lane': float(
                    np.round(np.random.uniform(200.0, 600.0), 2)
                ),
                'ped_arrival_vph': float(
                    np.round(np.random.uniform(100.0, 500.0), 2)
                ),
                'elderly_ratio': float(np.round(np.random.uniform(0.10, 0.30), 4)),
                'cycle_sec': cycle_sec,
                'ped_green_sec': ped_green_sec,
                'vehicle_green_sec': vehicle_green_sec,
                'distance_from_cw1_m': float(
                    np.round(math.dist((cw1_x, cw1_y), (node_x, node_y)), 2)
                ),
                'crossing_edge_a': item['crossing_edges'][0],
                'crossing_edge_b': item['crossing_edges'][1],
                'detector_in_edge': item['detector_in_edge'],
                'detector_out_edge': item['detector_out_edge'],
                'walk_from': item['walk_from'],
                'walk_to': item['walk_to'],
            }
        )
    return pd.DataFrame(records)


# 04. node.xml 생성 함수
def create_node_xml():
    """격자형 평면 네트워크의 노드 파일을 생성한다."""
    root = ET.Element('nodes')
    signal_nodes = {item['node_id'] for item in CROSSWALK_LAYOUT}
    for node_id, (x_coord, y_coord) in NODE_COORDS.items():
        ET.SubElement(
            root,
            'node',
            {
                'id': node_id,
                'x': f'{x_coord:.2f}',
                'y': f'{y_coord:.2f}',
                'type': 'traffic_light' if node_id in signal_nodes else 'priority',
            },
        )
    indent_xml(root)
    ET.ElementTree(root).write(NODE_FILE, encoding='utf-8', xml_declaration=True)


# 05. edge.xml 생성 함수
def create_edge_xml():
    """격자형 평면 네트워크의 양방향 링크 파일을 생성한다."""
    root = ET.Element('edges')
    for from_node, to_node in HORIZONTAL_LINKS:
        for src, dst in ((from_node, to_node), (to_node, from_node)):
            ET.SubElement(
                root,
                'edge',
                {
                    'id': f'{src}_{dst}',
                    'from': src,
                    'to': dst,
                    'numLanes': '2',
                    'speed': '13.89',
                    'priority': '3',
                    'sidewalkWidth': '2.0',
                },
            )
    for from_node, to_node in VERTICAL_LINKS:
        for src, dst in ((from_node, to_node), (to_node, from_node)):
            ET.SubElement(
                root,
                'edge',
                {
                    'id': f'{src}_{dst}',
                    'from': src,
                    'to': dst,
                    'numLanes': '1',
                    'speed': '8.33',
                    'priority': '2',
                    'sidewalkWidth': '2.0',
                },
            )
    indent_xml(root)
    ET.ElementTree(root).write(EDGE_FILE, encoding='utf-8', xml_declaration=True)


def create_connection_xml(params):
    """지정된 횡단보도를 명시적으로 생성하기 위한 연결 파일을 만든다."""
    root = ET.Element('connections')
    for row in params.itertuples():
        ET.SubElement(
            root,
            'crossing',
            {
                'node': row.node_id,
                'edges': f'{row.crossing_edge_a} {row.crossing_edge_b}',
            },
        )
    indent_xml(root)
    ET.ElementTree(root).write(
        CONNECTION_FILE, encoding='utf-8', xml_declaration=True
    )


# 06. netconvert 실행 → net.xml 빌드
def build_net():
    """plain XML을 이용해 SUMO 네트워크 파일을 생성한다."""
    subprocess.run(
        [
            NETCONVERT_BINARY,
            '--node-files',
            str(NODE_FILE),
            '--edge-files',
            str(EDGE_FILE),
            '--connection-files',
            str(CONNECTION_FILE),
            '--output-file',
            str(NET_FILE),
            '--walkingareas',
            '--default.crossing-width',
            '4.0',
            '--tls.ignore-internal-junction-jam',
            '--no-warnings',
        ],
        check=True,
        cwd=BASE_DIR,
    )


def read_network_metadata(params):
    """생성된 net.xml을 읽어 TLS, 링크, 감지기 생성에 필요한 메타데이터를 정리한다."""
    tree = ET.parse(NET_FILE)
    root = tree.getroot()

    edge_functions = {}
    edge_lanes = defaultdict(list)
    lane_meta = {}
    tls_meta = defaultdict(
        lambda: {
            'link_count': 0,
            'vehicle_links': set(),
            'ped_links': set(),
            'incoming_vehicle_lanes': set(),
            'incoming_vehicle_edges': set(),
            'crossing_edge_id': None,
        }
    )

    for edge_elem in root.findall('edge'):
        edge_id = edge_elem.attrib['id']
        edge_function = edge_elem.attrib.get('function', 'normal')
        edge_functions[edge_id] = edge_function
        for lane_elem in edge_elem.findall('lane'):
            lane_id = lane_elem.attrib['id']
            allow = lane_elem.attrib.get('allow', '')
            disallow = lane_elem.attrib.get('disallow', '')
            lane_info = {
                'lane_id': lane_id,
                'edge_id': edge_id,
                'length': float(lane_elem.attrib.get('length', '0')),
                'allow': allow,
                'disallow': disallow,
                'is_vehicle_lane': (
                    edge_function == 'normal' and 'pedestrian' not in allow.split()
                ),
            }
            lane_meta[lane_id] = lane_info
            edge_lanes[edge_id].append(lane_info)

    for connection_elem in root.findall('connection'):
        tl_id = connection_elem.attrib.get('tl')
        if tl_id not in TLS_TO_CW:
            continue
        link_index = int(connection_elem.attrib['linkIndex'])
        from_edge = connection_elem.attrib['from']
        to_edge = connection_elem.attrib['to']
        from_lane = f"{from_edge}_{connection_elem.attrib.get('fromLane', '0')}"
        tls_meta[tl_id]['link_count'] = max(tls_meta[tl_id]['link_count'], link_index + 1)
        is_ped_link = (
            edge_functions.get(from_edge, 'normal') in {'walkingarea', 'crossing'}
            or edge_functions.get(to_edge, 'normal') in {'walkingarea', 'crossing'}
            or connection_elem.attrib.get('dir') == 's'
        )
        if is_ped_link:
            tls_meta[tl_id]['ped_links'].add(link_index)
            if edge_functions.get(to_edge, 'normal') == 'crossing':
                tls_meta[tl_id]['crossing_edge_id'] = to_edge
            elif edge_functions.get(from_edge, 'normal') == 'crossing':
                tls_meta[tl_id]['crossing_edge_id'] = from_edge
        else:
            tls_meta[tl_id]['vehicle_links'].add(link_index)
            if from_lane in lane_meta and lane_meta[from_lane]['is_vehicle_lane']:
                tls_meta[tl_id]['incoming_vehicle_lanes'].add(from_lane)
                tls_meta[tl_id]['incoming_vehicle_edges'].add(from_edge)

    metadata = {}
    for row in params.itertuples():
        tl_data = tls_meta[row.node_id]
        preferred_edges = sorted(
            tl_data['incoming_vehicle_edges'],
            key=lambda edge_id: (-EDGE_ROUTE_WEIGHTS.get(edge_id, 0), edge_id),
        )
        preferred_lanes = []
        for edge_id in preferred_edges:
            edge_vehicle_lanes = [
                lane['lane_id']
                for lane in edge_lanes[edge_id]
                if lane['is_vehicle_lane']
            ]
            preferred_lanes.extend(edge_vehicle_lanes)
        if not preferred_lanes:
            raise RuntimeError(f'{row.cw_id}에 유효한 차량 감지기 차로가 없습니다.')
        detector_in_lane = preferred_lanes[0]
        detector_out_lane = preferred_lanes[1] if len(preferred_lanes) > 1 else preferred_lanes[0]
        lane_lengths = {
            lane_id: lane_meta[lane_id]['length']
            for lane_id in tl_data['incoming_vehicle_lanes']
        }
        metadata[row.cw_id] = {
            'cw_id': row.cw_id,
            'node_id': row.node_id,
            'tls_id': row.node_id,
            'link_count': tl_data['link_count'],
            'vehicle_links': sorted(tl_data['vehicle_links']),
            'ped_links': sorted(tl_data['ped_links']),
            'crossing_edge_id': tl_data['crossing_edge_id'],
            'incoming_lanes': sorted(tl_data['incoming_vehicle_lanes']),
            'incoming_edges': sorted(tl_data['incoming_vehicle_edges']),
            'lane_lengths': lane_lengths,
            'detector_in_lane': detector_in_lane,
            'detector_out_lane': detector_out_lane,
            'detector_in_length': lane_meta[detector_in_lane]['length'],
            'detector_out_length': lane_meta[detector_out_lane]['length'],
        }
    return metadata


# 07. tll.xml 생성 함수 (10개 TLS)
def create_tll_xml(params, metadata):
    """실험용 5현시 TLS 프로그램을 생성한다."""
    root = ET.Element('additional')
    for row in params.itertuples():
        cw_meta = metadata[row.cw_id]
        link_count = cw_meta['link_count']
        vehicle_links = cw_meta['vehicle_links']
        ped_links = cw_meta['ped_links']
        if link_count == 0:
            raise RuntimeError(f'{row.cw_id}({row.node_id})에 제어 링크가 없습니다.')
        if not ped_links:
            raise RuntimeError(f'{row.cw_id}({row.node_id})에 보행 링크가 없습니다.')

        vehicle_state = ['r'] * link_count
        vehicle_green_char = 'g' if len(vehicle_links) > 4 else 'G'
        for link_index in vehicle_links:
            vehicle_state[link_index] = vehicle_green_char

        yellow_state = ['r'] * link_count
        for link_index in vehicle_links:
            yellow_state[link_index] = 'y'

        all_red_state = ['r'] * link_count

        pedestrian_state = ['r'] * link_count
        for link_index in ped_links:
            pedestrian_state[link_index] = 'g'

        tl_elem = ET.SubElement(
            root,
            'tlLogic',
            {
                'id': row.node_id,
                'type': 'static',
                'programID': 'custom_static',
                'offset': '0',
            },
        )
        ET.SubElement(
            tl_elem,
            'phase',
            {'duration': str(int(row.vehicle_green_sec)), 'state': ''.join(vehicle_state)},
        )
        ET.SubElement(
            tl_elem,
            'phase',
            {'duration': '4', 'state': ''.join(yellow_state)},
        )
        ET.SubElement(
            tl_elem,
            'phase',
            {'duration': '3', 'state': ''.join(all_red_state)},
        )
        ET.SubElement(
            tl_elem,
            'phase',
            {'duration': str(int(row.ped_green_sec)), 'state': ''.join(pedestrian_state)},
        )
        ET.SubElement(
            tl_elem,
            'phase',
            {'duration': '2', 'state': ''.join(all_red_state)},
        )
    indent_xml(root)
    ET.ElementTree(root).write(TLL_FILE, encoding='utf-8', xml_declaration=True)


# 08. rou.xml 생성 함수 (vType + vehicleFlow + personFlow)
def create_rou_xml(params):
    """차량과 보행자 흐름을 포함한 경로 파일을 생성한다."""
    root = ET.Element('routes')
    ET.SubElement(
        root,
        'vType',
        {
            'id': 'passenger',
            'vClass': 'passenger',
            'maxSpeed': '13.9',
            'sigma': '0.5',
            'accel': '2.6',
            'decel': '4.5',
            'length': '5.0',
            'minGap': '2.5',
        },
    )
    ET.SubElement(
        root,
        'vType',
        {
            'id': 'normal_ped',
            'vClass': 'pedestrian',
            'maxSpeed': '1.5',
            'minGap': '0.25',
            'color': '0,0,255',
        },
    )
    ET.SubElement(
        root,
        'vType',
        {
            'id': 'elderly_ped',
            'vClass': 'pedestrian',
            'maxSpeed': '1.1',
            'minGap': '0.25',
            'sigma': '0.3',
            'color': '255,0,0',
        },
    )

    for route_id, edge_list in ROUTE_DEFINITIONS.items():
        ET.SubElement(root, 'route', {'id': route_id, 'edges': ' '.join(edge_list)})

    # 증분 로딩 환경에서 보행 흐름이 누락되지 않도록 personFlow를 먼저 기록한다.
    for row in params.itertuples():
        elderly_rate = row.ped_arrival_vph * row.elderly_ratio
        normal_rate = row.ped_arrival_vph - elderly_rate
        for flow_type, rate in (
            ('normal_ped', normal_rate),
            ('elderly_ped', elderly_rate),
        ):
            if rate <= 0:
                continue
            flow_id = (
                f"ped_{row.cw_id.lower()}_"
                f"{'normal' if flow_type == 'normal_ped' else 'elderly'}"
            )
            person_flow = ET.SubElement(
                root,
                'personFlow',
                {
                    'id': flow_id,
                    'type': flow_type,
                    'begin': '0',
                    'end': str(SIM_DURATION),
                    'period': f'{3600.0 / rate:.2f}',
                    'beginPos': '5',
                },
            )
            ET.SubElement(
                person_flow,
                'walk',
                {'from': row.walk_from, 'to': row.walk_to},
            )

    for route_id in ROUTE_DEFINITIONS:
        for suffix, begin_sec, end_sec, vehs_per_hour in FLOW_WINDOWS:
            ET.SubElement(
                root,
                'flow',
                {
                    'id': f'{route_id}_{suffix}',
                    'type': 'passenger',
                    'route': route_id,
                    'begin': str(begin_sec),
                    'end': str(end_sec),
                    'vehsPerHour': str(vehs_per_hour),
                    'departLane': 'best',
                    'departSpeed': 'max',
                },
            )
    indent_xml(root)
    ET.ElementTree(root).write(ROU_FILE, encoding='utf-8', xml_declaration=True)


# 09. add.xml 생성 함수 (e1 detector)
def create_add_xml(params, metadata):
    """횡단보도 전후 10m 지점의 유도루프 감지기를 생성한다."""
    root = ET.Element('additional')
    for row in params.itertuples():
        cw_meta = metadata[row.cw_id]
        in_pos = max(5.0, cw_meta['detector_in_length'] - 10.0)
        out_pos = max(5.0, cw_meta['detector_out_length'] - 10.0)
        ET.SubElement(
            root,
            'inductionLoop',
            {
                'id': f'det_{row.cw_id.lower()}_in',
                'lane': cw_meta['detector_in_lane'],
                'pos': f'{in_pos:.2f}',
                'freq': '1',
                'file': str(DET_OUTPUT_FILE),
            },
        )
        ET.SubElement(
            root,
            'inductionLoop',
            {
                'id': f'det_{row.cw_id.lower()}_out',
                'lane': cw_meta['detector_out_lane'],
                'pos': f'{out_pos:.2f}',
                'freq': '1',
                'file': str(DET_OUTPUT_FILE),
            },
        )
    indent_xml(root)
    ET.ElementTree(root).write(ADD_FILE, encoding='utf-8', xml_declaration=True)


# 10. sumocfg 생성 함수
def create_sumocfg():
    """실험 공통 설정을 담는 SUMO 구성 파일을 생성한다."""
    root = ET.Element('configuration')

    input_elem = ET.SubElement(root, 'input')
    ET.SubElement(input_elem, 'net-file', {'value': NET_FILE.name})
    ET.SubElement(input_elem, 'route-files', {'value': ROU_FILE.name})
    ET.SubElement(
        input_elem,
        'additional-files',
        {'value': f'{TLL_FILE.name},{ADD_FILE.name}'},
    )

    time_elem = ET.SubElement(root, 'time')
    ET.SubElement(time_elem, 'begin', {'value': '0'})
    ET.SubElement(time_elem, 'end', {'value': str(SIM_DURATION)})
    ET.SubElement(time_elem, 'step-length', {'value': '1'})

    process_elem = ET.SubElement(root, 'processing')
    ET.SubElement(process_elem, 'waiting-time-memory', {'value': '3600'})
    ET.SubElement(process_elem, 'time-to-teleport', {'value': '300'})
    ET.SubElement(process_elem, 'pedestrian.model', {'value': 'striping'})

    report_elem = ET.SubElement(root, 'report')
    ET.SubElement(report_elem, 'no-step-log', {'value': 'true'})
    ET.SubElement(report_elem, 'duration-log.disable', {'value': 'true'})

    indent_xml(root)
    ET.ElementTree(root).write(CFG_FILE, encoding='utf-8', xml_declaration=True)


# 11. PETCalculator 클래스
class PETCalculator:
    """감지기 통과 시각과 보행자 진입 시각을 이용해 PET를 근사한다."""

    def __init__(self, crosswalk_ids):
        self.crosswalk_ids = crosswalk_ids
        self.detector_buffer = defaultdict(lambda: deque(maxlen=120))
        self.pet_values = defaultdict(list)
        self.elderly_pet_values = defaultdict(list)
        self.normal_pet_values = defaultdict(list)
        self.severe_conflicts = Counter()
        self.medium_conflicts = Counter()
        self.elderly_severe_conflicts = Counter()
        self.elderly_moderate_conflicts = Counter()
        self.normal_severe_conflicts = Counter()
        self.normal_moderate_conflicts = Counter()
        self.pet_records = []

    def update_vehicle(self, det_id, time_sec):
        """감지기 통과 차량의 시각 버퍼를 갱신한다."""
        self.detector_buffer[det_id].append(float(time_sec))

    def check_pedestrian(self, cw_id, ped_type, time_sec):
        """보행자 횡단 진입 시 타입별 PET와 상충 건수를 기록한다."""
        detector_ids = [f'det_{cw_id.lower()}_in', f'det_{cw_id.lower()}_out']
        candidate_times = []
        for det_id in detector_ids:
            candidate_times.extend(self.detector_buffer[det_id])
        if not candidate_times:
            return None, None

        pet_value = min(abs(float(time_sec) - event_time) for event_time in candidate_times)
        self.pet_values[cw_id].append(float(pet_value))
        self.pet_records.append(
            {
                'cw_id': cw_id,
                'ped_type': ped_type,
                'pet_sec': float(pet_value),
            }
        )

        if ped_type == 'elderly_ped':
            self.elderly_pet_values[cw_id].append(float(pet_value))
        else:
            self.normal_pet_values[cw_id].append(float(pet_value))

        if pet_value < 1.5:
            self.severe_conflicts[cw_id] += 1
            if ped_type == 'elderly_ped':
                self.elderly_severe_conflicts[cw_id] += 1
            else:
                self.normal_severe_conflicts[cw_id] += 1
            return pet_value, 'severe'
        if pet_value < 3.0:
            self.medium_conflicts[cw_id] += 1
            if ped_type == 'elderly_ped':
                self.elderly_moderate_conflicts[cw_id] += 1
            else:
                self.normal_moderate_conflicts[cw_id] += 1
            return pet_value, 'medium'
        return pet_value, 'safe'


def is_in_crosswalk(person_id, tls_id, metadata):
    """현재 보행자가 해당 TLS의 횡단부에 있는지 판별한다."""
    cw_id = TLS_TO_CW[tls_id]
    try:
        return traci.person.getRoadID(person_id) == metadata[cw_id]['crossing_edge_id']
    except traci.TraCIException:
        return False


# 12. run_simulation(scenario, seed, params) 함수
def run_simulation(scenario, seed, params, metadata):
    """시나리오별 TraCI 제어와 성과지표 수집을 수행한다."""
    scenario_id = scenario_name(scenario)
    port = random.randint(8813, 9000)
    log_path = RESULTS_DIR / f'{scenario_id.lower()}_seed{seed}.log'
    smart_tls_list = SCENARIO_SMART_TLS[scenario]
    sumo_cmd = [
        SUMO_BINARY,
        '-c',
        str(CFG_FILE),
        '--remote-port',
        str(port),
        '--seed',
        str(seed),
        '--no-step-log',
        'true',
    ]

    extension_log = []
    spillover_log = []
    vehicle_wait_adjusted = {}
    vehicle_wait_baseline = {}
    cw_vehicle_wait = defaultdict(dict)
    cw_ped_wait = defaultdict(dict)
    cw_max_queue = Counter()
    spillback_count = Counter()
    edge_volume_counter = Counter()
    vehicle_last_edge = {}
    person_crossing_state = {}
    person_cw_map = {}
    person_type_map = {}
    pedestrian_log = {}
    active_crossing_people = defaultdict(set)
    cw_elderly_pedestrians = Counter()
    cw_normal_pedestrians = Counter()
    elderly_incomplete = Counter()
    normal_incomplete = Counter()
    last_phase = {tls_id: None for tls_id in smart_tls_list}
    extension_count = {tls_id: 0 for tls_id in smart_tls_list}
    pet_calc = PETCalculator([row.cw_id for row in params.itertuples()])
    warmup_started = False
    sumo_process = None

    def finalize_crossing(person_id, arrival_time):
        """활성 보행자의 횡단 완료와 신호 내 완료 여부를 정리한다."""
        ped_record = pedestrian_log.pop(person_id, None)
        if ped_record is None:
            return
        ped_record['arrival_time'] = float(arrival_time)
        cw_id = ped_record['cw_id']
        ped_type = ped_record['type']
        if arrival_time > ped_record['green_end_time']:
            if ped_type == 'elderly_ped':
                elderly_incomplete[cw_id] += 1
            else:
                normal_incomplete[cw_id] += 1
        active_crossing_people[ped_record['tls_id']].discard(person_id)
        person_crossing_state[person_id] = False

    try:
        with log_path.open('w', encoding='utf-8') as log_file:
            sumo_process = subprocess.Popen(
                sumo_cmd,
                cwd=BASE_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

            connected = False
            for _ in range(80):
                try:
                    traci.init(port)
                    connected = True
                    break
                except traci.exceptions.FatalTraCIError:
                    time.sleep(0.1)
            if not connected:
                raise RuntimeError(f'TraCI 연결 실패: {scenario_id}, seed={seed}')

            while traci.simulation.getTime() < SIM_DURATION:
                traci.simulationStep()
                current_time = float(traci.simulation.getTime())
                arrived_person_ids = list(
                    getattr(traci.simulation, 'getArrivedPersonIDList', lambda: [])()
                )

                if (not warmup_started) and current_time >= WARMUP_DURATION:
                    for veh_id in traci.vehicle.getIDList():
                        vehicle_wait_baseline[veh_id] = traci.vehicle.getAccumulatedWaitingTime(
                            veh_id
                        )
                    warmup_started = True

                if warmup_started:
                    for veh_id in traci.simulation.getDepartedIDList():
                        vehicle_wait_baseline.setdefault(veh_id, 0.0)

                detector_ids = [
                    f'det_{row.cw_id.lower()}_in'
                    for row in params.itertuples()
                ] + [
                    f'det_{row.cw_id.lower()}_out'
                    for row in params.itertuples()
                ]
                for det_id in detector_ids:
                    for _ in traci.inductionloop.getLastStepVehicleIDs(det_id):
                        pet_calc.update_vehicle(det_id, current_time)

                for veh_id in traci.vehicle.getIDList():
                    road_id = traci.vehicle.getRoadID(veh_id)
                    if road_id.startswith(':'):
                        continue
                    if warmup_started and vehicle_last_edge.get(veh_id) != road_id:
                        edge_volume_counter[road_id] += 1
                    vehicle_last_edge[veh_id] = road_id
                    if warmup_started:
                        baseline = vehicle_wait_baseline.setdefault(veh_id, 0.0)
                        vehicle_wait_adjusted[veh_id] = max(
                            0.0,
                            traci.vehicle.getAccumulatedWaitingTime(veh_id) - baseline,
                        )

                for person_id in traci.person.getIDList():
                    if person_id not in person_cw_map:
                        person_cw_map[person_id] = parse_person_crosswalk(person_id)
                    if person_id not in person_type_map:
                        person_type_map[person_id] = traci.person.getTypeID(person_id)

                if warmup_started:
                    for row in params.itertuples():
                        cw_id = row.cw_id
                        cw_meta = metadata[cw_id]

                        queue_total = 0
                        spill_detected = False
                        for lane_id in cw_meta['incoming_lanes']:
                            halting = traci.lane.getLastStepHaltingNumber(lane_id)
                            queue_total += halting
                            if halting * 7.5 > cw_meta['lane_lengths'][lane_id]:
                                spill_detected = True
                            for veh_id in traci.lane.getLastStepVehicleIDs(lane_id):
                                if veh_id in vehicle_wait_adjusted:
                                    cw_vehicle_wait[cw_id][veh_id] = vehicle_wait_adjusted[
                                        veh_id
                                    ]

                        if spill_detected:
                            spillback_count[cw_id] += 1
                        cw_max_queue[cw_id] = max(cw_max_queue[cw_id], queue_total)

                        edge_speeds = [
                            traci.edge.getLastStepMeanSpeed(edge_id)
                            for edge_id in cw_meta['incoming_edges']
                        ]
                        edge_occupancies = [
                            traci.edge.getLastStepOccupancy(edge_id)
                            for edge_id in cw_meta['incoming_edges']
                        ]

                        if cw_id in {'CW1', 'CW2', 'CW3'}:
                            spillover_log.append(
                                {
                                    'scenario': scenario_id,
                                    'scenario_key': scenario,
                                    'seed': seed,
                                    'time': current_time,
                                    'cw_id': cw_id,
                                    'queue': queue_total,
                                    'mean_speed': safe_mean(edge_speeds),
                                    'occupancy': safe_mean(edge_occupancies),
                                }
                            )

                    for person_id in traci.person.getIDList():
                        cw_id = person_cw_map.get(person_id)
                        if not cw_id:
                            continue
                        ped_type = person_type_map.get(person_id, 'normal_ped')
                        waiting_time = traci.person.getWaitingTime(person_id)
                        cw_ped_wait[cw_id][person_id] = max(
                            cw_ped_wait[cw_id].get(person_id, 0.0),
                            waiting_time,
                        )
                        in_crossing = (
                            traci.person.getRoadID(person_id)
                            == metadata[cw_id]['crossing_edge_id']
                        )
                        if in_crossing and not person_crossing_state.get(person_id, False):
                            tls_id = metadata[cw_id]['tls_id']
                            pedestrian_log[person_id] = {
                                'type': ped_type,
                                'enter_time': current_time,
                                'cw_id': cw_id,
                                'green_end_time': float(
                                    traci.trafficlight.getNextSwitch(tls_id)
                                ),
                                'tls_id': tls_id,
                            }
                            active_crossing_people[tls_id].add(person_id)
                            if ped_type == 'elderly_ped':
                                cw_elderly_pedestrians[cw_id] += 1
                            else:
                                cw_normal_pedestrians[cw_id] += 1
                            pet_calc.check_pedestrian(cw_id, ped_type, current_time)
                        elif (not in_crossing) and person_crossing_state.get(person_id, False):
                            finalize_crossing(person_id, current_time)
                        person_crossing_state[person_id] = in_crossing

                    for person_id in arrived_person_ids:
                        finalize_crossing(person_id, current_time)

                for tls_id in smart_tls_list:
                    phase_idx = traci.trafficlight.getPhase(tls_id)
                    if phase_idx != last_phase[tls_id]:
                        if phase_idx == 3:
                            extension_count[tls_id] = 0
                        last_phase[tls_id] = phase_idx
                    if phase_idx == 3:
                        next_switch = traci.trafficlight.getNextSwitch(tls_id)
                        remaining = next_switch - current_time
                        if remaining <= 10.0 and extension_count[tls_id] < 2:
                            active_peds = [
                                person_id
                                for person_id in traci.person.getIDList()
                                if is_in_crosswalk(person_id, tls_id, metadata)
                            ]
                            if active_peds:
                                traci.trafficlight.setPhaseDuration(
                                    tls_id, remaining + 5.0
                                )
                                new_green_end_time = current_time + remaining + 5.0
                                extension_count[tls_id] += 1
                                for person_id in list(active_crossing_people[tls_id]):
                                    if person_id in pedestrian_log:
                                        pedestrian_log[person_id]['green_end_time'] = max(
                                            pedestrian_log[person_id]['green_end_time'],
                                            new_green_end_time,
                                        )
                                extension_log.append(
                                    {
                                        'scenario': scenario_id,
                                        'scenario_key': scenario,
                                        'seed': seed,
                                        'time': current_time,
                                        'tls': tls_id,
                                        'cw_id': TLS_TO_CW[tls_id],
                                        'count': extension_count[tls_id],
                                    }
                                )

    finally:
        try:
            traci.close()
        except Exception:
            pass
        if sumo_process is not None:
            try:
                sumo_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sumo_process.kill()
                sumo_process.wait(timeout=5)

    for person_id in list(pedestrian_log):
        finalize_crossing(person_id, SIM_DURATION)

    crosswalk_rows = []
    all_ped_waits = []
    total_severe = 0
    total_medium = 0
    total_spillback = 0
    total_elderly_severe = 0
    total_normal_severe = 0
    total_elderly_incomplete = 0
    total_normal_incomplete = 0
    total_elderly_pedestrians = 0
    total_normal_pedestrians = 0

    for row in params.itertuples():
        cw_id = row.cw_id
        vehicle_wait_values = list(cw_vehicle_wait[cw_id].values())
        ped_wait_values = list(cw_ped_wait[cw_id].values())
        pet_values = pet_calc.pet_values[cw_id]
        elderly_pet_values = pet_calc.elderly_pet_values[cw_id]
        normal_pet_values = pet_calc.normal_pet_values[cw_id]
        severe_count = int(pet_calc.severe_conflicts[cw_id])
        medium_count = int(pet_calc.medium_conflicts[cw_id])
        elderly_severe_count = int(pet_calc.elderly_severe_conflicts[cw_id])
        normal_severe_count = int(pet_calc.normal_severe_conflicts[cw_id])
        elderly_moderate_count = int(pet_calc.elderly_moderate_conflicts[cw_id])
        normal_moderate_count = int(pet_calc.normal_moderate_conflicts[cw_id])
        elderly_total = int(cw_elderly_pedestrians[cw_id])
        normal_total = int(cw_normal_pedestrians[cw_id])
        total_pedestrians = elderly_total + normal_total
        elderly_incomplete_count = int(elderly_incomplete[cw_id])
        normal_incomplete_count = int(normal_incomplete[cw_id])
        elderly_risk_score = compute_risk_score(
            elderly_severe_count,
            elderly_total,
            ELDERLY_RISK_FACTOR,
        )
        normal_risk_score = compute_risk_score(normal_severe_count, normal_total, 1.0)
        total_risk_score = compute_risk_score(
            normal_severe_count + elderly_severe_count * ELDERLY_RISK_FACTOR,
            total_pedestrians,
            1.0,
        )
        total_severe += severe_count
        total_medium += medium_count
        total_spillback += int(spillback_count[cw_id])
        total_elderly_severe += elderly_severe_count
        total_normal_severe += normal_severe_count
        total_elderly_incomplete += elderly_incomplete_count
        total_normal_incomplete += normal_incomplete_count
        total_elderly_pedestrians += elderly_total
        total_normal_pedestrians += normal_total
        all_ped_waits.extend(ped_wait_values)
        crosswalk_rows.append(
            {
                'scenario': scenario_id,
                'scenario_key': scenario,
                'seed': seed,
                'cw_id': cw_id,
                'node_id': row.node_id,
                'distance_from_cw1_m': row.distance_from_cw1_m,
                'vehicle_avg_wait_sec': safe_mean(vehicle_wait_values),
                'vehicle_max_queue_veh': int(cw_max_queue[cw_id]),
                'ped_avg_wait_sec': safe_mean(ped_wait_values),
                'pet_mean_sec': safe_mean(pet_values),
                'pet_sample_count': int(len(pet_values)),
                'elderly_pet_mean_sec': safe_mean(elderly_pet_values),
                'elderly_pet_sample_count': int(len(elderly_pet_values)),
                'normal_pet_mean_sec': safe_mean(normal_pet_values),
                'normal_pet_sample_count': int(len(normal_pet_values)),
                'severe_conflicts': severe_count,
                'medium_conflicts': medium_count,
                'elderly_severe_conflicts': elderly_severe_count,
                'normal_severe_conflicts': normal_severe_count,
                'elderly_moderate_conflicts': elderly_moderate_count,
                'normal_moderate_conflicts': normal_moderate_count,
                'elderly_incomplete_crossing': elderly_incomplete_count,
                'normal_incomplete_crossing': normal_incomplete_count,
                'elderly_total_pedestrians': elderly_total,
                'normal_total_pedestrians': normal_total,
                'total_pedestrians': total_pedestrians,
                'elderly_risk_score': elderly_risk_score,
                'normal_risk_score': normal_risk_score,
                'total_risk_score': total_risk_score,
                'spillback_count': int(spillback_count[cw_id]),
            }
        )

    overall = {
        'scenario': scenario_id,
        'scenario_key': scenario,
        'seed': seed,
        'vehicle_avg_wait_sec': safe_mean(vehicle_wait_adjusted.values()),
        'vehicle_max_queue_veh': int(max(cw_max_queue.values()) if cw_max_queue else 0),
        'ped_avg_wait_sec': safe_mean(all_ped_waits),
        'pet_mean_sec': safe_mean(
            pet for values in pet_calc.pet_values.values() for pet in values
        ),
        'elderly_pet_mean_sec': safe_mean(
            pet for values in pet_calc.elderly_pet_values.values() for pet in values
        ),
        'normal_pet_mean_sec': safe_mean(
            pet for values in pet_calc.normal_pet_values.values() for pet in values
        ),
        'severe_conflicts': total_severe,
        'medium_conflicts': total_medium,
        'conflict_total': total_severe + total_medium,
        'elderly_severe_conflicts': total_elderly_severe,
        'normal_severe_conflicts': total_normal_severe,
        'elderly_incomplete_crossing': total_elderly_incomplete,
        'normal_incomplete_crossing': total_normal_incomplete,
        'elderly_total_pedestrians': total_elderly_pedestrians,
        'normal_total_pedestrians': total_normal_pedestrians,
        'total_pedestrians': total_elderly_pedestrians + total_normal_pedestrians,
        'elderly_risk_score': compute_risk_score(
            total_elderly_severe,
            total_elderly_pedestrians,
            ELDERLY_RISK_FACTOR,
        ),
        'normal_risk_score': compute_risk_score(
            total_normal_severe,
            total_normal_pedestrians,
            1.0,
        ),
        'total_risk_score': compute_risk_score(
            total_normal_severe + total_elderly_severe * ELDERLY_RISK_FACTOR,
            total_elderly_pedestrians + total_normal_pedestrians,
            1.0,
        ),
        'spillback_count': total_spillback,
    }

    return (
        {
            'scenario': scenario_id,
            'scenario_key': scenario,
            'seed': seed,
            'crosswalk_rows': crosswalk_rows,
            'overall': overall,
            'pet_values': dict(pet_calc.pet_values),
            'pet_records': list(pet_calc.pet_records),
            'edge_volumes': dict(edge_volume_counter),
        },
        extension_log,
        spillover_log,
    )


# 13. run_all_experiments() — 5회×3시나리오 반복, CRN 적용
def run_all_experiments():
    """전체 실험을 준비하고 시나리오별 반복 실행을 수행한다."""
    params = generate_params(42)
    params.to_csv(PARAMS_FILE, index=False)

    create_node_xml()
    create_edge_xml()
    create_connection_xml(params)
    build_net()
    metadata = read_network_metadata(params)
    create_tll_xml(params, metadata)
    create_rou_xml(params)
    create_add_xml(params, metadata)
    create_sumocfg()

    all_results = []
    extension_logs = []
    spillover_logs = []
    for seed in SEEDS:
        for scenario in ('baseline', 'smart_single', 'smart_multi'):
            print(
                f'[실행] scenario={scenario_name(scenario)} '
                f'(key={scenario}), seed={seed}'
            )
            result, extension_log, spillover_log = run_simulation(
                scenario, seed, params, metadata
            )
            all_results.append(result)
            extension_logs.extend(extension_log)
            spillover_logs.extend(spillover_log)
    return params, metadata, all_results, extension_logs, spillover_logs


# 14. aggregate_results() — DataFrame 집계 및 CSV 저장
def aggregate_results(params, all_results, extension_logs, spillover_logs):
    """반복 실험 결과를 DataFrame으로 집계하고 CSV로 저장한다."""
    crosswalk_rows = []
    overall_rows = []
    pet_rows = []
    edge_volume_rows = []

    for result in all_results:
        crosswalk_rows.extend(result['crosswalk_rows'])
        overall_rows.append(result['overall'])
        for pet_record in result.get('pet_records', []):
            pet_rows.append(
                {
                    'scenario': result['scenario'],
                    'scenario_key': result['scenario_key'],
                    'seed': result['seed'],
                    'cw_id': pet_record['cw_id'],
                    'ped_type': pet_record['ped_type'],
                    'pet_sec': pet_record['pet_sec'],
                }
            )
        for edge_id, volume in result['edge_volumes'].items():
            edge_volume_rows.append(
                {
                    'scenario': result['scenario'],
                    'scenario_key': result['scenario_key'],
                    'seed': result['seed'],
                    'edge_id': edge_id,
                    'volume': volume,
                }
            )

    raw_df = pd.DataFrame(crosswalk_rows)
    overall_df = pd.DataFrame(overall_rows)
    extension_df = pd.DataFrame(
        extension_logs,
        columns=['scenario', 'scenario_key', 'seed', 'time', 'tls', 'cw_id', 'count'],
    )
    spillover_df = pd.DataFrame(
        spillover_logs,
        columns=[
            'scenario',
            'scenario_key',
            'seed',
            'time',
            'cw_id',
            'queue',
            'mean_speed',
            'occupancy',
        ],
    )
    pet_df = pd.DataFrame(
        pet_rows,
        columns=['scenario', 'scenario_key', 'seed', 'cw_id', 'ped_type', 'pet_sec'],
    )
    edge_volume_df = pd.DataFrame(
        edge_volume_rows,
        columns=['scenario', 'scenario_key', 'seed', 'edge_id', 'volume'],
    )

    raw_df.to_csv(RAW_FILE, index=False)
    overall_df.to_csv(OVERALL_FILE, index=False)
    extension_df.to_csv(EXTENSION_FILE, index=False)
    spillover_df.to_csv(SPILLOVER_FILE, index=False)
    pet_df.to_csv(PET_FILE, index=False)
    edge_volume_df.to_csv(EDGE_VOLUME_FILE, index=False)

    metric_directions = {
        'vehicle_avg_wait_sec': 'lower_better',
        'vehicle_max_queue_veh': 'lower_better',
        'ped_avg_wait_sec': 'lower_better',
        'pet_mean_sec': 'higher_better',
        'elderly_pet_mean_sec': 'higher_better',
        'normal_pet_mean_sec': 'higher_better',
        'severe_conflicts': 'lower_better',
        'medium_conflicts': 'lower_better',
        'elderly_severe_conflicts': 'lower_better',
        'normal_severe_conflicts': 'lower_better',
        'elderly_incomplete_crossing': 'lower_better',
        'normal_incomplete_crossing': 'lower_better',
        'elderly_risk_score': 'lower_better',
        'normal_risk_score': 'lower_better',
        'total_risk_score': 'lower_better',
        'spillback_count': 'lower_better',
    }

    comparison_rows = []
    metric_labels = {
        'vehicle_avg_wait_sec': '차량 평균 대기시간(초/대)',
        'vehicle_max_queue_veh': '차량 최대 대기행렬(대)',
        'ped_avg_wait_sec': '보행자 평균 대기시간(초/인)',
        'pet_mean_sec': 'PET 평균(초)',
        'elderly_pet_mean_sec': '고령자 PET 평균(초)',
        'normal_pet_mean_sec': '일반 보행자 PET 평균(초)',
        'severe_conflicts': '심각 상충 건수',
        'medium_conflicts': '중간 상충 건수',
        'elderly_severe_conflicts': '고령자 심각 상충 건수',
        'normal_severe_conflicts': '일반 보행자 심각 상충 건수',
        'elderly_incomplete_crossing': '고령자 신호 내 횡단 미완료',
        'normal_incomplete_crossing': '일반 보행자 신호 내 횡단 미완료',
        'elderly_risk_score': '고령자 가중 위험도(1인당)',
        'normal_risk_score': '일반 보행자 위험도(1인당)',
        'total_risk_score': '통합 위험도(1인당)',
        'spillback_count': 'spillback 발생 횟수',
    }

    for cw_id in list(params['cw_id']) + ['ALL']:
        source_df = overall_df.copy() if cw_id == 'ALL' else raw_df[raw_df['cw_id'] == cw_id]
        for metric_name, metric_label in metric_labels.items():
            row = {
                'cw_id': cw_id,
                'metric': metric_name,
                'metric_label': metric_label,
            }
            means = {}
            for scenario_id in ('S1', 'S2', 'S3'):
                values = source_df.loc[source_df['scenario'] == scenario_id, metric_name]
                means[scenario_id] = safe_mean(values)
                row[f'{scenario_id}_mean'] = means[scenario_id]
                row[f'{scenario_id}_sd'] = safe_std(values)
                row[f'{scenario_id}_mean_sd'] = (
                    f"{row[f'{scenario_id}_mean']:.2f}±{row[f'{scenario_id}_sd']:.2f}"
                    if not np.isnan(row[f'{scenario_id}_mean'])
                    else 'NA'
                )
            baseline_mean = means['S1']
            for compare_id in ('S2', 'S3'):
                compare_mean = means[compare_id]
                if np.isnan(baseline_mean) or baseline_mean == 0 or np.isnan(compare_mean):
                    improvement = np.nan
                elif metric_directions[metric_name] == 'lower_better':
                    improvement = (baseline_mean - compare_mean) / baseline_mean * 100.0
                else:
                    improvement = (compare_mean - baseline_mean) / baseline_mean * 100.0
                row[f'{compare_id}_vs_S1_improvement_pct'] = improvement
            row['elderly_risk_reduction_rate_pct'] = (
                row['S2_vs_S1_improvement_pct']
                if metric_name == 'elderly_risk_score'
                else np.nan
            )
            row['normal_risk_reduction_rate_pct'] = (
                row['S2_vs_S1_improvement_pct']
                if metric_name == 'normal_risk_score'
                else np.nan
            )
            row['risk_reduction_rate_pct'] = (
                row['S2_vs_S1_improvement_pct']
                if metric_name == 'total_risk_score'
                else np.nan
            )
            comparison_rows.append(row)

    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(COMPARISON_FILE, index=False)

    risk_summary_rows = []
    for cw_id in params['cw_id']:
        base_row = raw_df[(raw_df['scenario'] == 'S1') & (raw_df['cw_id'] == cw_id)]
        s2_row = raw_df[(raw_df['scenario'] == 'S2') & (raw_df['cw_id'] == cw_id)]
        s3_row = raw_df[(raw_df['scenario'] == 'S3') & (raw_df['cw_id'] == cw_id)]
        elderly_base = safe_mean(base_row['elderly_risk_score'])
        elderly_s2 = safe_mean(s2_row['elderly_risk_score'])
        elderly_s3 = safe_mean(s3_row['elderly_risk_score'])
        normal_base = safe_mean(base_row['normal_risk_score'])
        normal_s2 = safe_mean(s2_row['normal_risk_score'])
        normal_s3 = safe_mean(s3_row['normal_risk_score'])
        total_base = safe_mean(base_row['total_risk_score'])
        total_s2 = safe_mean(s2_row['total_risk_score'])
        total_s3 = safe_mean(s3_row['total_risk_score'])

        def reduction_rate(base_value, compare_value):
            if np.isnan(base_value) or np.isnan(compare_value) or base_value == 0:
                return np.nan
            return float((base_value - compare_value) / base_value * 100.0)

        risk_summary_rows.append(
            {
                'cw_id': cw_id,
                'elderly_ratio': float(
                    params.loc[params['cw_id'] == cw_id, 'elderly_ratio'].iloc[0]
                ),
                'elderly_risk_reduction_s2_pct': reduction_rate(
                    elderly_base, elderly_s2
                ),
                'elderly_risk_reduction_s3_pct': reduction_rate(
                    elderly_base, elderly_s3
                ),
                'normal_risk_reduction_s2_pct': reduction_rate(
                    normal_base, normal_s2
                ),
                'normal_risk_reduction_s3_pct': reduction_rate(
                    normal_base, normal_s3
                ),
                'risk_reduction_rate_s2_pct': reduction_rate(total_base, total_s2),
                'risk_reduction_rate_s3_pct': reduction_rate(total_base, total_s3),
            }
        )
    risk_reduction_df = pd.DataFrame(risk_summary_rows)

    return {
        'params': params,
        'raw_df': raw_df,
        'overall_df': overall_df,
        'comparison_df': comparison_df,
        'extension_df': extension_df,
        'spillover_df': spillover_df,
        'pet_df': pet_df,
        'edge_volume_df': edge_volume_df,
        'risk_reduction_df': risk_reduction_df,
    }


# 15. plot_results() — 7개 subplot 시각화 및 PNG 저장
def plot_results(aggregated):
    """요구된 7개 시각화를 하나의 그림으로 저장한다."""
    raw_df = aggregated['raw_df']
    extension_df = aggregated['extension_df']
    spillover_df = aggregated['spillover_df']
    pet_df = aggregated['pet_df']
    edge_volume_df = aggregated['edge_volume_df']
    risk_reduction_df = aggregated['risk_reduction_df']
    params = aggregated['params']

    fig, axes = plt.subplots(4, 2, figsize=(24, 24))
    ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax_unused = axes.flatten()

    def nonempty_box_values(series):
        """boxplot 입력이 비어 있을 때도 그림이 깨지지 않게 한다."""
        values = np.asarray(series, dtype=float)
        values = values[~np.isnan(values)]
        return values if values.size > 0 else np.array([np.nan])

    # P1: 횡단보도별 차량 평균 대기시간 grouped bar
    pivot_wait = (
        raw_df.groupby(['cw_id', 'scenario'])['vehicle_avg_wait_sec']
        .mean()
        .unstack()
        .reindex(index=params['cw_id'].tolist())
    )
    x_positions = np.arange(len(pivot_wait.index))
    width = 0.25
    colors = {'S1': '#4c78a8', 'S2': '#f58518', 'S3': '#54a24b'}
    for index, scenario_id in enumerate(['S1', 'S2', 'S3']):
        ax1.bar(
            x_positions + (index - 1) * width,
            pivot_wait[scenario_id].values,
            width=width,
            label=scenario_id,
            color=colors[scenario_id],
        )
    ax1.set_title('P1. 횡단보도별 차량 평균 대기시간')
    ax1.set_xticks(x_positions)
    ax1.set_xticklabels(pivot_wait.index, rotation=45)
    ax1.set_ylabel('평균 대기시간 (초/대)')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)

    # P2: CW1 연장 이벤트와 CW1/CW2/CW3 대기행렬 시계열
    representative_seed = 42
    spill_seed = spillover_df[
        (spillover_df['scenario'] == 'S2') & (spillover_df['seed'] == representative_seed)
    ]
    queue_pivot = spill_seed.pivot(index='time', columns='cw_id', values='queue')
    for cw_id, color in [('CW1', '#4c78a8'), ('CW2', '#f58518'), ('CW3', '#54a24b')]:
        if cw_id in queue_pivot.columns:
            ax2.plot(
                queue_pivot.index,
                queue_pivot[cw_id],
                label=cw_id,
                color=color,
                linewidth=1.8,
            )
    representative_extensions = extension_df[
        (extension_df['scenario'] == 'S2')
        & (extension_df['seed'] == representative_seed)
        & (extension_df['cw_id'] == 'CW1')
    ]
    for event_time in representative_extensions['time'].tolist():
        ax2.axvline(event_time, color='red', linestyle='--', linewidth=0.8, alpha=0.6)
    ax2.set_title('P2. CW1 연장 이벤트와 인근 대기행렬')
    ax2.set_xlabel('시뮬레이션 시간 (초)')
    ax2.set_ylabel('대기행렬 길이 (대)')
    ax2.legend()
    ax2.grid(alpha=0.3)

    # P3: 거리 vs 대기시간 증가량 산점도
    wait_s1 = (
        raw_df[raw_df['scenario'] == 'S1']
        .groupby('cw_id')['vehicle_avg_wait_sec']
        .mean()
    )
    wait_s2 = (
        raw_df[raw_df['scenario'] == 'S2']
        .groupby('cw_id')['vehicle_avg_wait_sec']
        .mean()
    )
    delay_delta = wait_s2 - wait_s1
    distance_map = params.set_index('cw_id')['distance_from_cw1_m']
    ax3.scatter(distance_map.values, delay_delta.reindex(distance_map.index).values, c='#4c78a8')
    for cw_id in distance_map.index:
        ax3.annotate(
            cw_id,
            (
                distance_map[cw_id],
                delay_delta.reindex(distance_map.index).loc[cw_id],
            ),
            fontsize=9,
            xytext=(4, 4),
            textcoords='offset points',
        )
    ax3.axhline(0.0, color='gray', linestyle='--', linewidth=0.8)
    ax3.set_title('P3. CW1과의 거리 vs 대기시간 증가량(S2-S1)')
    ax3.set_xlabel('CW1과의 거리 (m)')
    ax3.set_ylabel('대기시간 차이 (초/대)')
    ax3.grid(alpha=0.3)

    # P4: PET 분포 box plot
    pet_samples = [
        nonempty_box_values(pet_df.loc[pet_df['scenario'] == 'S1', 'pet_sec']),
        nonempty_box_values(pet_df.loc[pet_df['scenario'] == 'S2', 'pet_sec']),
    ]
    ax4.boxplot(
        pet_samples,
        labels=['S1', 'S2'],
        patch_artist=True,
        boxprops={'facecolor': '#9ecae1'},
        medianprops={'color': 'black'},
    )
    ax4.set_title('P4. PET 분포 비교')
    ax4.set_ylabel('PET (초)')
    ax4.grid(axis='y', alpha=0.3)

    # P5: 도로망 히트맵
    graph = nx.Graph()
    for node_id, coord in NODE_COORDS.items():
        graph.add_node(node_id, pos=coord)
    for from_node, to_node in HORIZONTAL_LINKS + VERTICAL_LINKS:
        graph.add_edge(from_node, to_node)

    node_wait_map = (
        raw_df[raw_df['scenario'] == 'S2']
        .groupby('node_id')['vehicle_avg_wait_sec']
        .mean()
        .to_dict()
    )
    for node_id in graph.nodes:
        if node_id not in node_wait_map:
            neighbor_values = [
                node_wait_map[neighbor]
                for neighbor in graph.neighbors(node_id)
                if neighbor in node_wait_map
            ]
            node_wait_map[node_id] = safe_mean(neighbor_values)

    edge_volume_mean = (
        edge_volume_df[edge_volume_df['scenario'] == 'S2']
        .groupby('edge_id')['volume']
        .mean()
        .to_dict()
    )
    undirected_volume = {}
    for from_node, to_node in graph.edges:
        forward_id = f'{from_node}_{to_node}'
        backward_id = f'{to_node}_{from_node}'
        undirected_volume[(from_node, to_node)] = (
            edge_volume_mean.get(forward_id, 0.0) + edge_volume_mean.get(backward_id, 0.0)
        )
    max_volume = max(undirected_volume.values()) if undirected_volume else 1.0
    edge_widths = [
        1.0 + 5.0 * undirected_volume[(u, v)] / max_volume
        for u, v in graph.edges
    ]
    node_colors = [node_wait_map[node] for node in graph.nodes]
    positions = nx.get_node_attributes(graph, 'pos')
    nx.draw_networkx_edges(graph, positions, ax=ax5, width=edge_widths, alpha=0.45)
    nodes = nx.draw_networkx_nodes(
        graph,
        positions,
        ax=ax5,
        node_color=node_colors,
        node_size=650,
        cmap='coolwarm',
        edgecolors='white',
        linewidths=1.5,
    )
    highlighted_nodes = {CW_TO_NODE['CW1'], CW_TO_NODE['CW2'], CW_TO_NODE['CW3']}
    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=list(highlighted_nodes),
        ax=ax5,
        node_color=[node_wait_map[node] for node in highlighted_nodes],
        node_size=720,
        cmap='coolwarm',
        edgecolors='black',
        linewidths=2.5,
    )
    nx.draw_networkx_labels(graph, positions, ax=ax5, font_size=9, font_weight='bold')
    ax5.set_title('P5. 도로망 히트맵(S2 평균)')
    ax5.set_axis_off()
    colorbar = fig.colorbar(nodes, ax=ax5, fraction=0.046, pad=0.04)
    colorbar.set_label('평균 차량 대기시간 (초/대)')

    # P6: 고령자 vs 일반 보행자 PET 분포 비교
    p6_specs = [
        ('S1', 'elderly_ped', 'S1-elderly', '#d62728'),
        ('S1', 'normal_ped', 'S1-normal', '#1f77b4'),
        ('S2', 'elderly_ped', 'S2-elderly', '#ff9896'),
        ('S2', 'normal_ped', 'S2-normal', '#9ecae1'),
    ]
    p6_data = [
        nonempty_box_values(
            pet_df[
                (pet_df['scenario'] == scenario_id)
                & (pet_df['ped_type'] == ped_type)
            ]['pet_sec']
        )
        for scenario_id, ped_type, _, _ in p6_specs
    ]
    p6_box = ax6.boxplot(
        p6_data,
        labels=[label for _, _, label, _ in p6_specs],
        patch_artist=True,
        medianprops={'color': 'black'},
    )
    for patch, (_, _, _, color) in zip(p6_box['boxes'], p6_specs):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)
    ax6.axhline(1.5, color='red', linestyle='--', linewidth=1.2, label='PET 1.5초')
    ax6.set_title('P6. 고령자 vs 일반 보행자 PET 분포')
    ax6.set_ylabel('PET (초)')
    ax6.tick_params(axis='x', rotation=20)
    ax6.legend()
    ax6.grid(axis='y', alpha=0.3)

    # P7: 횡단보도별 고령자/일반 위험도 감소 효과
    risk_plot_df = risk_reduction_df.set_index('cw_id').reindex(params['cw_id'].tolist())
    x_positions = np.arange(len(risk_plot_df.index))
    bar_width = 0.36
    ax7.bar(
        x_positions - bar_width / 2,
        risk_plot_df['elderly_risk_reduction_s2_pct'].fillna(0.0).values,
        width=bar_width,
        color='#d62728',
        label='고령자',
    )
    ax7.bar(
        x_positions + bar_width / 2,
        risk_plot_df['normal_risk_reduction_s2_pct'].fillna(0.0).values,
        width=bar_width,
        color='#1f77b4',
        label='일반',
    )
    ax7.axhline(20.0, color='gray', linestyle='--', linewidth=1.0, label='20% 목표선')
    ax7.set_title('P7. 횡단보도별 위험도 감소 효과(S2-S1)')
    ax7.set_xticks(x_positions)
    ax7.set_xticklabels(risk_plot_df.index, rotation=45)
    ax7.set_ylabel('위험도 감소율 (%)')
    ax7.legend()
    ax7.grid(axis='y', alpha=0.3)

    ax_unused.axis('off')
    fig.tight_layout()
    fig.savefig(FIGURE_FILE, dpi=200, bbox_inches='tight')
    plt.close(fig)


# 16. run_statistics() — t-검정 및 콘솔 출력
def run_statistics(aggregated):
    """요구된 대응 t-검정 결과를 콘솔에 출력한다."""
    overall_df = aggregated['overall_df']
    extension_df = aggregated['extension_df']
    spillover_df = aggregated['spillover_df']
    pet_df = aggregated['pet_df']
    risk_reduction_df = aggregated['risk_reduction_df']

    metrics = [
        ('vehicle_avg_wait_sec', '차량 대기시간'),
        ('ped_avg_wait_sec', '보행자 대기시간'),
        ('conflict_total', '상충 건수'),
    ]

    for compare_scenario in ('S2', 'S3'):
        for metric_name, label in metrics:
            baseline = (
                overall_df[overall_df['scenario'] == 'S1']
                .sort_values('seed')[metric_name]
                .to_numpy(dtype=float)
            )
            compare = (
                overall_df[overall_df['scenario'] == compare_scenario]
                .sort_values('seed')[metric_name]
                .to_numpy(dtype=float)
            )
            t_stat, p_value, effect_size, ci = paired_test_stats(baseline, compare)
            conclusion = '유의함' if (not np.isnan(p_value) and p_value < 0.05) else '유의하지 않음'
            print(
                f'[{label}] S1 vs {compare_scenario}: '
                f't={t_stat:.2f}, p={p_value:.3f}, d={effect_size:.2f}, '
                f'95%CI=[{ci[0]:.2f}, {ci[1]:.2f}] -> {conclusion}'
            )

    for cw_id in ('CW2', 'CW3'):
        for metric_name, label in (
            ('queue', '대기행렬'),
            ('mean_speed', '평균속도'),
            ('occupancy', '점유율'),
        ):
            pre_seed_means = []
            post_seed_means = []
            for seed in SEEDS:
                event_times = extension_df[
                    (extension_df['scenario'] == 'S2')
                    & (extension_df['seed'] == seed)
                    & (extension_df['cw_id'] == 'CW1')
                ]['time'].tolist()
                seed_series = spillover_df[
                    (spillover_df['scenario'] == 'S2')
                    & (spillover_df['seed'] == seed)
                    & (spillover_df['cw_id'] == cw_id)
                ]
                pre_windows = []
                post_windows = []
                for event_time in event_times:
                    pre_values = seed_series[
                        (seed_series['time'] >= event_time - 120.0)
                        & (seed_series['time'] < event_time)
                    ][metric_name]
                    post_values = seed_series[
                        (seed_series['time'] > event_time)
                        & (seed_series['time'] <= event_time + 120.0)
                    ][metric_name]
                    if (not pre_values.empty) and (not post_values.empty):
                        pre_windows.append(pre_values.mean())
                        post_windows.append(post_values.mean())
                if pre_windows and post_windows:
                    pre_seed_means.append(float(np.mean(pre_windows)))
                    post_seed_means.append(float(np.mean(post_windows)))

            t_stat, p_value, effect_size, ci = paired_test_stats(
                pre_seed_means, post_seed_means
            )
            conclusion = '유의함' if (not np.isnan(p_value) and p_value < 0.05) else '유의하지 않음'
            print(
                f'[{cw_id} {label}] 연장 전후: '
                f't={t_stat:.2f}, p={p_value:.3f}, d={effect_size:.2f}, '
                f'95%CI=[{ci[0]:.2f}, {ci[1]:.2f}] -> {conclusion}'
            )

    for scenario_id in ('S1', 'S2'):
        elderly_pet = pet_df[
            (pet_df['scenario'] == scenario_id) & (pet_df['ped_type'] == 'elderly_ped')
        ]['pet_sec'].to_numpy(dtype=float)
        normal_pet = pet_df[
            (pet_df['scenario'] == scenario_id) & (pet_df['ped_type'] == 'normal_ped')
        ]['pet_sec'].to_numpy(dtype=float)
        t_stat, p_value, effect_size, ci = independent_test_stats(
            elderly_pet, normal_pet
        )
        conclusion = '유의함' if (not np.isnan(p_value) and p_value < 0.05) else '유의하지 않음'
        print(
            f'[고령자 PET] elderly vs normal ({scenario_id}): '
            f't={t_stat:.2f}, p={p_value:.3f}, d={effect_size:.2f}, '
            f'95%CI=[{ci[0]:.2f}, {ci[1]:.2f}] -> {conclusion}'
        )

    for scenario_id in ('S2', 'S3'):
        reduction_col = f'risk_reduction_rate_{scenario_id.lower()}_pct'
        corr_df = risk_reduction_df[['elderly_ratio', reduction_col]].dropna()
        if len(corr_df) < 2 or corr_df['elderly_ratio'].nunique() < 2:
            corr_coef, p_value = np.nan, np.nan
        else:
            corr_coef, p_value = stats.pearsonr(
                corr_df['elderly_ratio'],
                corr_df[reduction_col],
            )
        conclusion = '유의함' if (not np.isnan(p_value) and p_value < 0.05) else '유의하지 않음'
        print(
            f'[고령자비율 vs 위험도감소율] {scenario_id}: '
            f'r={corr_coef:.2f}, p={p_value:.3f} -> {conclusion}'
        )


# 17. main() 실행 블록
def main():
    """전체 실험 파이프라인을 순차적으로 실행한다."""
    params, metadata, all_results, extension_logs, spillover_logs = run_all_experiments()
    aggregated = aggregate_results(params, all_results, extension_logs, spillover_logs)
    plot_results(aggregated)
    run_statistics(aggregated)
    print(f'[완료] 파라미터 CSV: {PARAMS_FILE}')
    print(f'[완료] 비교 CSV: {COMPARISON_FILE}')
    print(f'[완료] 결과 그림: {FIGURE_FILE}')


if __name__ == '__main__':
    main()
