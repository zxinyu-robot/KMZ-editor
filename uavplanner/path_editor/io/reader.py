# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 文件读取 - KML/KMZ/GeoJSON/JSON 多边形与点列表解析
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""文件 I/O 层：从 KML、KMZ、GeoJSON、JSON 解析多边形、点列表与参数。"""

import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Optional

from ..output.kmz import EXTRA_PLANNING_FIELD_NAMES, build_minimal_template_kml, build_minimal_waypoint_template
from ..output.action_library import parse_action_library_from_wpml

NS_WPML = "http://www.dji.com/wpmz/1.0.6"
NS_KML = "http://www.opengis.net/kml/2.2"


def _extract_template_type_from_kml(root: ET.Element) -> Optional[str]:
    """从 KML 根节点提取 wpml:templateType。"""
    for elem in root.iter():
        tag = (elem.tag or "").split("}")[-1]
        if tag == "templateType" and elem.text:
            return elem.text.strip().lower()
    return None


def _extract_points_from_kml_root(root: ET.Element) -> List[Tuple[float, float]]:
    """从 KML 根节点提取 Point Placemark 坐标 [(lon, lat), ...]。"""
    points_ll = []
    for pm in root.iter():
        if "Placemark" not in (pm.tag or ""):
            continue
        pt = None
        for child in pm:
            tag = (child.tag or "").split("}")[-1]
            if tag == "Point":
                pt = child
                break
        if pt is None:
            continue
        for coords in pt.iter():
            if "coordinates" in (coords.tag or "").lower() and coords.text:
                for line in coords.text.strip().split():
                    parts = line.strip().split(",")
                    if len(parts) >= 2:
                        points_ll.append((float(parts[0]), float(parts[1])))
                        break
                break
    return points_ll


def extract_waypoints_from_wpml(wpml_bytes: bytes) -> List[Tuple[float, float, float]]:
    """从 waylines.wpml 解析航点 [(lon, lat, alt), ...]，按 index 排序。"""
    root = ET.fromstring(wpml_bytes)
    waypoints: List[Tuple[int, float, float, float]] = []  # (index, lon, lat, alt)
    for pm in root.iter():
        if "Placemark" not in (pm.tag or ""):
            continue
        lon, lat, alt = None, None, 100.0
        idx = -1
        for child in pm:
            tag = (child.tag or "").split("}")[-1]
            if tag == "Point":
                for coords in child.iter():
                    if "coordinates" in (coords.tag or "").lower() and coords.text:
                        parts = coords.text.strip().split()[0].split(",")
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                        break
            elif tag == "index" and child.text:
                try:
                    idx = int(child.text)
                except ValueError:
                    pass
            elif tag == "executeHeight" and child.text:
                try:
                    alt = float(child.text)
                except ValueError:
                    pass
        if lon is not None and lat is not None and idx >= 0:
            waypoints.append((idx, lon, lat, alt))
    waypoints.sort(key=lambda x: x[0])
    return [(lon, lat, alt) for _, lon, lat, alt in waypoints]


def _extract_polygon_from_kml_root(root: ET.Element) -> List[Tuple[float, float]]:
    """从 KML ElementTree 根节点提取多边形顶点 [(lon, lat), ...]。"""
    polygon_ll = []
    for coords in root.iter():
        if "coordinates" in (coords.tag or "").lower() and coords.text:
            for line in coords.text.strip().split():
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    polygon_ll.append((float(parts[0]), float(parts[1])))
            if len(polygon_ll) >= 3:
                break
    return polygon_ll


def parse_polygon_from_kmz(kmz_path: str) -> List[Tuple[float, float]]:
    """从 KMZ 的 template.kml 解析 Polygon 顶点 [(lon, lat), ...]。供 verify、test 等复用。"""
    path = Path(kmz_path)
    if not path.exists():
        raise FileNotFoundError(str(kmz_path))
    with zipfile.ZipFile(path, "r") as z:
        tpl = z.read("wpmz/template.kml")
    root = ET.fromstring(tpl)
    return _extract_polygon_from_kml_root(root)


def parse_waypoints_from_kmz(kmz_path: str) -> List[Tuple[float, float, float]]:
    """从 KMZ 的 waylines.wpml 解析航点 [(lon, lat, alt), ...]，按 index 排序。供 verify、test 等复用。"""
    path = Path(kmz_path)
    if not path.exists():
        raise FileNotFoundError(str(kmz_path))
    with zipfile.ZipFile(path, "r") as z:
        try:
            wpml = z.read("wpmz/waylines.wpml")
        except KeyError:
            return []
    return extract_waypoints_from_wpml(wpml)


def _extract_overlap_from_kml(root: ET.Element) -> dict:
    """从 KML 根节点 Placemark 下 wpml:overlap 提取重叠率。ortho/inclined H=航向、W=旁向，0-100 转为 0-1。"""
    out = {}
    for pm in root.iter():
        if "Placemark" not in (pm.tag or ""):
            continue
        for child in pm:
            tag = (child.tag or "").split("}")[-1]
            if tag != "overlap":
                continue
            for sub in child:
                st = (sub.tag or "").split("}")[-1]
                if sub.text and sub.text.strip():
                    try:
                        v = float(sub.text) / 100.0  # 80 -> 0.8
                        if "OverlapH" in st:
                            out["overlap_longitudinal"] = max(0, min(1, v))
                        elif "OverlapW" in st:
                            out["overlap_lateral"] = max(0, min(1, v))
                    except ValueError:
                        pass
            if out:
                return out
    return out


def _extract_margin_from_kml(root: ET.Element) -> Optional[float]:
    """从 KML 根节点 Placemark 下 wpml:margin 提取边界内缩（米）。"""
    for pm in root.iter():
        if "Placemark" not in (pm.tag or ""):
            continue
        for child in pm:
            tag = (child.tag or "").split("}")[-1]
            if tag == "margin" and child.text and child.text.strip():
                try:
                    return float(child.text)
                except ValueError:
                    pass
    return None


def _extract_params_from_kml_root(root: ET.Element) -> dict:
    """从 KML 根节点提取 direction, height, auto_speed, overlap, margin 等参数。"""
    params = {"direction": 0.0, "height": 100.0, "auto_speed": 10.0}
    for elem in root.iter():
        tag = (elem.tag or "").split("}")[-1]
        if elem.text and elem.text.strip():
            try:
                if tag == "direction":
                    params["direction"] = float(elem.text)
                elif tag in ("globalShootHeight", "ellipsoidHeight", "height"):
                    params["height"] = float(elem.text)
                elif tag == "autoFlightSpeed":
                    params["auto_speed"] = float(elem.text)
            except ValueError:
                pass
    overlap = _extract_overlap_from_kml(root)
    if overlap:
        params.update(overlap)
    margin = _extract_margin_from_kml(root)
    if margin is not None:
        params["margin"] = margin

    # 读取由 _apply_extra_planning_params_to_template 写入的规划专用参数
    _extract_extra_planning_params_from_kml(root, params)

    return params


def _extract_extra_planning_params_from_kml(root: ET.Element, params: dict) -> None:
    """从 template.kml Document/ExtendedData 读回规划专用参数（EXTRA_PLANNING_FIELD_NAMES）。"""
    doc = root.find(f".//{{{NS_KML}}}Document")
    if doc is None:
        return
    ext = doc.find(f"{{{NS_KML}}}ExtendedData")
    if ext is None:
        return

    _BOOL_FIELDS = {
        "use_camera",
        "optimize_path",
        "with_timestamps",
        "ortho_capture_enabled",
        "oblique_capture_enabled",
        "include_top_cap",
        "append_centroid",
    }
    _FLOAT_FIELDS = {
        "gsd_cm_per_px",
        "spacing",
        "reference_time",
        "ir_gsd",
        "start_z",
        "survey_top_asl",
        "survey_bottom_asl",
        "side_flight_speed",
        "coverage_yaw_offset",
        "sweep_yaw_offset",
        "pitch",
        "flight_height",
        "coverage_ratio",
        "start_azimuth_deg",
    }
    _STR_FIELDS = {
        "camera_preset",
        "climb_mode",
        "vertical_climb_mode",
        "oblique_climb_mode",
        "route_orientation",
        "geometry_mode",
        "payload_lens_index",
    }
    _LL_FIELDS = {"start_ll", "end_ll", "home_ll"}

    for data_elem in ext:
        name = data_elem.attrib.get("name", "")
        if name not in EXTRA_PLANNING_FIELD_NAMES:
            continue
        value_text = None
        for c in data_elem:
            if (c.tag or "").endswith("value") and c.text:
                value_text = c.text.strip()
                break
        if not value_text:
            continue

        if name in _BOOL_FIELDS:
            params[name] = value_text.lower() in ("true", "1")
        elif name in _FLOAT_FIELDS:
            try:
                params[name] = float(value_text)
            except (TypeError, ValueError):
                pass
        elif name in _STR_FIELDS:
            params[name] = value_text
        elif name in _LL_FIELDS:
            parts = value_text.split(",")
            if len(parts) == 2:
                try:
                    params[name] = (float(parts[0]), float(parts[1]))
                except (TypeError, ValueError):
                    pass
        elif name == "points_per_rev":
            try:
                params[name] = int(float(value_text))
            except (TypeError, ValueError):
                pass
        elif name == "takeoff_ingress_pose":
            try:
                parsed = json.loads(value_text)
                if isinstance(parsed, dict):
                    params[name] = parsed
            except json.JSONDecodeError:
                pass


def _extract_wayline_coord_sys_from_kml(root: ET.Element) -> dict:
    """从 KML 根节点提取 waylineCoordinateSysParam（仿地等）。"""
    params = {}
    for folder in root.iter():
        if "Folder" not in (folder.tag or ""):
            continue
        for child in folder:
            if "waylineCoordinateSysParam" not in (child.tag or ""):
                continue
            for sub in child:
                tag = (sub.tag or "").split("}")[-1]
                if sub.text and sub.text.strip():
                    if tag == "surfaceFollowModeEnable":
                        params["surface_follow_enable"] = sub.text.strip() in ("1", "true")
                    elif tag == "surfaceRelativeHeight":
                        try:
                            params["surface_relative_height"] = float(sub.text)
                        except ValueError:
                            pass
                    elif tag == "isRealtimeSurfaceFollow":
                        params["is_realtime_surface_follow"] = sub.text.strip() in ("1", "true")
            break
        if params:
            break
    return params


def _extract_mission_config_from_kml(root: ET.Element) -> dict:
    """从 KML 根节点提取 missionConfig（F-006 ~ F-014）。"""
    mission = {}
    for mc in root.iter():
        if "missionConfig" not in (mc.tag or ""):
            continue
        for child in mc:
            tag = (child.tag or "").split("}")[-1]
            if child.text and child.text.strip():
                if tag == "flyToWaylineMode":
                    mission["fly_to_wayline_mode"] = child.text.strip()
                elif tag == "finishAction":
                    mission["finish_action"] = child.text.strip()
                elif tag == "exitOnRCLost":
                    mission["exit_on_rc_lost"] = child.text.strip()
                elif tag == "executeRCLostAction":
                    mission["execute_rc_lost_action"] = child.text.strip()
                elif tag == "takeOffSecurityHeight":
                    try:
                        mission["take_off_security_height"] = float(child.text)
                    except ValueError:
                        pass
                elif tag == "globalTransitionalSpeed":
                    try:
                        mission["global_transitional_speed"] = float(child.text)
                    except ValueError:
                        pass
                elif tag == "globalRTHHeight":
                    try:
                        mission["global_rth_height"] = float(child.text)
                    except ValueError:
                        pass
        break
    return mission


def _parse_geojson_points(data: dict) -> List[Tuple[float, float]]:
    """从 GeoJSON 结构中解析点列表（MultiPoint、Point）。"""
    geom = data
    if data.get("type") == "Feature":
        geom = data.get("geometry") or {}
    if geom.get("type") == "FeatureCollection":
        features = geom.get("features") or []
        out = []
        for f in features:
            g = f.get("geometry") or {}
            pts = _get_points_from_geom(g)
            if pts:
                out.extend(pts)
        return out if out else []
    return _get_points_from_geom(geom)


def _get_points_from_geom(geom: dict) -> List[Tuple[float, float]]:
    """从 Point、MultiPoint 或 LineString 几何体提取 [(lon, lat), ...]。"""
    if geom.get("type") == "Point":
        c = geom.get("coordinates")
        if c and len(c) >= 2:
            return [(float(c[0]), float(c[1]))]
        return []
    if geom.get("type") == "MultiPoint":
        coords = geom.get("coordinates") or []
        out = []
        for c in coords:
            if c and len(c) >= 2:
                out.append((float(c[0]), float(c[1])))
        return out
    if geom.get("type") == "LineString":
        coords = geom.get("coordinates") or []
        return [(float(c[0]), float(c[1])) for c in coords if c and len(c) >= 2]
    return []


def _parse_geojson_coordinates(data: dict) -> List[Tuple[float, float]]:
    """从 GeoJSON 结构中解析多边形外环坐标。"""
    geom = data
    if data.get("type") == "Feature":
        geom = data.get("geometry") or {}
    if geom.get("type") == "FeatureCollection":
        features = geom.get("features") or []
        for f in features:
            g = f.get("geometry") or {}
            if g.get("type") in ("Polygon", "MultiPolygon"):
                coords = _get_first_ring(g)
                if coords:
                    return coords
        return []
    if geom.get("type") == "Polygon":
        rings = geom.get("coordinates") or []
        if rings:
            return _ring_to_ll(rings[0])
    if geom.get("type") == "MultiPolygon":
        polys = geom.get("coordinates") or []
        if polys and polys[0]:
            return _ring_to_ll(polys[0][0])
    return []


def _extract_geojson_feature_properties(data: dict) -> dict:
    """从 GeoJSON 提取 properties（优先取第一个有效 Feature 的 properties）。

    当前规划逻辑主要依赖 geometry；properties 用于透传 Pxx 参数（可选）。
    """
    if not isinstance(data, dict):
        return {}

    if data.get("type") == "Feature":
        props = data.get("properties")
        return props if isinstance(props, dict) else {}

    if data.get("type") == "FeatureCollection":
        for f in data.get("features") or []:
            if not isinstance(f, dict):
                continue
            props = f.get("properties")
            if isinstance(props, dict) and props:
                return props
        # 兜底：允许空 properties，但不影响解析
        return {}

    # 非标准 GeoJSON：尝试直接读顶层 properties
    props = data.get("properties")
    return props if isinstance(props, dict) else {}


def _normalize_rate_0_to_1(v: object) -> Optional[float]:
    """将重叠率归一到 [0,1]。

    支持两种输入：
    - 0~1 的浮点/字符串（例如 0.7）
    - 0~100 的百分比（例如 70）
    """
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None

    if x > 1.0:
        x = x / 100.0
    return max(0.0, min(1.0, x))


def _apply_polygon_props_to_params(
    props: dict,
    params: dict,
    polygon_ll: Optional[List[Tuple[float, float]]] = None,
) -> None:
    """把 properties 中的 Pxx 字段映射到 planning 参数/写回参数字典。

    说明：
    - 这里不会改变 HTTP/CLI 入参结构；仅把 GeoJSON properties 的字段映射到后端当前能消费的参数键。
    - mapping2d 当前主要消费：spacing/height/direction/margin/overlap_*、以及 writer 消费的 mission_config/surface_follow/action_overrides/start_ll 等。
    """
    if not isinstance(props, dict):
        return

    def _get_float(key: str) -> Optional[float]:
        if key not in props:
            return None
        try:
            return float(props.get(key))
        except (TypeError, ValueError):
            return None

    def _get_int(key: str) -> Optional[int]:
        x = _get_float(key)
        if x is None:
            return None

    def _normalize_heading_mode(v: object) -> Optional[str]:
        if v is None:
            return None
        # 兼容枚举编码：1=fixed, 2=followWayline
        try:
            iv = int(float(v))
            if iv == 1:
                return "fixed"
            if iv == 2:
                return "followWayline"
        except (TypeError, ValueError):
            pass
        s = str(v).strip()
        if not s:
            return None
        sl = s.lower()
        if sl == "fixed":
            return "fixed"
        if sl in ("followwayline", "follow_wayline"):
            return "followWayline"
        return None

    def _parse_takeoff_ref_point(v: object) -> Optional[str]:
        """解析 P18，标准化为 'lat,lon,height' 字符串。"""
        if v is None:
            return None

        # 1) 直接字符串：'lat,lon,height' 或 'lon,lat,height'
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",")]
            if len(parts) == 3:
                try:
                    a, b, c = float(parts[0]), float(parts[1]), float(parts[2])
                    # 规则：若第一段明显是经度（绝对值>90），按 lon,lat,height 纠正
                    if abs(a) > 90 and abs(b) <= 90:
                        lon, lat, h = a, b, c
                    else:
                        lat, lon, h = a, b, c
                    return f"{lat:.6f},{lon:.6f},{h:.3f}"
                except (TypeError, ValueError):
                    return None
            return None

        # 2) 数组：[lon,lat,height] 或 [lat,lon,height]（按同样规则判定）
        if isinstance(v, (list, tuple)) and len(v) >= 3:
            try:
                a, b, c = float(v[0]), float(v[1]), float(v[2])
                if abs(a) > 90 and abs(b) <= 90:
                    lon, lat, h = a, b, c
                else:
                    lat, lon, h = a, b, c
                return f"{lat:.6f},{lon:.6f},{h:.3f}"
            except (TypeError, ValueError):
                return None

        # 3) 对象：优先 lat/lon 字段
        if isinstance(v, dict):
            lat = v.get("lat") if v.get("lat") is not None else v.get("latitude")
            lon = v.get("lon")
            if lon is None:
                lon = v.get("lng") if v.get("lng") is not None else v.get("longitude")
            h = v.get("height")
            if h is None:
                h = v.get("alt") if v.get("alt") is not None else v.get("z")
            try:
                if lat is not None and lon is not None and h is not None:
                    return f"{float(lat):.6f},{float(lon):.6f},{float(h):.3f}"
            except (TypeError, ValueError):
                return None
        return None
        try:
            return int(x)
        except (TypeError, ValueError):
            return None

    # ========== 1) 面状算法直接消费 ==========

    # P04 安全起飞高度 -> height（当前算法将 height 视为航点高度）
    p04 = _get_float("P04")
    if p04 is not None:
        params["height"] = p04

    # P11/P12 重叠率 -> overlap_lateral / overlap_longitudinal
    p11 = _normalize_rate_0_to_1(props.get("P11"))
    if p11 is not None:
        params["overlap_lateral"] = p11
    p12 = _normalize_rate_0_to_1(props.get("P12"))
    if p12 is not None:
        params["overlap_longitudinal"] = p12

    # O05/O06（倾斜重叠率）-> overlap_lateral_inclined / overlap_longitudinal_inclined
    o05 = _normalize_rate_0_to_1(props.get("O05"))
    if o05 is not None:
        params["overlap_lateral_inclined"] = o05
    o06 = _normalize_rate_0_to_1(props.get("O06"))
    if o06 is not None:
        params["overlap_longitudinal_inclined"] = o06

    # P13 边距 -> margin
    p13 = _get_float("P13")
    if p13 is not None:
        params["margin"] = p13

    # P19 主航线角度 -> direction
    p19 = _get_float("P19")
    if p19 is not None:
        params["direction"] = p19

    # P02 GSD(cm/px) -> 暂存到 gsd_cm_per_px，后续由外层做 spacing 推导（避免依赖 camera_preset）
    p02 = _get_float("P02")
    if p02 is not None:
        params["gsd_cm_per_px"] = p02

    # P05/P06/P10 速度类 -> flight_speed（算法用于可选时间语义） & auto_speed（writer 用于 duration/waypointSpeed）
    # P05：全局航线速度（m/s）
    p05 = _get_float("P05")  # 全局航线速度
    p06 = _get_float("P06")  # 主航线速度槽位：航段速度 m/s（writer 的 auto_speed 口径）
    p10 = _get_float("P10")  # 被摄面海拔速度（当前工程缺少更细分落点：作为 auto_speed 的兜底）

    auto_speed = p06 if p06 is not None else (p05 if p05 is not None else p10)
    if auto_speed is not None:
        params["auto_speed"] = auto_speed
        params["flight_speed"] = auto_speed

    # P16 起始点策略 -> start_ll（几何层使用）
    if polygon_ll is not None and len(polygon_ll) >= 3 and ("P16" in props):
        p16 = _get_int("P16")
        if p16 is not None:
            # 四角定义：NE/NW/SE/SW 用目标角点（lon/lat 方向）并在 polygon 顶点中找最近点
            lon_vals = [p[0] for p in polygon_ll]
            lat_vals = [p[1] for p in polygon_ll]
            min_lon, max_lon = min(lon_vals), max(lon_vals)
            min_lat, max_lat = min(lat_vals), max(lat_vals)
            if p16 == 1:  # corner_ne
                target = (max_lon, max_lat)
            elif p16 == 2:  # corner_nw
                target = (min_lon, max_lat)
            elif p16 == 3:  # corner_se
                target = (max_lon, min_lat)
            elif p16 == 4:  # corner_sw
                target = (min_lon, min_lat)
            else:
                target = None

            if target is not None:
                best = None
                best_d2 = None
                for lon, lat in polygon_ll:
                    dx = lon - target[0]
                    dy = lat - target[1]
                    d2 = dx * dx + dy * dy
                    if best is None or d2 < best_d2:
                        best = (lon, lat)
                        best_d2 = d2
                if best is not None:
                    params["start_ll"] = best

    # P03 航点高度模式 -> execute_height_mode（writer 用于解释 executeHeight）
    # WPML executeHeightMode 枚举：
    #   msl -> WGS84
    #   agl_takeoff -> relativeToStartPoint
    #   agl_terrain -> realTimeFollowSurface
    p03 = _get_int("P03")
    if p03 is not None:
        if p03 == 1:
            params["execute_height_mode"] = "WGS84"
        elif p03 == 2:
            params["execute_height_mode"] = "relativeToStartPoint"
        elif p03 == 3:
            params["execute_height_mode"] = "realTimeFollowSurface"

    # P26/P27 飞行器偏航参数 -> writer 航点 heading
    heading_mode = _normalize_heading_mode(props.get("P26"))
    if heading_mode is not None:
        params["heading_mode"] = heading_mode
    p27 = _get_float("P27")
    if p27 is not None:
        # 统一归一到 [0, 360)
        params["heading_angle"] = float(p27) % 360.0

    # ========== 2) Writer 消费字段 ==========

    # P07 高程优化 + P25 仿地相对高度 -> surface_follow（writer 写入 waylineCoordinateSysParam）
    p07_raw = props.get("P07")
    p07: Optional[int]
    try:
        p07 = int(float(p07_raw)) if p07_raw is not None else None
    except (TypeError, ValueError):
        p07 = None
    p25 = _get_float("P25")
    if p07 is not None:
        # 策略开关：off=0,on=1
        enabled = bool(p07)
        if enabled:
            params["surface_follow"] = {
                "surface_follow_enable": True,
                # 优先 P25；若未提供则回退到 height
                "surface_relative_height": float(p25 if p25 is not None else params.get("height", 100.0)),
                "is_realtime_surface_follow": params.get("execute_height_mode") == "realTimeFollowSurface",
            }

    # MissionConfig：P04/P05/P08/P09/P18/P20
    p08 = _get_int("P08")
    p09 = _get_float("P09")
    p20 = _get_float("P20")
    p18 = _parse_takeoff_ref_point(props.get("P18"))

    if any(k in props for k in ("P04", "P05", "P08", "P09", "P18", "P20")):
        cfg = dict(params.get("mission_config") or {})

        # P04：安全起飞高度
        if p04 is not None:
            cfg["take_off_security_height"] = p04

        # P08：完成动作（映射到 WPML finishAction）
        if p08 is not None:
            if p08 == 1:  # go_home
                cfg["finish_action"] = "goHome"
            elif p08 == 2:  # goto_first_hover
                cfg["finish_action"] = "gotoFirstWaypoint"
            elif p08 == 3:  # exit
                cfg["finish_action"] = "noAction"
            elif p08 == 4:  # auto_land
                cfg["finish_action"] = "autoLand"

        # P09：起飞速度 -> missionConfig.globalTransitionalSpeed（当前工程中唯一的速度口径）
        if p09 is not None:
            cfg["global_transitional_speed"] = p09
        elif p05 is not None and "global_transitional_speed" not in cfg:
            cfg["global_transitional_speed"] = p05

        # P18：起飞点参考坐标（lat,lon,height）
        if p18 is not None:
            cfg["take_off_ref_point"] = p18

        # P20：起飞点参考 AGL 高度
        if p20 is not None:
            cfg["take_off_ref_point_agl_height"] = p20

        # 允许 writer 识别：将任务配置放入 mission_config 字段
        if cfg:
            params["mission_config"] = cfg

    # P14 拍照模式 / P15 自定义相机角度：writer action override
    p14 = _get_int("P14")
    if p14 is not None:
        if p14 == 1:
            params["capture_mode"] = "time"
        elif p14 == 2:
            params["capture_mode"] = "distance"
    p15 = _get_float("P15")
    if p15 is not None:
        params["camera_pitch"] = p15

    # P01 正射投影：作为题型/模板选择标识；当前 reader 仅生成 mapping2d minimal 模板，因此这里只透传
    p01 = _get_int("P01")
    if p01 is not None:
        params["projection_type"] = p01

    # properties 直传 canonical 字段（与 params 同名）
    # 用于 input_path 场景下的联调：前端可直接把 UI=>params 的字段写入 properties，
    # 避免必须手工用 Pxx/Oxx slot 键。
    def _get_float_prop(key: str) -> Optional[float]:
        if key not in props:
            return None
        try:
            return float(props.get(key))
        except (TypeError, ValueError):
            return None

    # 几何/规划字段
    h = _get_float_prop("height")
    if h is not None:
        params["height"] = h
    d = _get_float_prop("direction")
    if d is not None:
        params["direction"] = d % 360.0
    ml = _normalize_rate_0_to_1(props.get("overlap_lateral"))
    if ml is not None:
        params["overlap_lateral"] = ml
    ml_in = _normalize_rate_0_to_1(props.get("overlap_lateral_inclined"))
    if ml_in is not None:
        params["overlap_lateral_inclined"] = ml_in
    mlong = _normalize_rate_0_to_1(props.get("overlap_longitudinal"))
    if mlong is not None:
        params["overlap_longitudinal"] = mlong
    mlong_in = _normalize_rate_0_to_1(props.get("overlap_longitudinal_inclined"))
    if mlong_in is not None:
        params["overlap_longitudinal_inclined"] = mlong_in
    m = _get_float_prop("margin")
    if m is not None:
        params["margin"] = m
    gsd = _get_float_prop("gsd_cm_per_px")
    if gsd is not None:
        params["gsd_cm_per_px"] = gsd

    # 速度字段：全局/航段（规划几何使用）
    gf = _get_float_prop("global_flight_speed")
    if gf is not None:
        params["global_flight_speed"] = gf
    mr = _get_float_prop("main_route_speed")
    if mr is not None:
        params["main_route_speed"] = mr
    fs = _get_float_prop("flight_speed")
    if fs is not None and "global_flight_speed" not in props and mr is None:
        params["flight_speed"] = fs

    # 写回字段：完成动作 / 起飞速度等 missionConfig
    mission_cfg = dict(params.get("mission_config") or {})
    th = _get_float_prop("take_off_security_height")
    if th is not None:
        mission_cfg["take_off_security_height"] = th
    fa = props.get("finish_action")
    if fa is not None:
        mission_cfg["finish_action"] = str(fa).strip()
    gts = _get_float_prop("global_transitional_speed")
    if gts is not None:
        mission_cfg["global_transitional_speed"] = gts
    if mission_cfg:
        params["mission_config"] = mission_cfg

    # 拍照模式（writer 写 shootType）
    cm = props.get("capture_mode")
    if cm is not None:
        params["capture_mode"] = str(cm).strip().lower()


def _get_first_ring(geom: dict) -> List[Tuple[float, float]]:
    if geom.get("type") == "Polygon":
        rings = geom.get("coordinates") or []
        if rings:
            return _ring_to_ll(rings[0])
    if geom.get("type") == "MultiPolygon":
        polys = geom.get("coordinates") or []
        if polys and polys[0]:
            return _ring_to_ll(polys[0][0])
    return []


def _ring_to_ll(ring: list) -> List[Tuple[float, float]]:
    """将 GeoJSON 环 [[lon, lat], ...] 转为 [(lon, lat), ...]，去除重复首尾。"""
    out = []
    for pt in ring:
        if len(pt) >= 2:
            out.append((float(pt[0]), float(pt[1])))
    if len(out) >= 2 and out[0] == out[-1]:
        out = out[:-1]
    return out


def read_kml(kml_path: str) -> Tuple[bytes, Optional[bytes], List[Tuple[float, float]], dict]:
    """读取独立 KML 文件。支持多边形与点列表（Point Placemarks）。"""
    path = Path(kml_path)
    if not path.exists():
        raise FileNotFoundError(kml_path)
    tpl_kml = path.read_bytes()
    root = ET.fromstring(tpl_kml)
    params = _extract_params_from_kml_root(root)
    template_type = _extract_template_type_from_kml(root)

    if template_type == "waypoint":
        points_ll = _extract_points_from_kml_root(root)
        if len(points_ll) >= 1:
            params["input_type"] = "waypoint"
            params["template_type"] = "waypoint"
            return tpl_kml, None, points_ll, params

    polygon_ll = _extract_polygon_from_kml_root(root)
    if len(polygon_ll) >= 3:
        params["input_type"] = "polygon"
        return tpl_kml, None, polygon_ll, params

    points_ll = _extract_points_from_kml_root(root)
    if len(points_ll) >= 1:
        params["input_type"] = "waypoint"
        tpl_kml = build_minimal_waypoint_template(points_ll, params.get("height", 100.0))
        return tpl_kml, None, points_ll, params

    raise ValueError(f"KML 中未找到有效多边形（至少 3 顶点）或航点（至少 1 点）: {kml_path}")


def read_geojson(geojson_path: str) -> Tuple[bytes, Optional[bytes], List[Tuple[float, float]], dict]:
    """读取 GeoJSON 文件。支持 MultiPoint/Point（航点）与 Polygon/MultiPolygon（面状）。"""
    path = Path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(geojson_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    params = {"direction": 0.0, "height": 100.0, "auto_speed": 10.0}
    # 可选：从 properties 覆盖规划参数（缺省则保持默认值）
    props = _extract_geojson_feature_properties(data)

    points_ll = _parse_geojson_points(data)
    if len(points_ll) >= 1:
        _apply_polygon_props_to_params(props, params, polygon_ll=None)
        params["input_type"] = "waypoint"
        tpl_kml = build_minimal_waypoint_template(points_ll, height=100.0)
        return tpl_kml, None, points_ll, params

    polygon_ll = _parse_geojson_coordinates(data)
    if len(polygon_ll) >= 3:
        _apply_polygon_props_to_params(props, params, polygon_ll=polygon_ll)
        params["input_type"] = "polygon"
        tpl_kml = build_minimal_template_kml(
            polygon_ll,
            height=params.get("height", 100.0),
            direction=params.get("direction", 0.0),
        )
        return tpl_kml, None, polygon_ll, params

    raise ValueError(
        f"GeoJSON 中未找到有效多边形（至少 3 顶点）或点列表（MultiPoint/Point，至少 1 点）: {geojson_path}"
    )


def read_json_polygon(json_path: str) -> Tuple[bytes, Optional[bytes], List[Tuple[float, float]], dict]:
    """读取 JSON 数据。支持点列表（coordinates/points/waypoints）与多边形。"""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    params = {"direction": 0.0, "height": 100.0, "auto_speed": 10.0}

    points_ll = _parse_geojson_points(data)
    if not points_ll:
        points_ll = _parse_json_points(data)
    if len(points_ll) >= 1:
        params["input_type"] = "waypoint"
        tpl_kml = build_minimal_waypoint_template(points_ll, height=params["height"])
        return tpl_kml, None, points_ll, params

    polygon_ll = _parse_geojson_coordinates(data)
    if not polygon_ll:
        coords = data.get("coordinates") or data.get("points") or data.get("polygon")
        if isinstance(coords, list) and len(coords) >= 3:
            out = []
            for pt in coords:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    out.append((float(pt[0]), float(pt[1])))
                elif isinstance(pt, dict):
                    lon = pt.get("longitude") or pt.get("lon") or pt.get("lng")
                    lat = pt.get("latitude") or pt.get("lat")
                    if lon is not None and lat is not None:
                        out.append((float(lon), float(lat)))
            if len(out) >= 3:
                polygon_ll = out

    if len(polygon_ll) >= 3:
        params["input_type"] = "polygon"
        tpl_kml = build_minimal_template_kml(polygon_ll, height=100.0, direction=0.0)
        return tpl_kml, None, polygon_ll, params

    raise ValueError(f"JSON 中未找到有效多边形（至少 3 顶点）或点列表（至少 1 点）: {json_path}")


def _parse_json_points(data: dict) -> List[Tuple[float, float]]:
    """从 JSON 中解析点数组。支持 coordinates、points、waypoints 等字段。"""
    for key in ("coordinates", "points", "waypoints", "path"):
        coords = data.get(key)
        if not isinstance(coords, list) or len(coords) < 1:
            continue
        out = []
        for pt in coords:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                out.append((float(pt[0]), float(pt[1])))
            elif isinstance(pt, dict):
                lon = pt.get("longitude") or pt.get("lon") or pt.get("lng")
                lat = pt.get("latitude") or pt.get("lat")
                if lon is not None and lat is not None:
                    out.append((float(lon), float(lat)))
        if out:
            return out
    return []


def read_kmz(kmz_path: str) -> Tuple[bytes, Optional[bytes], List[Tuple[float, float]], dict]:
    """读取 KMZ 文件。支持 waypoint（点列表）与 mapping2d/mapping3d（多边形）模板。"""
    path = Path(kmz_path)
    if not path.exists():
        raise FileNotFoundError(kmz_path)

    with zipfile.ZipFile(path, "r") as z:
        tpl_kml = z.read("wpmz/template.kml")
        try:
            tpl_wpml = z.read("wpmz/waylines.wpml")
        except KeyError:
            tpl_wpml = None

    root = ET.fromstring(tpl_kml)
    template_type = _extract_template_type_from_kml(root)
    params = _extract_params_from_kml_root(root)
    params["template_type"] = template_type or "mapping2d"
    mission_cfg = _extract_mission_config_from_kml(root)
    if mission_cfg:
        params["mission_config"] = mission_cfg
    surface_follow = _extract_wayline_coord_sys_from_kml(root)
    if surface_follow:
        params["surface_follow"] = surface_follow

    if template_type == "waypoint":
        if tpl_wpml:
            waypoints = extract_waypoints_from_wpml(tpl_wpml)
            points_ll = [(w[0], w[1]) for w in waypoints]
            params["waypoints_3d"] = waypoints
        else:
            points_ll = _extract_points_from_kml_root(root)
        if len(points_ll) < 1:
            raise ValueError(f"KMZ waypoint 模板中未找到有效航点: {kmz_path}")
        params["input_type"] = "waypoint"
        if tpl_wpml:
            params["action_library"] = parse_action_library_from_wpml(tpl_wpml)
        return tpl_kml, tpl_wpml, points_ll, params

    polygon_ll = _extract_polygon_from_kml_root(root)
    if len(polygon_ll) < 3:
        raise ValueError(f"KMZ 中未找到有效多边形（至少需 3 个顶点）: {kmz_path}")
    params["input_type"] = "polygon"
    if tpl_wpml:
        params["action_library"] = parse_action_library_from_wpml(tpl_wpml)
    return tpl_kml, tpl_wpml, polygon_ll, params


def read_input(input_path: str) -> Tuple[bytes, Optional[bytes], List[Tuple[float, float]], dict]:
    """统一输入入口：根据文件扩展名或内容自动识别格式并解析。

    Args:
        input_path: 输入文件路径。

    Returns:
        (template_kml, template_wpml, polygon_ll, params) 四元组。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 无法识别格式或未找到有效多边形。
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(input_path)

    suf = path.suffix.lower()
    if suf == ".kmz":
        return read_kmz(input_path)
    if suf == ".kml":
        return read_kml(input_path)
    if suf == ".geojson":
        return read_geojson(input_path)
    if suf == ".json":
        return read_json_polygon(input_path)

    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    if text.lstrip().startswith("<?xml") or text.lstrip().startswith("<kml"):
        return read_kml(input_path)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if data.get("type") in ("Feature", "FeatureCollection", "Polygon", "MultiPolygon", "LineString"):
                return read_geojson(input_path)
            if "coordinates" in data or "polygon" in data or "points" in data:
                return read_json_polygon(input_path)
    except json.JSONDecodeError:
        pass
    raise ValueError(f"无法识别输入格式，请使用 .kmz / .kml / .geojson / .json 扩展名: {input_path}")
