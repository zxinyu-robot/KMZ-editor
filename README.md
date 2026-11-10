# uavplanner

> 无人机航线 KMZ 导出与几何工具库，支持请求体解析、`route_3d.waypoints_wgs84`、KMZ 读回、坐标变换与规划结果回投。

## 项目状态

| 项目 | 状态 |
| --- | --- |
| 维护状态 | Active |
| 包名 | `uavplanner` 0.1.0 |
| Python | >= 3.10 |
| 运行时依赖 | `numpy`、`pyproj`、`lxml` |
| 边界 | 不包含 `path_generator` 完整航线规划服务执行 |

面状、航点、圆柱和带状几何规划与导出集中在 `uavplanner.path_editor`，可通过 Python API 或 CLI 使用。

## 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip setuptools
pip install -e .
pip install -e ".[dev]"
```

## 快速开始

查看 CLI 和子命令：

```bash
python -m uavplanner.path_editor.cli
python -m uavplanner.path_editor.cli polygon --help
```

导出面状航线：

```bash
python -m uavplanner.path_editor.cli polygon examples/your_polygon.geojson -o /tmp/out.kmz --spacing 15
```

输入支持 KMZ、KML、GeoJSON 和 JSON；可选 DSM 仿地、相机预设和任务参数。

## Python API

```python
from pathlib import Path
from uavplanner import export_generator_route_from_route3d_to_kmz

export_generator_route_from_route3d_to_kmz(
    business_route_type="polygon",
    polygon_ll=[[113.9, 22.5], [113.91, 22.5], [113.91, 22.51]],
    params={"height": 80.0},
    route_3d={"waypoints_wgs84": [[113.9, 22.5, 50.0], [113.905, 22.505, 50.0]]},
    kmz_output_path=Path("/tmp/out.kmz"),
)
```

主要导出 API：`export_generator_route_from_route3d_to_kmz`、`extract_calculate_payload`、`project_generator_waypoints_to_llh`、`build_wayline_info_from_kmz`、`resolve_tileset_path_from_model_id`。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `uavplanner/path_editor/` | 几何规划、I/O、KMZ 组装和 CLI |
| `uavplanner/export_bridge.py` | `route_3d` 到 KMZ 导出 |
| `uavplanner/contracts/` | 请求合同与字段过滤 |
| `uavplanner/kmz/` | KMZ 解析 |
| `uavplanner/projection.py` | 米制航点到 WGS84 回投 |
| `uavplanner/coordinate_frames.py` | LLH、ENU、AABB 坐标变换 |

## 边界与说明

本库负责几何数据处理和 KMZ 生成，不执行完整 `path_generator` 服务。可选安装 `uav_planners` 后启用 tileset ENU→ECEF 分支；未提供模型路径解析函数时，带 `model_id` 的 `cylinder` 请求会抛出 `ValueError`。

## 许可证

以仓库中的 LICENSE 文件为准。
