# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 业务题型 → path_generator / MissionConfig 参数字典（单一实现源）
# ------------------------------------------------------------ #
import logging
import os
import time
from math import atan2, cos, radians, sin
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from uavplanner.path_editor.geometry import (
    build_ll_xy_transform,
    build_llh_enu_transform,
    normalize_angle_deg,
)
from uavplanner.path_editor.params import CAMERA_PRESETS

_logger = logging.getLogger(__name__)

def _agent_debug_log(
    *,
    run_id: str = "",
    hypothesis_id: str = "",
    location: str = "",
    message: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> None:
    _ = (run_id, hypothesis_id, location, message, data)
    return


def _normalize_data_source_type(value: Any) -> Optional[str]:
    """标准化 data_source_type 输入。"""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("auto", "pointcloud_file", "tileset"):
        return s
    return None


def _infer_data_source_type_from_path(path_value: Optional[str]) -> Optional[str]:
    """按路径后缀推断数据源类型。"""
    if not path_value:
        return None
    suffix = Path(path_value).suffix.lower()
    if suffix == ".json":
        return "tileset"
    if suffix in (".pcd", ".ply"):
        return "pointcloud_file"
    return None


def _apply_data_source_mode(
    mission: Dict[str, Any],
    *,
    region_only_enabled: bool,
    data_path: Optional[str],
    explicit_data_source_type: Optional[str],
) -> None:
    """固定 mission 三模分流字段产物。"""
    mission.pop("tileset_path", None)
    mission.pop("pointcloud_path", None)
    mission["region_only_enabled"] = bool(region_only_enabled)
    if region_only_enabled:
        mission["data_source_type"] = "auto"
        return

    if not data_path:
        mission["data_source_type"] = explicit_data_source_type or "auto"
        return

    source_type = explicit_data_source_type or _infer_data_source_type_from_path(data_path) or "auto"
    mission["data_source_type"] = source_type
    if source_type == "tileset":
        mission["tileset_path"] = data_path
        # 保留 pointcloud_path 兼容既有调用链，MissionConfig 会识别 .json。
        mission["pointcloud_path"] = data_path
    else:
        mission["pointcloud_path"] = data_path


def _finalize_takeoff_ingress_fields(mission: Dict[str, Any]) -> None:
    """将 mission 内 takeoff_ingress_pose 对象展开为 takeoff_ingress_*（供 MissionConfig 消费）。

    支持顶层 options 经合并残留，或 path_generator 嵌套写入的 pose 对象。
    """
    pose = mission.pop("takeoff_ingress_pose", None)
    if pose is None:
        pose = mission.pop("takeoffIngressPose", None)
    if not isinstance(pose, dict):
        return

    def _fget(d: Dict[str, Any], *keys: str) -> Optional[float]:
        for k in keys:
            if k not in d or d.get(k) is None:
                continue
            try:
                return float(d[k])
            except (TypeError, ValueError):
                return None
        return None

    tx = _fget(pose, "x", "X")
    ty = _fget(pose, "y", "Y")
    tz = _fget(pose, "z", "Z")
    if tx is None or ty is None or tz is None:
        return
    mission["takeoff_ingress_x"] = tx
    mission["takeoff_ingress_y"] = ty
    mission["takeoff_ingress_z"] = tz
    th = _fget(pose, "heading_deg", "headingDeg", "heading")
    if th is not None:
        mission["takeoff_ingress_heading_deg"] = th


def _pop_first_float(d: Dict[str, Any], keys: Tuple[str, ...], default: float) -> float:
    """依次弹出 keys 中第一个存在的键并转为 float；值为 None 时继续尝试下一键。

    避免 ``d.pop("height", default)`` 在键存在且值为 JSON null 时得到 None、继而 ``float(None)`` 报错。
    """
    for k in keys:
        if k not in d:
            continue
        v = d.pop(k)
        if v is not None:
            return float(v)
    return float(default)


def _pop_overlap_ratio(
    d: Dict[str, Any],
    keys: Tuple[str, ...],
    default: float,
    public_name: str,
) -> float:
    """读取重叠率并归一化到 0~1。

    - 对外合同字段固定为 ``overlap_lateral`` / ``overlap_longitudinal``。
    - 若传入 70/80 这类百分数，自动折算为 0.7/0.8。
    """
    value = _pop_first_float(d, keys, default)
    if value > 1.0 and value <= 100.0:
        value = value / 100.0
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{public_name} must be between 0 and 1")
    return float(value)


_CAMERA_FIELD_ALIASES = {
    "focal_length_mm": ("focal_length_mm", "focal_length", "focalLength", "focalLengthMm"),
    "sensor_width_mm": ("sensor_width_mm", "sensor_width", "sensorWidth", "sensorWidthMm"),
    "sensor_height_mm": ("sensor_height_mm", "sensor_height", "sensorHeight", "sensorHeightMm"),
    "resolution_x": ("resolution_x", "image_width", "imageWidth", "resolutionX"),
    "resolution_y": ("resolution_y", "image_height", "imageHeight", "resolutionY"),
}


def _camera_preset_from_model_hint(o: Dict[str, Any]) -> Optional[str]:
    """根据机型键推断默认相机预设（仅在未显式给 camera_preset 时生效）。"""
    drone_key = o.get("drone_model_key")
    if drone_key is None:
        drone_key = o.get("droneModelKey")
    if drone_key is None:
        drone_key = o.get("drone_model")
    if drone_key is None:
        return None

    if isinstance(drone_key, dict):
        try:
            enum_value = int(drone_key.get("droneEnumValue"))
            sub_enum_value = int(drone_key.get("droneSubEnumValue"))
        except (TypeError, ValueError):
            return None
    else:
        parts = [p.strip() for p in str(drone_key).split("-") if str(p).strip() != ""]
        if len(parts) < 3:
            return None
        try:
            enum_value = int(parts[-2])
            sub_enum_value = int(parts[-1])
        except (TypeError, ValueError):
            return None

    # Matrice 4T：默认按可见光广角口径做 GSD 约束推导。
    if enum_value == 99 and sub_enum_value == 1:
        return "m4t_wide"
    return None


def _camera_from_public_fields(o: Dict[str, Any]) -> Dict[str, Any]:
    """将 UI 相机字段编译为 path_generator 的 Camera 字段。"""
    camera_raw = o.pop("camera_param", None)
    if camera_raw is None:
        camera_raw = o.pop("cameraParam", None)
    if camera_raw is None:
        camera_raw = o.pop("camera", None)

    preset = o.pop("camera_preset", None)
    if preset is None:
        preset = o.pop("cameraPreset", None)
    if preset is None:
        preset = _camera_preset_from_model_hint(o)
    preset_key = str(preset or "m3e").strip().lower()
    base = CAMERA_PRESETS.get(preset_key, CAMERA_PRESETS.get("m3e", {})) or {}
    raw = camera_raw if isinstance(camera_raw, dict) else {}

    camera: Dict[str, Any] = {}
    for target_key, aliases in _CAMERA_FIELD_ALIASES.items():
        value = None
        for alias in aliases:
            if alias in raw and raw.get(alias) is not None:
                value = raw.get(alias)
                break
        if value is None:
            if target_key == "focal_length_mm":
                value = base.get("focal_length")
            elif target_key == "sensor_width_mm":
                value = base.get("sensor_width")
            elif target_key == "sensor_height_mm":
                value = base.get("sensor_height")
            elif target_key == "resolution_x":
                value = base.get("image_width")
            elif target_key == "resolution_y":
                value = base.get("image_height")
        if value is not None:
            camera[target_key] = float(value) if target_key not in {"resolution_x", "resolution_y"} else int(value)
    return camera


def _pop_gsd_m_per_px(o: Dict[str, Any]) -> Optional[float]:
    """读取 UI GSD(cm/px)，内部统一为 m/px。"""
    raw = o.pop("gsd_cm_per_px", None)
    if raw is None:
        raw = o.pop("gsdCmPerPx", None)
    if raw is None:
        return None
    value = float(raw)
    if value <= 0:
        raise ValueError("gsd_cm_per_px must be > 0")
    return value / 100.0


def _pop_standoff_distance_m(o: Dict[str, Any]) -> Optional[float]:
    """读取相对被摄面距离（m），统一映射到 MissionConfig.global_distance_m。"""
    raw = o.pop("global_distance_m", None)
    if raw is None:
        raw = o.pop("globalDistanceM", None)
    if raw is None:
        raw = o.pop("standoff_distance", None)
    if raw is None:
        raw = o.pop("standoffDistance", None)
    if raw is None:
        return None
    value = float(raw)
    if value <= 0:
        raise ValueError("global_distance_m must be > 0")
    return value


_KML_HEIGHT_KEYS = frozenset(
    {
        "height",
        "globalShootHeight",
        "ellipsoidHeight",
        "global_shoot_height",
        "executeHeight",
        "shootHeight",
        "globalFlightHeight",
    }
)


def _flight_altitude_from_kml_features(features: Any) -> Optional[float]:
    """从前端回传的 kml_json / template_kml_json 结构中深度优先提取第一个可解析的高度数值。"""
    if features is None:
        return None
    if isinstance(features, dict):
        for k, v in features.items():
            ks = str(k)
            if ks in _KML_HEIGHT_KEYS or ks.endswith("Height"):
                try:
                    if v is not None and str(v).strip() != "":
                        return float(v)
                except (TypeError, ValueError):
                    pass
            sub = _flight_altitude_from_kml_features(v)
            if sub is not None:
                return sub
    elif isinstance(features, (list, tuple)):
        for it in features:
            sub = _flight_altitude_from_kml_features(it)
            if sub is not None:
                return sub
    return None


def ref_lon_lat_from_polygon_ll(polygon_ll: List[List[float]]) -> Tuple[float, float]:
    """多边形参考经纬度（顶点质心）。闭合环首尾重复点时只计一次，避免拉偏投影原点。"""
    if not polygon_ll:
        raise ValueError("多边形坐标为空")
    pts = [
        (float(p[0]), float(p[1]))
        for p in polygon_ll
        if isinstance(p, (list, tuple)) and len(p) >= 2
    ]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if not pts:
        raise ValueError("多边形坐标为空")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _vertices_llh_with_ground(
    polygon_ll: List[List[float]],
    ground_fallback: float,
) -> Tuple[List[Tuple[float, float, float]], float]:
    """顶点 (lon,lat,h)，h 缺省用 ground_fallback；返回顶点列表与平均椭球高（作 ENU 原点 u）。"""
    raw: List[Tuple[float, float, float]] = []
    for p in polygon_ll:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        lon, lat = float(p[0]), float(p[1])
        if len(p) >= 3 and p[2] is not None:
            h = float(p[2])
        else:
            h = float(ground_fallback)
        raw.append((lon, lat, h))
    if len(raw) < 3:
        return [], float(ground_fallback)
    hs = [t[2] for t in raw]
    ref_alt = sum(hs) / len(hs)
    return raw, ref_alt


def _close_vertices_llh(
    vertices_llh: List[Tuple[float, float, float]],
) -> List[Tuple[float, float, float]]:
    """闭合 LLH 顶点环。"""
    if not vertices_llh:
        return []
    pts = [(float(lon), float(lat), float(h)) for lon, lat, h in vertices_llh]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _open_vertices_llh(
    vertices_llh: List[Tuple[float, float, float]],
) -> List[Tuple[float, float, float]]:
    """返回未闭合 3D 顶点列表。"""
    if not vertices_llh:
        return []
    pts = [(float(lon), float(lat), float(h)) for lon, lat, h in vertices_llh]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _start_lon_lat_from_polygon_ll(
    polygon_ll: List[List[float]],
    ref_lon: float,
    ref_lat: float,
) -> Tuple[float, float]:
    """取“最近起飞点”参考：优先输入首点，缺失时退回参考点。"""
    for p in polygon_ll or []:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        return float(p[0]), float(p[1])
    return float(ref_lon), float(ref_lat)


def _rotate_open_ring(points: List[Tuple[float, float, float]], start_idx: int) -> List[Tuple[float, float, float]]:
    """将未闭合 ring 旋转到指定起点索引。"""
    if not points:
        return []
    n = len(points)
    idx = int(start_idx) % n
    if idx == 0:
        return list(points)
    return list(points[idx:]) + list(points[:idx])


def _ordered_horizontal_footprint_vertices_llh(
    vertices_llh: List[Tuple[float, float, float]],
    *,
    prefer_base_level: bool,
) -> List[Tuple[float, float, float]]:
    """将 3D 顶点收敛为按水平周向排序的 footprint 顶点。

    `cylinder` 输入常见为“八个立体角点”，原始顺序可能是顶/底面交错或按拾取顺序返回。
    若直接按输入顺序连线，投影到水平面后容易形成自交几何。这里固定按：
    1. 优先选择底面点（若底面点数量足够）；
    2. 否则使用全部点的水平投影；
    3. 在局部 ENU 水平面按相对质心的极角排序；
    4. 去除重复水平点。
    """
    pts = _open_vertices_llh(vertices_llh)
    if len(pts) < 3:
        return pts

    heights = [float(h) for _lon, _lat, h in pts]
    base_height = min(heights)
    top_height = max(heights)
    prism_height = top_height - base_height
    selected = pts
    if prefer_base_level and prism_height > 1e-6:
        base_tol = max(0.1, prism_height * 1e-3)
        base_pts = [pt for pt in pts if abs(float(pt[2]) - base_height) <= base_tol]
        if len(base_pts) >= 3:
            selected = base_pts

    ref_lon = sum(lon for lon, _lat, _h in selected) / len(selected)
    ref_lat = sum(lat for _lon, lat, _h in selected) / len(selected)
    ref_alt = sum(h for _lon, _lat, h in selected) / len(selected)
    llh_to_enu, _ = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)

    annotated: List[Tuple[float, float, float, float, float, float, float]] = []
    for lon, lat, h in selected:
        e, n, _u = llh_to_enu(lon, lat, h)
        annotated.append((lon, lat, h, float(e), float(n), 0.0, 0.0))

    center_e = sum(item[3] for item in annotated) / len(annotated)
    center_n = sum(item[4] for item in annotated) / len(annotated)
    polar: List[Tuple[float, float, float, float, float, float, float]] = []
    for lon, lat, h, e, n, _ang, _r2 in annotated:
        de = e - center_e
        dn = n - center_n
        polar.append((lon, lat, h, e, n, float(atan2(dn, de)), de * de + dn * dn))

    polar.sort(key=lambda item: (item[5], item[6]))
    deduped: List[Tuple[float, float, float, float, float, float, float]] = []
    xy_tol_m = 0.05
    for item in polar:
        _lon, _lat, _h, e, n, _ang, _r2 = item
        if any((e - prev[3]) ** 2 + (n - prev[4]) ** 2 <= xy_tol_m * xy_tol_m for prev in deduped):
            continue
        deduped.append(item)

    if len(deduped) >= 3:
        return [(lon, lat, h) for lon, lat, h, _e, _n, _ang, _r2 in deduped]
    return [(lon, lat, h) for lon, lat, h, _e, _n, _ang, _r2 in polar]


def _bottom_ring_and_prism_height(
    vertices_llh: List[Tuple[float, float, float]],
    prism_height_default: float,
) -> Tuple[List[Tuple[float, float, float]], float]:
    """将 3D 顶点收敛为柱体底面 ring + prism height。"""
    if not vertices_llh:
        return [], float(prism_height_default)
    heights = [float(h) for _lon, _lat, h in vertices_llh]
    base_height = min(heights)
    top_height = max(heights)
    prism_height = top_height - base_height
    if prism_height <= 1e-6:
        prism_height = float(prism_height_default)
    footprint = _ordered_horizontal_footprint_vertices_llh(
        vertices_llh,
        prefer_base_level=True,
    )
    base_ring = [
        (float(lon), float(lat), float(base_height))
        for lon, lat, _h in (footprint or _open_vertices_llh(vertices_llh))
    ]
    return _close_vertices_llh(base_ring), float(prism_height)


def _heading_unit_xy(heading_deg: float) -> Tuple[float, float]:
    """heading(北0顺时针) -> 局部 EN 平面单位向量 (E, N)。"""
    h = radians(normalize_angle_deg(heading_deg))
    return (sin(h), cos(h))


def _facade_template_plane_from_vertices_llh(
    vertices_llh: List[Tuple[float, float, float]],
    direction_deg: float,
) -> List[Tuple[float, float, float]]:
    """按 direction 将 facade 输入点重建为竖直矩形模板面。

    输入点只用于估计水平范围与上下高程；direction 决定模板面的候选朝向。
    为兼容前端“方向角可能表示法向或沿面方向”两种口径，分别尝试
    ``normal=direction`` 与 ``normal=direction+90``，选择厚度更小的一种。
    """
    if not vertices_llh:
        return []

    pts = [(float(lon), float(lat), float(h)) for lon, lat, h in vertices_llh]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 2:
        return _close_vertices_llh(pts)

    heights = [h for _lon, _lat, h in pts]
    base_height = min(heights)
    top_height = max(heights)
    if top_height - base_height <= 1e-6:
        return _close_vertices_llh(pts)

    ref_lon = sum(lon for lon, _lat, _h in pts) / len(pts)
    ref_lat = sum(lat for _lon, lat, _h in pts) / len(pts)
    ref_alt = sum(heights) / len(heights)
    llh_to_enu, enu_to_llh = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)
    enu_pts = [llh_to_enu(lon, lat, h) for lon, lat, h in pts]
    base_u = float(base_height - ref_alt)
    top_u = float(top_height - ref_alt)

    def _candidate(normal_heading_deg: float) -> Optional[Tuple[float, List[Tuple[float, float, float]]]]:
        nx, ny = _heading_unit_xy(normal_heading_deg)
        tx, ty = _heading_unit_xy(normal_heading_deg + 90.0)
        normal_vals = [e * nx + n * ny for e, n, _u in enu_pts]
        tangent_vals = [e * tx + n * ty for e, n, _u in enu_pts]
        min_t = min(tangent_vals)
        max_t = max(tangent_vals)
        width = max_t - min_t
        if width <= 1e-6:
            return None
        min_n = min(normal_vals)
        max_n = max(normal_vals)
        center_n = 0.5 * (min_n + max_n)
        depth = max_n - min_n
        corners = [
            (center_n * nx + min_t * tx, center_n * ny + min_t * ty, base_u),
            (center_n * nx + max_t * tx, center_n * ny + max_t * ty, base_u),
            (center_n * nx + max_t * tx, center_n * ny + max_t * ty, top_u),
            (center_n * nx + min_t * tx, center_n * ny + min_t * ty, top_u),
        ]
        return (depth / width, corners)

    candidates = [
        item
        for item in (
            _candidate(direction_deg),
            _candidate(direction_deg + 90.0),
        )
        if item is not None
    ]
    if not candidates:
        return _close_vertices_llh(pts)

    _score, corners_enu = min(candidates, key=lambda item: item[0])
    ring: List[Tuple[float, float, float]] = []
    for e, n, u in corners_enu:
        lon, lat, alt = enu_to_llh(e, n, u)
        ring.append((float(lon), float(lat), float(alt)))
    return _close_vertices_llh(ring)


def _lift_vertices_llh_to_nonnegative(
    vertices_llh: List[Tuple[float, float, float]],
) -> Tuple[List[Tuple[float, float, float]], float]:
    """将顶点整体抬升到最低高程不低于 0；返回 (抬升后顶点, 抬升量)。"""
    if not vertices_llh:
        return [], 0.0
    min_h = min(float(h) for _lon, _lat, h in vertices_llh)
    lift = max(0.0, -min_h)
    if lift <= 1e-9:
        return list(vertices_llh), 0.0
    return [
        (float(lon), float(lat), float(h) + lift)
        for lon, lat, h in vertices_llh
    ], float(lift)


def _facade_plane_frame_from_vertices_llh(
    template_vertices_llh: List[Tuple[float, float, float]],
    ref_lon: float,
    ref_lat: float,
    ref_alt: float,
) -> Optional[Dict[str, Any]]:
    """由 facade 模板面构造局部平面坐标系：x=沿立面宽度，y=立面高度，z=离面法向距离。"""
    ring = _open_vertices_llh(template_vertices_llh)
    if len(ring) < 4:
        return None
    llh_to_enu, _ = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)
    corners_enu = [
        np.asarray(llh_to_enu(float(lon), float(lat), float(h)), dtype=np.float64)
        for lon, lat, h in ring[:4]
    ]
    origin = corners_enu[0]
    along = corners_enu[1] - corners_enu[0]
    up = corners_enu[3] - corners_enu[0]
    width = float(np.linalg.norm(along))
    height = float(np.linalg.norm(up))
    if width <= 1e-6 or height <= 1e-6:
        return None
    along_unit = along / width
    up_unit = up / height
    normal = np.cross(along_unit, up_unit)
    normal_norm = float(np.linalg.norm(normal))
    if normal_norm <= 1e-6:
        return None
    normal_unit = normal / normal_norm
    return {
        "origin_enu": tuple(float(v) for v in origin.tolist()),
        "along_unit_enu": tuple(float(v) for v in along_unit.tolist()),
        "up_unit_enu": tuple(float(v) for v in up_unit.tolist()),
        "normal_unit_enu": tuple(float(v) for v in normal_unit.tolist()),
        "width": width,
        "height": height,
        "polygon_xy": [
            (0.0, 0.0),
            (width, 0.0),
            (width, height),
            (0.0, height),
            (0.0, 0.0),
        ],
    }


def _rect_from_en_polygon(poly: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def enu_bounding_rect_xy_from_polygon_ll(
    polygon_ll: List[List[float]], ref_lon: float, ref_lat: float
) -> Tuple[float, float, float, float]:
    ll2xy, _ = build_ll_xy_transform(ref_lon, ref_lat)
    xs: List[float] = []
    ys: List[float] = []
    for p in polygon_ll:
        x, y = ll2xy(float(p[0]), float(p[1]))
        xs.append(x)
        ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))


def enu_polygon_xy_from_polygon_ll(
    polygon_ll: List[List[float]], ref_lon: float, ref_lat: float
) -> List[Tuple[float, float]]:
    """将经纬度多边形转换为投影平面坐标多边形（闭合环，与 build_ll_xy_transform 一致）。"""
    ll2xy, _ = build_ll_xy_transform(ref_lon, ref_lat)
    pts = [(float(p[0]), float(p[1])) for p in polygon_ll if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 3:
        return []
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return [ll2xy(lon, lat) for lon, lat in pts]


def enu_horizontal_polygon_from_vertices_llh(
    vertices_llh: List[Tuple[float, float, float]],
    ref_lon: float,
    ref_lat: float,
    ref_alt: float,
    *,
    prefer_base_level: bool = False,
) -> List[Tuple[float, float]]:
    """WGS84 LLH → 以 (ref_lon, ref_lat, ref_alt) 为原点的局部 ENU 水平面坐标 (E,N)（闭合环）。"""
    footprint = _ordered_horizontal_footprint_vertices_llh(
        vertices_llh,
        prefer_base_level=prefer_base_level,
    )
    source = footprint or _open_vertices_llh(vertices_llh)
    if len(source) < 3:
        return []
    llh_to_enu, _ = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)
    en_pts: List[Tuple[float, float]] = []
    for lon, lat, h in source:
        e, n, _u = llh_to_enu(lon, lat, h)
        en_pts.append((float(e), float(n)))
    if en_pts[0] != en_pts[-1]:
        en_pts.append(en_pts[0])
    return en_pts


def build_generator_mission_params(
    business_route_type: str,
    polygon_ll: List[List[float]],
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """按业务题型构造 path_generator / MissionConfig 用参数字典。"""
    run_id = f"gm-{int(time.time() * 1000)}-{os.getpid()}"
    # region agent log
    _agent_debug_log(
        run_id=run_id,
        hypothesis_id="H1",
        location="backend/app/utils/path_planner/generator_mission.py:build_generator_mission_params:entry",
        message="build_generator_mission_params entry",
        data={
            "module_file": __file__,
            "business_route_type_raw": business_route_type,
            "business_route_type_stripped": str(business_route_type).strip().lower(),
        },
    )
    # endregion
    o = dict(options or {})
    explicit_height = any(o.get(k) is not None for k in ("height", "altitude"))
    camera = _camera_from_public_fields(o)
    gsd_m_per_px = _pop_gsd_m_per_px(o)
    raw_model_file_id = (
        o.get("model_file_id") or o.get("model_id") or o.get("modelFileId") or o.get("modelId")
    )
    standoff_distance_m = _pop_standoff_distance_m(o)
    nested = o.pop("path_generator", None)
    if nested is not None and not isinstance(nested, dict):
        raise ValueError("options.path_generator 须为对象")

    kml_for_alt = o.pop("kml_json", None)
    if kml_for_alt is None:
        kml_for_alt = o.pop("input_kml_json", None)
    if kml_for_alt is None:
        kml_for_alt = o.pop("template_kml_json", None)
    alt_from_kml = _flight_altitude_from_kml_features(kml_for_alt)

    use_enu_raw = o.pop("use_enu_region_coordinates", True)
    use_enu = True if use_enu_raw is None else bool(use_enu_raw)

    region_ground_z_fallback = _pop_first_float(o, ("region_ground_z",), 0.0)

    ref_lon, ref_lat = ref_lon_lat_from_polygon_ll(polygon_ll)
    verts_llh, ref_alt_en = _vertices_llh_with_ground(polygon_ll, region_ground_z_fallback)
    region_polygon_ll = polygon_ll
    # region agent log
    _agent_debug_log(
        run_id=run_id,
        hypothesis_id="H3",
        location="backend/app/utils/path_planner/generator_mission.py:build_generator_mission_params:pre_polygon_block",
        message="pre polygon block state",
        data={
            "route_type": str(business_route_type),
            "has_mission_local": ("mission" in locals()),
            "has_rect_local": ("rect" in locals()),
            "has_poly_xy_local": ("poly_xy" in locals()),
        },
    )
    # endregion

    if business_route_type == "facade":
        lifted_verts_llh, facade_lift = _lift_vertices_llh_to_nonnegative(verts_llh)
        if facade_lift > 0.0:
            verts_llh = lifted_verts_llh
            ref_alt_en += facade_lift
            region_polygon_ll = [[lon, lat, h] for lon, lat, h in lifted_verts_llh]
    if business_route_type == "cylinder":
        # geometry UI 合同只传几何体级字段；legacy 圆柱低层参数不再下沉到 mission。
        for key in (
            "center_ll",
            "radius",
            "pitch",
            "start_z",
            "points_per_rev",
            "flight_height",
            "geometry_mode",
            "home_ll",
            "append_centroid",
        ):
            o.pop(key, None)
        footprint_llh = _ordered_horizontal_footprint_vertices_llh(
            verts_llh,
            prefer_base_level=True,
        )
        if footprint_llh:
            region_polygon_ll = [[lon, lat, h] for lon, lat, h in footprint_llh]

    if use_enu:
        poly_xy = enu_horizontal_polygon_from_vertices_llh(
            verts_llh,
            ref_lon,
            ref_lat,
            ref_alt_en,
            prefer_base_level=(business_route_type == "cylinder"),
        )
        rect = _rect_from_en_polygon(poly_xy)
        region_z_mission = ref_alt_en
        region_frame = "enu_horizontal"
    else:
        poly_xy = enu_polygon_xy_from_polygon_ll(region_polygon_ll, ref_lon, ref_lat)
        rect = enu_bounding_rect_xy_from_polygon_ll(region_polygon_ll, ref_lon, ref_lat)
        region_z_mission = region_ground_z_fallback
        region_frame = "projected_xy"

    # altitude 是航线高度基准；当 gsd 推导或显式给出 standoff/global_distance 时，
    # 由各生成器按 effective_altitude=max(altitude, global_distance_m) 执行约束。
    if explicit_height:
        altitude = _pop_first_float(o, ("height", "altitude"), 50.0)
    elif alt_from_kml is not None:
        altitude = float(alt_from_kml)
        o.pop("height", None)
        o.pop("altitude", None)
    else:
        altitude = _pop_first_float(o, ("height", "altitude"), 50.0)

    speed_ms = _pop_first_float(o, ("flight_speed", "auto_speed", "speed_ms"), 5.0)
    # 对外只接收 overlap_*；MissionConfig 内部仍使用 side_/front_。
    side_overlap = _pop_overlap_ratio(
        o,
        ("overlap_lateral",),
        0.7,
        "overlap_lateral",
    )
    front_overlap = _pop_overlap_ratio(
        o,
        ("overlap_longitudinal",),
        0.8,
        "overlap_longitudinal",
    )

    explicit_source_type = _normalize_data_source_type(
        o.pop("data_source_type", None) or o.pop("dataSourceType", None)
    )

    pc_raw = o.pop("pointcloud_path", None)
    if pc_raw is None:
        pc_raw = o.pop("point_cloud_path", None)
    if pc_raw is None:
        pc_raw = o.pop("tileset_path", None)
    if pc_raw is None:
        pc_raw = o.pop("tilesetPath", None)
    if pc_raw is None:
        pc_raw = o.pop("input_path", None)
    if pc_raw is None:
        pc_raw = o.pop("inputPath", None)
    pc_path: Optional[str] = None
    if pc_raw:
        ps = str(pc_raw).strip()
        if ps:
            p = Path(ps).expanduser()
            if p.is_file():
                pc_path = str(p)

    mission: Dict[str, Any] = {
        "altitude": altitude,
        "speed_ms": speed_ms,
        "side_overlap": side_overlap,
        "front_overlap": front_overlap,
        "region_ground_z": region_z_mission,
        "region_horizontal_frame": region_frame,
    }
    if camera:
        mission["camera"] = camera
    if standoff_distance_m is not None:
        mission["global_distance_m"] = standoff_distance_m
    # 几何题型下 altitude 负责飞行高度基准，gsd 负责航带间距约束，两者可并存。
    if gsd_m_per_px is not None:
        mission["gsd"] = gsd_m_per_px

    if business_route_type == "polygon":
        mission["algorithm"] = "boustrophedon"
        _apply_data_source_mode(
            mission,
            region_only_enabled=True,
            data_path=None,
            explicit_data_source_type=explicit_source_type,
        )
        mission["coverage_area_rect_xy"] = rect
        mission["coverage_area_polygon_xy"] = poly_xy
        # region agent log
        _agent_debug_log(
            run_id=run_id,
            hypothesis_id="H4",
            location="backend/app/utils/path_planner/generator_mission.py:build_generator_mission_params:polygon_branch",
            message="polygon branch mission compiled",
            data={
                "algorithm": mission.get("algorithm"),
                "region_only_enabled": mission.get("region_only_enabled"),
                "data_source_type": mission.get("data_source_type"),
                "has_rect": bool(mission.get("coverage_area_rect_xy")),
                "has_poly": bool(mission.get("coverage_area_polygon_xy")),
            },
        )
        # endregion
    elif business_route_type == "facade":
        mission["algorithm"] = "oblique"
        _apply_data_source_mode(
            mission,
            region_only_enabled=True,
            data_path=None,
            explicit_data_source_type=explicit_source_type,
        )
        try:
            facade_direction = float(o.get("direction", 0.0) or 0.0)
        except (TypeError, ValueError):
            facade_direction = 0.0
        try:
            cp = o.get("camera_pitch")
            mission["facade_scan_gimbal_pitch_deg"] = float(cp) if cp is not None else -40.0
        except (TypeError, ValueError):
            mission["facade_scan_gimbal_pitch_deg"] = -40.0
        template_vertices_llh = _facade_template_plane_from_vertices_llh(
            verts_llh,
            facade_direction,
        )
        facade_plane = _facade_plane_frame_from_vertices_llh(
            template_vertices_llh,
            ref_lon,
            ref_lat,
            ref_alt_en,
        )
        if facade_plane is None:
            raise ValueError("facade 输入点无法构成立面平面")
        mission["coverage_area_rect_xy"] = (0.0, 0.0, facade_plane["width"], facade_plane["height"])
        mission["coverage_area_polygon_xy"] = facade_plane["polygon_xy"]
        mission["region_horizontal_frame"] = "facade_plane"
        # 航点 z 为沿立面法向离墙工作距离：优先 global_distance_m，否则将用户 height 封顶为 15m，避免与立面总高混淆
        _gd = mission.get("global_distance_m")
        if _gd is not None and float(_gd) > 0:
            mission["altitude"] = float(_gd)
        else:
            mission["altitude"] = min(float(mission["altitude"]), 15.0)
        mission["template_vertices_llh"] = template_vertices_llh
        mission["facade_plane_origin_enu"] = facade_plane["origin_enu"]
        mission["facade_plane_along_unit_enu"] = facade_plane["along_unit_enu"]
        mission["facade_plane_up_unit_enu"] = facade_plane["up_unit_enu"]
        mission["facade_plane_normal_unit_enu"] = facade_plane["normal_unit_enu"]
        mission["facade_plane_width"] = facade_plane["width"]
        mission["facade_plane_height"] = facade_plane["height"]
        # region agent log
        _agent_debug_log(
            run_id=run_id,
            hypothesis_id="H_pre_algo",
            location="generator_mission.py:build_generator_mission_params:facade_branch_end",
            message="进入 path_generator（boustrophedon 立面弓字形）前的立面几何与 mission 摘要",
            data={
                "polygon_ll_input": polygon_ll,
                "verts_llh_effective": verts_llh,
                "region_polygon_ll": region_polygon_ll,
                "ref_lon": ref_lon,
                "ref_lat": ref_lat,
                "ref_alt_en": ref_alt_en,
                "facade_direction_deg": facade_direction,
                "template_vertices_llh": template_vertices_llh,
                "coverage_area_rect_xy": list(mission.get("coverage_area_rect_xy") or ()),
                "coverage_area_polygon_xy": mission.get("coverage_area_polygon_xy"),
                "facade_plane_origin_enu": mission.get("facade_plane_origin_enu"),
                "algorithm": mission.get("algorithm"),
                "altitude_mission": mission.get("altitude"),
                "global_distance_m": mission.get("global_distance_m"),
                "side_overlap": mission.get("side_overlap"),
                "front_overlap": mission.get("front_overlap"),
            },
        )
        # endregion
    elif business_route_type == "cylinder":
        mission["algorithm"] = "spiral"
        base_ring_llh, prism_height = _bottom_ring_and_prism_height(verts_llh, altitude)
        llh_to_enu, _ = build_llh_enu_transform(ref_lon, ref_lat, ref_alt_en)
        base_open_llh = _open_vertices_llh(base_ring_llh)
        start_lon, start_lat = _start_lon_lat_from_polygon_ll(polygon_ll, ref_lon, ref_lat)
        if base_open_llh:
            start_e, start_n, _ = llh_to_enu(start_lon, start_lat, ref_alt_en)
            nearest_idx = 0
            nearest_d2 = None
            for idx, (lon, lat, h) in enumerate(base_open_llh):
                e, n, _ = llh_to_enu(lon, lat, h)
                d2 = (float(e) - float(start_e)) ** 2 + (float(n) - float(start_n)) ** 2
                if nearest_d2 is None or d2 < nearest_d2:
                    nearest_idx = idx
                    nearest_d2 = d2
            base_open_llh = _rotate_open_ring(base_open_llh, nearest_idx)
            base_ring_llh = _close_vertices_llh(base_open_llh)
        base_vertices_enu = [
            tuple(float(v) for v in llh_to_enu(lon, lat, alt))
            for lon, lat, alt in base_open_llh
        ]
        top_vertices_enu = [
            tuple(float(v) for v in llh_to_enu(lon, lat, alt + prism_height))
            for lon, lat, alt in base_open_llh
        ]
        mission["template_vertices_llh"] = base_ring_llh
        mission["template_prism_height"] = prism_height
        mission["template_base_vertices_enu"] = base_vertices_enu
        mission["template_top_vertices_enu"] = top_vertices_enu
        _apply_data_source_mode(
            mission,
            region_only_enabled=False,
            data_path=pc_path,
            explicit_data_source_type=explicit_source_type,
        )
        mission["coverage_area_rect_xy"] = rect
        coverage_polygon_xy = [(float(e), float(n)) for e, n, _u in base_vertices_enu]
        if coverage_polygon_xy and coverage_polygon_xy[0] != coverage_polygon_xy[-1]:
            coverage_polygon_xy.append(coverage_polygon_xy[0])
        mission["coverage_area_polygon_xy"] = coverage_polygon_xy or poly_xy
    elif business_route_type == "close_photography":
        if pc_path:
            mission["algorithm"] = "viewpoint_optimized"
            _apply_data_source_mode(
                mission,
                region_only_enabled=False,
                data_path=pc_path,
                explicit_data_source_type=explicit_source_type,
            )
        else:
            mission["algorithm"] = "boustrophedon"
            _apply_data_source_mode(
                mission,
                region_only_enabled=True,
                data_path=None,
                explicit_data_source_type=explicit_source_type,
            )
            mission["coverage_area_rect_xy"] = rect
            mission["coverage_area_polygon_xy"] = poly_xy
    else:
        # region agent log
        _agent_debug_log(
            run_id=run_id,
            hypothesis_id="H2",
            location="backend/app/utils/path_planner/generator_mission.py:build_generator_mission_params:unsupported_branch",
            message="unsupported generator route type branch",
            data={
                "business_route_type": str(business_route_type),
                "available_branches": ["polygon", "facade", "cylinder", "close_photography"],
            },
        )
        # endregion
        raise ValueError(f"不支持的 generator 业务题型: {business_route_type}")

    for k, v in o.items():
        if k in (
            "input_path",
            "algorithm",
            "surface_follow",
            "action_template_id",
            "mission_config",
            "action_library",
        ):
            continue
        mission[k] = v

    if nested:
        mission.update(nested)

    _finalize_takeoff_ingress_fields(mission)

    _logger.info(
        "build_generator_mission_params: route_type=%s algorithm=%s region_only=%s",
        str(business_route_type).strip().lower(),
        str(mission.get("algorithm", "")),
        bool(mission.get("region_only_enabled")),
    )

    return mission
