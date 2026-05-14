# -*- coding: utf-8 -*-
# 自 drone_3d_path backend/app/utils/path_planner/path_editor_bridge.py 迁移：规划器米制航点 → WGS84。
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from uavplanner.path_editor.geometry import build_ll_xy_transform, build_llh_enu_transform


def ecef_xyz_to_llh_deg(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """ECEF (m) → WGS84 大地坐标 (deg, deg, m)。"""
    from pyproj import Transformer

    tr = Transformer.from_crs("EPSG:4978", "EPSG:4979", always_xy=True)
    lon, lat, alt = tr.transform(float(x), float(y), float(z))
    return float(lon), float(lat), float(alt)


def project_generator_waypoints_to_llh(
    result: Dict[str, Any],
    ref_lon: float,
    ref_lat: float,
    ref_alt: float,
    *,
    region_only_enabled: bool = False,
    region_horizontal_frame: str = "projected_xy",
    facade_plane_origin_enu: Optional[Tuple[float, float, float]] = None,
    facade_plane_along_unit_enu: Optional[Tuple[float, float, float]] = None,
    facade_plane_up_unit_enu: Optional[Tuple[float, float, float]] = None,
    facade_plane_normal_unit_enu: Optional[Tuple[float, float, float]] = None,
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[float, float, float]]]:
    """将 path_generator 风格结果中的 x/y/z 航点回投为 WGS84 llh。

    若安装 ``uav_planners``，tileset ENU→ECEF 分支可用；否则退化为 ``enu_to_llh``。
    """
    _, xy_to_ll = build_ll_xy_transform(ref_lon, ref_lat)
    _, enu_to_llh = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)
    rf = str(region_horizontal_frame or "projected_xy").strip().lower()
    meta: Dict[str, Any] = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}

    def _meta_enu_with_ecef_origin(m: Dict[str, Any]) -> bool:
        o = m.get("enu_origin_ecef")
        if not isinstance(o, (list, tuple)) or len(o) != 3:
            return False
        try:
            tuple(float(v) for v in o)
        except (TypeError, ValueError):
            return False
        return str(m.get("planning_frame", "")).strip().lower() == "enu"

    enu_to_ecef_fn = None
    use_tileset_enu = False
    if not region_only_enabled and meta and _meta_enu_with_ecef_origin(meta):
        try:
            from uav_planners.utils.waypoint_frame_converter import enu_to_ecef

            use_tileset_enu = True
            enu_to_ecef_fn = enu_to_ecef
        except ImportError:
            pass

    waypoints_enu: List[Tuple[float, float, float]] = []
    waypoints_ll: List[Tuple[float, float, float]] = []
    facade_origin = (
        tuple(float(v) for v in facade_plane_origin_enu)
        if isinstance(facade_plane_origin_enu, (list, tuple)) and len(facade_plane_origin_enu) == 3
        else None
    )
    facade_along = (
        tuple(float(v) for v in facade_plane_along_unit_enu)
        if isinstance(facade_plane_along_unit_enu, (list, tuple)) and len(facade_plane_along_unit_enu) == 3
        else None
    )
    facade_up = (
        tuple(float(v) for v in facade_plane_up_unit_enu)
        if isinstance(facade_plane_up_unit_enu, (list, tuple)) and len(facade_plane_up_unit_enu) == 3
        else None
    )
    facade_normal = (
        tuple(float(v) for v in facade_plane_normal_unit_enu)
        if isinstance(facade_plane_normal_unit_enu, (list, tuple)) and len(facade_plane_normal_unit_enu) == 3
        else None
    )
    for w in result.get("waypoints") or []:
        if not isinstance(w, dict):
            continue
        if not all(k in w for k in ("x", "y", "z")):
            continue
        x = float(w["x"])
        y = float(w["y"])
        z = float(w["z"])
        if region_only_enabled:
            if str(meta.get("algorithm", "")).strip().lower() == "prism":
                lon, lat, alt = enu_to_llh(x, y, z)
                waypoints_enu.append((x, y, z))
                waypoints_ll.append((lon, lat, alt))
                continue
            if rf == "facade_plane":
                if not all((facade_origin, facade_along, facade_up, facade_normal)):
                    raise ValueError("facade_plane 坐标回投缺少平面参考信息")
                e = facade_origin[0] + x * facade_along[0] + y * facade_up[0] + z * facade_normal[0]
                n = facade_origin[1] + x * facade_along[1] + y * facade_up[1] + z * facade_normal[1]
                u = facade_origin[2] + x * facade_along[2] + y * facade_up[2] + z * facade_normal[2]
                lon, lat, alt = enu_to_llh(e, n, u)
                waypoints_enu.append((float(e), float(n), float(u)))
                waypoints_ll.append((lon, lat, alt))
                continue
            if rf == "enu_horizontal":
                u_abs = float(ref_alt) + float(z)
                lon, lat, alt = enu_to_llh(x, y, u_abs)
            else:
                lon, lat = xy_to_ll(x, y)
                alt = float(z)
        elif use_tileset_enu and enu_to_ecef_fn is not None:
            origin = tuple(float(v) for v in meta["enu_origin_ecef"])
            xe, ye, ze = enu_to_ecef_fn(x, y, z, origin)
            lon, lat, alt = ecef_xyz_to_llh_deg(xe, ye, ze)
        else:
            lon, lat, alt = enu_to_llh(x, y, z)
        waypoints_enu.append((x, y, z))
        waypoints_ll.append((lon, lat, alt))
    return waypoints_enu, waypoints_ll


def waypoint_wpml_attrs_from_generator_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """与 ``project_generator_waypoints_to_llh`` 相同的航点过滤顺序，供 ``waypoint_wpml_attrs`` 与 LLH 对齐。"""
    out: List[Dict[str, Any]] = []
    for w in result.get("waypoints") or []:
        if not isinstance(w, dict):
            continue
        if not all(k in w for k in ("x", "y", "z")):
            continue
        attr: Dict[str, Any] = {
            "enu_x": float(w["x"]),
            "enu_y": float(w["y"]),
            "enu_z": float(w["z"]),
        }
        if w.get("heading_deg") is not None:
            try:
                attr["heading_deg"] = float(w["heading_deg"])
            except (TypeError, ValueError):
                pass
        if w.get("gimbal_pitch_deg") is not None:
            try:
                attr["gimbal_pitch_deg"] = float(w["gimbal_pitch_deg"])
            except (TypeError, ValueError):
                pass
        if w.get("speed_ms") is not None:
            try:
                attr["speed_ms"] = float(w["speed_ms"])
            except (TypeError, ValueError):
                pass
        for key in ("gimbal_yaw_deg", "aircraft_roll_deg", "aircraft_pitch_deg"):
            if w.get(key) is None:
                continue
            try:
                attr[key] = float(w[key])
            except (TypeError, ValueError):
                pass
        out.append(attr)
    return out
