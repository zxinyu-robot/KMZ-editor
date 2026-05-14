# uavplanner

自 `drone_3d_path` 迁移的 **无人机航线 KMZ 导出与几何工具** 库：与 `calculate-area` 同构的请求体解析、`route_3d.waypoints_wgs84` 与 `options` 驱动的 KMZ 生成、KMZ 读回、坐标变换与规划结果回投等。**不包含** `path_generator` 的完整航线规划服务执行；面状/航点/圆柱/带状等几何规划与导出集中在 `uavplanner.path_editor` 中，可通过 Python API 或 CLI 使用。

## 环境要求

- **Python** ≥ 3.10（见 `pyproject.toml`）
- **运行时依赖**：`numpy`、`pyproj`、`lxml`

## 安装

在仓库根目录执行：

```bash
cd /path/to/uavplanner
python3 -m venv .venv && . .venv/bin/activate
pip install -U pip setuptools
pip install -e .
```

开发依赖（含 `pytest`）：

```bash
pip install -e ".[dev]"
```

## 命令行：`path_editor`

安装后以模块方式运行（子命令：`polygon` | `waypoint` | `corridor` | `cylinder`）。

查看**全部子命令**（不要只加 `--help`，否则会被默认补成 `polygon --help`）：

```bash
python -m uavplanner.path_editor.cli
python -m uavplanner.path_editor.cli polygon --help
```

示例（面状航线；首参可省略 `polygon`，CLI 会自动补上）：

```bash
python -m uavplanner.path_editor.cli polygon examples/your_polygon.geojson -o /tmp/out.kmz --spacing 15
```

输入支持 KMZ/KML/GeoJSON/JSON；可选 DSM 仿地、相机预设、任务参数（返航高度、完成动作等）。详见各子命令的 `--help`。

## 库用法

### 从包顶层导入

`uavplanner` 包对外导出（见 `uavplanner/__init__.py`）：

| 符号 | 说明 |
|------|------|
| `export_generator_route_from_route3d_to_kmz` | 由 `route_3d` + 业务类型与参数导出 KMZ |
| `extract_calculate_payload` | 解析与 waylines 对齐的请求体 |
| `lon_lat_list_from_coordinates` | 坐标列表提取 |
| `public_calculate_error_message` | 对外可读错误文案 |
| `resolve_tileset_path_from_model_id` | 按 `model_id` 解析 tileset 路径（部分题型需注入本地解析函数） |
| `project_generator_waypoints_to_llh` | 规划器米制航点 → WGS84（可选安装 `uav_planners` 以启用 tileset ENU→ECEF 分支） |
| `waypoint_wpml_attrs_from_generator_result` | 从生成结果提取航点 WPML 属性 |
| `build_wayline_info_from_kmz` | 从 KMZ 构建航带信息 |

### KMZ 导出

```python
from pathlib import Path
from uavplanner import export_generator_route_from_route3d_to_kmz

export_generator_route_from_route3d_to_kmz(
    business_route_type="polygon",
    polygon_ll=[[113.9, 22.5], [113.91, 22.5], [113.91, 22.51], [113.9, 22.51], [113.9, 22.5]],
    params={"height": 80.0},
    route_3d={"waypoints_wgs84": [[113.9, 22.5, 50.0], [113.905, 22.505, 50.0]]},
    kmz_output_path=Path("/tmp/out.kmz"),
)
```

### 请求体解析与模型路径（原 waylines 合同）

```python
from uavplanner import extract_calculate_payload, lon_lat_list_from_coordinates, resolve_tileset_path_from_model_id

route_type, coordinates, options = extract_calculate_payload(body_dict)
opts2 = resolve_tileset_path_from_model_id(
    route_type,
    options,
    resolve_model_local_path=lambda mid: "/data/tileset.json",
)
coord_list = lon_lat_list_from_coordinates(coordinates)
```

未提供 `resolve_model_local_path` 且 body 带 `model_id`：对 `polygon` / `facade` / `close_photography` 与旧行为一致（可忽略）；对 `cylinder` 会抛出 `ValueError`。

### KMZ 读回

```python
from uavplanner import build_wayline_info_from_kmz

info = build_wayline_info_from_kmz("/path/to/file.kmz")
```

### 规划器坐标回投（不含规划，仅几何）

```python
from uavplanner import project_generator_waypoints_to_llh

enu, llh = project_generator_waypoints_to_llh(
    result_dict, ref_lon, ref_lat, ref_alt, region_only_enabled=True
)
```

### 坐标辅助

```python
from uavplanner.coordinate_frames import llh_to_mission_enu, llh_to_aabb_local
from uavplanner.transform import build_ll_to_xy_funcs
```

## 源码布局

| 路径 | 说明 |
|------|------|
| `uavplanner/path_editor/` | 几何规划、I/O、KMZ 组装、CLI（`cli.py`） |
| `uavplanner/response_util.py` | `path_editor_plan_fail` 等统一失败结构（供 `path_editor/api` 使用） |
| `uavplanner/generator_mission.py` | `build_generator_mission_params` |
| `uavplanner/export_bridge.py` | `export_generator_route_from_route3d_to_kmz` |
| `uavplanner/contracts/` | `calculate_area_contract`（sanitize、嵌套过滤；`get_coverage_mission_merge_keys` 等为 MissionConfig 字段静态快照） |
| `uavplanner/kmz/` | `KMZParser` 等 |
| `uavplanner/calculate_area_payload.py` | `extract_calculate_payload` 等与 waylines 对齐 |
| `uavplanner/wayline_kmz_info.py` | `build_wayline_info_from_kmz` |
| `uavplanner/projection.py` | `project_generator_waypoints_to_llh` 等 |
| `uavplanner/coordinate_frames.py` | LLH ↔ ENU ↔ AABB |
| `uavplanner/transform.py` | `build_ll_to_xy_funcs` |

## 版本与元数据

包名与版本见根目录 `pyproject.toml`（当前 `uavplanner` 0.1.0）。
