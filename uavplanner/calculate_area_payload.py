# -*- coding: utf-8 -*-
# 自 drone_3d_path backend/app/views/waylines.py 抽取：calculate-area / export-kmz 请求体解析与 options 归一化。
# 不含 Flask、不含 Model3D；模型绑定路径解析通过可选回调注入。
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from uavplanner.contracts.calculate_area_contract import (
    sanitize_geometry_ui_options as _sanitize_geometry_ui_options,
)


def public_calculate_error_message(message: str) -> str:
    """对用户可见错误文案中的内部字段名做温和替换（与 waylines 一致）。"""
    return (
        str(message or "")
        .replace("side_overlap", "overlap_lateral")
        .replace("front_overlap", "overlap_longitudinal")
    )


def ratio_01_from_calculate_ui(val: Any) -> Optional[float]:
    """将 UI 重叠率/覆盖率转为 0~1；支持 0~1 小数或 1~100 百分数。"""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if f > 1.0 and f <= 100.0:
        f /= 100.0
    return f


def apply_calculate_options_value_normalization(out: Dict[str, Any]) -> None:
    """calculate-area：统一重叠率、GSD(cm/px)、速度回退与 climb 别名（单一归一化入口）。"""
    for key in ("overlap_lateral", "overlap_longitudinal"):
        if key not in out or out[key] is None:
            continue
        nv = ratio_01_from_calculate_ui(out[key])
        if nv is not None and 0.0 <= nv <= 1.0:
            out[key] = nv
    if out.get("coverage_ratio") is not None:
        nv = ratio_01_from_calculate_ui(out["coverage_ratio"])
        if nv is not None and 0.0 <= nv <= 1.0:
            out["coverage_ratio"] = nv
    if out.get("gsd_cm_per_px") is None and out.get("gsd") is not None:
        try:
            g = float(out["gsd"])
            if g > 0:
                out["gsd_cm_per_px"] = g
        except (TypeError, ValueError):
            pass
    out.pop("gsd", None)
    if (
        out.get("flight_speed") is None
        and out.get("auto_speed") is None
        and out.get("speed_ms") is None
        and out.get("side_flight_speed") is not None
    ):
        try:
            out["flight_speed"] = float(out["side_flight_speed"])
        except (TypeError, ValueError):
            pass
    if out.get("vertical_climb_mode") is None and out.get("climb_mode") is not None:
        out["vertical_climb_mode"] = out["climb_mode"]
    if out.get("payload_lens_index") is not None:
        out.pop("payloadLensIndex", None)


def normalize_calculate_options(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out = dict(raw)
    alias_map = {
        "routeType": "route_type",
        "surfaceFollow": "surface_follow",
        "cameraPitch": "camera_pitch",
        "flightSpeed": "flight_speed",
        "autoFlightSpeed": "flight_speed",
        "autoSpeed": "auto_speed",
        "speedMs": "speed_ms",
        "globalFlightSpeed": "global_flight_speed",
        "mainRouteSpeed": "main_route_speed",
        "gsdCmPerPx": "gsd_cm_per_px",
        "useCamera": "use_camera",
        "cameraPreset": "camera_preset",
        "optimizePath": "optimize_path",
        "orthoCaptureEnabled": "ortho_capture_enabled",
        "obliqueCaptureEnabled": "oblique_capture_enabled",
        "overlapLateral": "overlap_lateral",
        "overlapLongitudinal": "overlap_longitudinal",
        "overlapLateralInclined": "overlap_lateral_inclined",
        "overlapLongitudinalInclined": "overlap_longitudinal_inclined",
        "takeOffSecurityHeight": "take_off_security_height",
        "heightMode": "height_mode",
        "executeHeightMode": "execute_height_mode",
        "execute_heightMode": "execute_height_mode",
        "executeheightMode": "execute_height_mode",
        "finishAction": "finish_action",
        "globalTransitionalSpeed": "global_transitional_speed",
        "globalRTHHeight": "global_rth_height",
        "useEnuRegionCoordinates": "use_enu_region_coordinates",
        "regionGroundZ": "region_ground_z",
        "pointCloudPath": "pointcloud_path",
        "tilesetPath": "tileset_path",
        "inputPath": "input_path",
        "globalDistanceM": "global_distance_m",
        "standoffDistance": "standoff_distance",
        "pathGenerator": "path_generator",
        "missionConfig": "mission_config",
        "droneModel": "drone_model_key",
        "droneModelKey": "drone_model_key",
        "payloadInfo": "payload_model_keys",
        "payloadModelKeys": "payload_model_keys",
        "modelFileId": "model_file_id",
        "modelId": "model_id",
        "captureMode": "capture_mode",
        "headingMode": "heading_mode",
        "headingAngle": "heading_angle",
        "actionTemplateId": "action_template_id",
        "surveyTopAsl": "survey_top_asl",
        "surveyBottomAsl": "survey_bottom_asl",
        "sideFlightSpeed": "side_flight_speed",
        "routeOrientation": "route_orientation",
        "includeTopCap": "include_top_cap",
        "coverageYawOffset": "coverage_yaw_offset",
        "sweepYawOffset": "sweep_yaw_offset",
        "geometryMode": "geometry_mode",
        "pointsPerRev": "points_per_rev",
        "flightHeight": "flight_height",
        "appendCentroid": "append_centroid",
        "irGsd": "ir_gsd",
        "startZ": "start_z",
        "verticalClimbMode": "vertical_climb_mode",
        "obliqueClimbMode": "oblique_climb_mode",
        "coverageRatio": "coverage_ratio",
        "startAzimuthDeg": "start_azimuth_deg",
        "payloadLensIndex": "payload_lens_index",
        "takeoffIngressPose": "takeoff_ingress_pose",
    }
    for src, dst in alias_map.items():
        if src in out and dst not in out and out.get(src) is not None:
            out[dst] = out.get(src)
    apply_calculate_options_value_normalization(out)
    return out


def reject_deprecated_calculate_options(options: Dict[str, Any]) -> None:
    if not isinstance(options, dict):
        return
    if options.get("debug_export_mode") is not None or options.get("debugExportMode") is not None:
        raise ValueError(
            "options.debug_export_mode 已弃用；calculate-area 已恢复原导出链路，不再支持 waypoint 调试导出"
        )


def normalize_calculate_route_type(raw_route_type: Any, options: Dict[str, Any]) -> str:
    rt = str(raw_route_type or "").strip().lower()
    route_alias_map = {
        "mapping_2d": "polygon",
        "mapping2d": "polygon",
        "mapping_strip": "corridor",
        "mappingstrip": "corridor",
        "clinder": "cylinder",
        "geo_cylinder": "cylinder",
        "cylinder route": "cylinder",
        "cylinder-route": "cylinder",
        "cylinder_route": "cylinder",
        "plane3d": "facade",
        "close_up_photo": "close_photography",
    }
    if rt == "mapping3d":
        sf = options.get("surface_follow")
        if isinstance(sf, dict) and sf.get("surface_follow_enable"):
            return "close_photography"
        return "facade"
    return route_alias_map.get(rt, rt)


def extract_calculate_payload(jdata: Dict[str, Any]) -> Tuple[str, List[Any], Dict[str, Any]]:
    """与 waylines.calculate-area / export-kmz 相同的顶层 JSON 解析。"""
    if isinstance(jdata.get("features"), list) and jdata.get("features"):
        feature = jdata["features"][0] or {}
        props = normalize_calculate_options(feature.get("properties") or {})
        reject_deprecated_calculate_options(props)
        geom = feature.get("geometry") or {}
        route_type = normalize_calculate_route_type(
            props.get("route_type") or props.get("routeType") or props.get("type"),
            props,
        )
        return route_type, geom.get("coordinates") or [], _sanitize_geometry_ui_options(route_type, props)

    options = normalize_calculate_options(jdata.get("options") or {})
    reject_deprecated_calculate_options(options)
    route_type = normalize_calculate_route_type(
        jdata.get("route_type") or jdata.get("routeType") or jdata.get("type"),
        options,
    )
    return route_type, jdata.get("coordinates") or [], _sanitize_geometry_ui_options(route_type, options)


def lon_lat_list_from_coordinates(coordinates: Any) -> List[List[float]]:
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("coordinates 不能为空")

    if (
        isinstance(coordinates[0], list)
        and coordinates[0]
        and isinstance(coordinates[0][0], (list, tuple))
    ):
        coordinates = coordinates[0]

    coordinate_list: List[List[float]] = []
    for coordinate in coordinates:
        if isinstance(coordinate, dict):
            lng = coordinate.get("lng")
            lat = coordinate.get("lat")
            alt = coordinate.get("alt")
            if alt is None:
                alt = coordinate.get("height")
            if alt is None:
                alt = coordinate.get("elevation")
        elif isinstance(coordinate, (list, tuple)) and len(coordinate) >= 2:
            lng = coordinate[0]
            lat = coordinate[1]
            alt = coordinate[2] if len(coordinate) >= 3 else None
        else:
            continue
        point = [float(lng), float(lat)]
        if alt is not None:
            point.append(float(alt))
        coordinate_list.append(point)

    if len(coordinate_list) < 2:
        raise ValueError("缺少有效坐标")
    return coordinate_list


def is_placeholder_tileset_path(value: Any) -> bool:
    if value is None:
        return False
    path_str = str(value).strip()
    if path_str == "":
        return False
    lower = path_str.lower()
    return (
        lower.startswith("/abs/path/")
        or lower.startswith("c:/abs/path/")
        or lower.startswith("c:\\abs\\path\\")
        or "{tileset" in lower
        or "<tileset" in lower
    )


def resolve_existing_tileset_path(options: Dict[str, Any]) -> Optional[str]:
    for key in (
        "pointcloud_path",
        "point_cloud_path",
        "tileset_path",
        "tilesetPath",
        "input_path",
        "inputPath",
    ):
        value = options.get(key)
        if value is None:
            continue
        path_str = str(value).strip()
        if path_str:
            return path_str
    return None


def route_allows_geometry_only_without_model(route_type: str, options: Dict[str, Any]) -> bool:
    _ = options
    rt = str(route_type or "").strip().lower()
    if rt in ("polygon", "facade", "close_photography"):
        return True
    if rt == "cylinder":
        return False
    return False


ResolveModelLocalPath = Callable[[int], str]
"""``model_file_id`` → 本地可读 tileset/点云路径（调用方负责下载/解析 DB）。"""


def resolve_tileset_path_from_model_id(
    route_type: str,
    options: Dict[str, Any],
    *,
    resolve_model_local_path: Optional[ResolveModelLocalPath] = None,
) -> Dict[str, Any]:
    """合并 ``pointcloud_path``：先认 options 内已有路径；否则在有 ``model_id`` 且提供回调时解析。

    与 waylines 行为一致，但 **不** 依赖 SQLAlchemy / Storage：由 ``resolve_model_local_path`` 注入。
    当存在 ``model_file_id`` 且非「纯几何可绕过」、且未提供回调时，抛出 ``ValueError``。
    """
    if not isinstance(options, dict):
        return {}

    out = dict(options)
    allow_geometry_only = route_allows_geometry_only_without_model(route_type, out)
    existing_path = resolve_existing_tileset_path(out)
    if existing_path and not is_placeholder_tileset_path(existing_path):
        existing_file = Path(existing_path).expanduser()
        if existing_file.is_file():
            out["pointcloud_path"] = str(existing_file)
            return out
        return out

    model_file_id = (
        out.get("model_file_id")
        or out.get("model_id")
        or out.get("modelFileId")
        or out.get("modelId")
    )
    if model_file_id in (None, ""):
        return out

    try:
        model_file_id_int = int(model_file_id)
    except (TypeError, ValueError):
        if allow_geometry_only:
            return out
        raise ValueError(f"绑定模型不存在: {model_file_id}") from None

    if resolve_model_local_path is None:
        if allow_geometry_only:
            return out
        raise ValueError(
            "options 含 model_id/model_file_id 但未解析到本地 tileset；"
            "对本 route_type 须提供 resolve_model_local_path(model_id) -> 本地路径"
        )

    try:
        local_path = resolve_model_local_path(model_file_id_int)
    except Exception as e:
        if allow_geometry_only:
            return out
        raise ValueError(f"绑定模型文件解析失败: {model_file_id}, {str(e)}") from e

    if not local_path or not Path(str(local_path)).is_file():
        if allow_geometry_only:
            return out
        raise ValueError(f"绑定模型缺少可读本地文件: {model_file_id}")

    out["pointcloud_path"] = str(local_path)
    return out
