# -*- coding: utf-8 -*-
# 自 drone_3d_path backend/app/utils/path_planner/path_editor_bridge.py 裁剪：
# 仅保留 route_3d → KMZ（export_generator_route_from_route3d_to_kmz + _export_kmz_common）。
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from uavplanner.generator_mission import build_generator_mission_params
from uavplanner.path_editor.io import read_input
from uavplanner.path_editor.output import build_minimal_template_kml, export_kmz
from uavplanner.path_editor.params import (
    merge_planning_params,
    parse_mission_config,
    parse_surface_follow_params,
)

logger_ = logging.getLogger(__name__)


def resolve_template_family_for_route(
    business_route_type: str, has_polygon: Optional[bool] = None
) -> str:
    """业务题型 → 模板结构族别（mapping2d / mapping3d / mappingPrism / waypoint）。"""
    _ = has_polygon
    rt = (business_route_type or "").strip().lower()
    if rt in {"polygon", "corridor", "facade"}:
        return "mapping2d"
    if rt == "cylinder":
        return "mappingPrism"
    if rt in {"close_photography"}:
        return "mapping3d"
    return "waypoint"


def resolve_template_type_for_route(
    business_route_type: str, has_polygon: Optional[bool] = None
) -> str:
    """业务题型 → 写回到 template.kml 的 DJI/WPML 标准 templateType。"""
    _ = has_polygon
    rt = (business_route_type or "").strip().lower()
    if rt == "cylinder":
        return "mappingPrism"
    if rt == "polygon":
        return "mapping2d"
    if rt == "facade":
        return "facade"
    if rt == "corridor":
        return "mappingStrip"
    if rt in {"close_photography"}:
        return "mapping3d"
    return "waypoint"


def _official_mission_defaults_for_route(business_route_type: str) -> Dict[str, Any]:
    """按官方司空样例提供非面状题型的 missionConfig 默认值。"""
    rt = (business_route_type or "").strip().lower()
    common: Dict[str, Any] = {
        "gsd": 0.01,
        "global_distance_m": 5.0,
        "min_flight_altitude_m": 2.0,
        "pointcloud_preprocess_enable": True,
        "waypoint_export_frame": "planning",
        "safety_distance": 3.0,
        "voxel_size": 1.0,
        "capture_interpolation_factor": 1.0,
        "tiles_kind": "auto",
        "tiles_max_points": 5_000_000,
        "tiles_lod_max": 3,
        "tiles_output_frame": "enu",
        "tiles_input_crs": "ecef",
        "transition_grid_resolution": 1.0,
        "transition_max_expansions": 30000,
        "transition_goal_tolerance": 2.0,
        "transition_waypoint_spacing": 4.0,
        "transition_enable_theta_star_fallback": True,
        "oblique_dst_srf": 5.0,
        "oblique_min_altitude": 2.0,
        "viewpoint_boundary_expand_m": 5.0,
        "viewpoint_min_points_per_layer": 4,
        "viewpoint_layer_order": "bottom_up",
        "viewpoint_min_altitude": 2.0,
        "viewpoint_beyond_altitude": 3.0,
        "viewpoint_layer_height_step_m": 3.3,
        "viewpoint_ring_arc_step_m": 10,
        "viewpoint_shape_use_full_points": True,
        "viewpoint_shape_method": "convex",
        "viewpoint_shape_roundness_m": 0.8,
        "viewpoint_alpha": 2.0,
        "viewpoint_layer_area_jump_ratio": 3.0,
        "viewpoint_layer_insert_max_global": 8,
        "focal_length_mm": 24.0,
        "sensor_width_mm": 36.0,
        "sensor_height_mm": 24.0,
        "resolution_x": 6000,
        "resolution_y": 4000,
        "take_off_security_height": 20.0,
        "global_transitional_speed": 15.0,
        "global_rth_height": 100.0,
        "drone_enum_value": 100,
        "drone_sub_enum_value": 1,
        "payload_enum_value": 89,
        "payload_sub_enum_value": 2,
        "payload_position_index": 0,
        "exit_on_rc_lost": "goContinue",
        "execute_rc_lost_action": "goBack",
    }
    if rt == "poly":
        return {
            **common,
            "fly_to_wayline_mode": "pointToPoint",
            "finish_action": "gotoFirstWaypoint",
            "wayline_avoid_limit_area_mode": 0,
        }
    if rt == "cylinder":
        return {
            **common,
            "fly_to_wayline_mode": "pointToPoint",
            "finish_action": "noAction",
            "wayline_avoid_limit_area_mode": 0,
        }
    if rt == "facade":
        return {
            **common,
            "fly_to_wayline_mode": "pointToPoint",
            "finish_action": "gotoFirstWaypoint",
            "wayline_avoid_limit_area_mode": 0,
        }
    if rt == "close_photography":
        return {
            **common,
            "fly_to_wayline_mode": "safely",
            "finish_action": "gotoFirstWaypoint",
            "wayline_avoid_limit_area_mode": 1,
            "auto_reroute_info": "",
        }
    return {}


def _parse_drone_model_key(drone_model_key: Any) -> Optional[Tuple[int, int]]:
    """解析 ``0-99-1`` 这类机型键，返回 ``(droneEnumValue, droneSubEnumValue)``。"""
    if drone_model_key is None:
        return None
    parts = [p.strip() for p in str(drone_model_key).split("-") if str(p).strip() != ""]
    if len(parts) < 3:
        return None
    try:
        return int(parts[-2]), int(parts[-1])
    except (TypeError, ValueError):
        return None


def _parse_payload_model_keys(payload_model_keys: Any) -> Optional[Dict[str, int]]:
    """解析 payload 信息，兼容 dict 与 ``1-89-0-0`` 这类存储字符串。"""
    if payload_model_keys is None:
        return None
    if isinstance(payload_model_keys, dict):
        try:
            return {
                "payload_enum_value": int(payload_model_keys["payloadEnumValue"]),
                "payload_sub_enum_value": int(payload_model_keys["payloadSubEnumValue"]),
                "payload_position_index": int(payload_model_keys["payloadPositionIndex"]),
            }
        except (KeyError, TypeError, ValueError):
            return None

    parts = [p.strip() for p in str(payload_model_keys).split("-") if str(p).strip() != ""]
    if len(parts) < 3:
        return None
    try:
        return {
            "payload_enum_value": int(parts[-3]),
            "payload_sub_enum_value": int(parts[-2]),
            "payload_position_index": int(parts[-1]),
        }
    except (TypeError, ValueError):
        return None


def _takeoff_ingress_pose_dict_for_kmz_export(merged: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 merge 结果构造写回 template.kml ExtendedData 的 takeoff_ingress_pose 对象。"""
    pose = merged.get("takeoff_ingress_pose")
    if isinstance(pose, dict):
        try:
            if pose.get("x") is None or pose.get("y") is None or pose.get("z") is None:
                return None
            out: Dict[str, Any] = {
                "x": float(pose["x"]),
                "y": float(pose["y"]),
                "z": float(pose["z"]),
            }
            if pose.get("heading_deg") is not None:
                out["heading_deg"] = float(pose["heading_deg"])
            return out
        except (TypeError, ValueError):
            return None
    tx, ty, tz = merged.get("takeoff_ingress_x"), merged.get("takeoff_ingress_y"), merged.get("takeoff_ingress_z")
    if tx is not None and ty is not None and tz is not None:
        try:
            out = {"x": float(tx), "y": float(ty), "z": float(tz)}
            th = merged.get("takeoff_ingress_heading_deg")
            if th is not None:
                out["heading_deg"] = float(th)
            return out
        except (TypeError, ValueError):
            return None
    return None


def _build_extra_planning_params_for_export(merged: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    keys = (
        "gsdCmPerPx",
        "irGsdCmPerPx",
        "startZ",
        "climbMode",
        "surveyTopAsl",
        "surveyBottomAsl",
        "sideFlightSpeed",
        "routeOrientation",
        "homeLl",
        "includeTopCap",
        "coverageYawOffset",
        "gsd_cm_per_px",
        "spacing",
        "use_camera",
        "camera_preset",
        "optimize_path",
        "with_timestamps",
        "start_ll",
        "end_ll",
        "reference_time",
        "ortho_capture_enabled",
        "oblique_capture_enabled",
    )
    out: Dict[str, Any] = {k: merged.get(k) for k in keys if merged.get(k) is not None}
    tip = _takeoff_ingress_pose_dict_for_kmz_export(merged)
    if tip is not None:
        out["takeoff_ingress_pose"] = tip
    return out if out else None


def _export_kmz_common(
    business_route_type: str,
    req_params: Dict[str, Any],
    polygon_ll: List[List[float]],
    waypoints: List[Tuple[float, float, float]],
    segment_start_indices: List[int],
    polygon_vertex_count: Optional[int],
    kmz_output_path: Path,
    *,
    template_vertices_llh: Optional[List[Tuple[float, float, float]]] = None,
    template_prism_height: Optional[float] = None,
    waypoint_wpml_attrs: Optional[List[Optional[Dict[str, Any]]]] = None,
    wpml_export_source: Optional[str] = None,
) -> None:
    """解析输入模板参数并按算法结果构造输出 KMZ。"""
    raw_params: Dict[str, Any] = {}
    template_wpml = None
    input_path = req_params.get("input_path")
    patch_template_kml = True
    if input_path:
        _template_kml, _template_wpml, _coords_ll, raw_params = read_input(str(input_path))
        patch_template_kml = Path(str(input_path)).suffix.lower() != ".kmz"

    merged = merge_planning_params(kmz_params=raw_params, cli_params=req_params)
    template_type_tag = resolve_template_type_for_route(business_route_type)
    template_family = resolve_template_family_for_route(business_route_type)
    height = float(merged.get("height", 100.0))
    auto_sp = merged.get("flight_speed")
    if auto_sp is None:
        auto_sp = merged.get("auto_speed")
    if auto_sp is None:
        auto_sp = 10.0
    auto_sp = float(auto_sp)
    poly = [(float(p[0]), float(p[1])) for p in polygon_ll]
    direction = float(merged.get("direction", 0.0))
    gimbal = merged.get("camera_pitch")
    if gimbal is not None:
        gimbal_f = float(gimbal)
    else:
        gimbal_f = -45.0 if template_family == "mapping3d" else None
    ol = merged.get("overlap_lateral")
    olo = merged.get("overlap_longitudinal")
    oli = merged.get("overlap_lateral_inclined")
    oloi = merged.get("overlap_longitudinal_inclined")
    ortho_w = int(round(float(ol) * 100)) if ol is not None else 80
    ortho_h = int(round(float(olo) * 100)) if olo is not None else 80
    inc_w = int(round(float(oli if oli is not None else ol) * 100)) if (oli is not None or ol is not None) else 70
    inc_h = int(round(float(oloi if oloi is not None else olo) * 100)) if (oloi is not None or olo is not None) else 80

    if template_family == "mapping3d":
        template_kml = build_minimal_template_kml(
            poly,
            height=height,
            direction=direction,
            template_type="mapping3d",
            template_type_tag=template_type_tag,
            placemark_profile=business_route_type,
            template_vertices_llh=template_vertices_llh,
            template_prism_height=template_prism_height,
            inclined_gimbal_pitch=gimbal_f,
            inclined_flight_speed=auto_sp,
            auto_flight_speed=auto_sp,
            overlap_ortho_h=ortho_h,
            overlap_ortho_w=ortho_w,
            overlap_inclined_h=inc_h,
            overlap_inclined_w=inc_w,
        )
    else:
        template_kml = build_minimal_template_kml(
            poly,
            height=height,
            direction=direction,
            template_type=template_family,
            template_type_tag=template_type_tag,
            placemark_profile=business_route_type,
            template_vertices_llh=template_vertices_llh,
            template_prism_height=template_prism_height,
            auto_flight_speed=auto_sp,
        )
    surf_dict = merged.get("surface_follow") or raw_params.get("surface_follow")
    surface_follow = parse_surface_follow_params(surf_dict) if surf_dict else None
    action_template_id = merged.get("action_template_id") or "photo_45"

    auto_speed = merged.get("flight_speed")
    if auto_speed is None:
        auto_speed = merged.get("auto_speed")
    if auto_speed is None:
        auto_speed = raw_params.get("auto_speed")
    if auto_speed is None:
        auto_speed = 10.0

    mission_cfg_dict = dict(_official_mission_defaults_for_route(business_route_type))
    mission_cfg_dict.update(raw_params.get("mission_config") or {})
    if "take_off_security_height" in req_params:
        mission_cfg_dict["take_off_security_height"] = req_params.get("take_off_security_height")
    if "finish_action" in req_params:
        mission_cfg_dict["finish_action"] = req_params.get("finish_action")
    if "global_transitional_speed" in req_params:
        mission_cfg_dict["global_transitional_speed"] = req_params.get("global_transitional_speed")
    if "global_rth_height" in req_params:
        mission_cfg_dict["global_rth_height"] = req_params.get("global_rth_height")

    drone_model = _parse_drone_model_key(
        req_params.get("drone_model_key", raw_params.get("drone_model_key"))
    )
    if drone_model is not None:
        mission_cfg_dict["drone_enum_value"] = drone_model[0]
        mission_cfg_dict["drone_sub_enum_value"] = drone_model[1]

    payload_info = _parse_payload_model_keys(
        req_params.get("payload_model_keys", raw_params.get("payload_model_keys"))
    )
    if payload_info is not None:
        mission_cfg_dict.update(payload_info)

    mission_config = parse_mission_config(mission_cfg_dict) if mission_cfg_dict else None
    if mission_config is not None and mission_config.take_off_ref_point is None:
        if waypoints:
            lon0, lat0, alt0 = waypoints[0]
            mission_config = mission_config.with_take_off_ref_point(float(lat0), float(lon0), float(alt0))
        elif polygon_ll:
            lon0, lat0 = float(polygon_ll[0][0]), float(polygon_ll[0][1])
            mission_config = mission_config.with_take_off_ref_point(
                float(lat0),
                float(lon0),
                float(merged.get("height") if merged.get("height") is not None else 100.0),
            )

    template_height_mode_wpml: Optional[str] = None
    hm = (merged.get("height_mode") or "").strip()
    ex = (merged.get("execute_height_mode") or "").strip()
    if (
        template_family == "mapping3d"
        and not hm
        and not ex
        and not (surface_follow and surface_follow.surface_follow_enable)
    ):
        template_height_mode_wpml = "relativeToStartPoint"

    heading_mode_for_export = merged.get("heading_mode")
    if waypoint_wpml_attrs and any(
        isinstance(a, dict) and a.get("heading_deg") is not None for a in waypoint_wpml_attrs
    ):
        hm2 = str(heading_mode_for_export or "").strip().lower()
        if hm2 in ("", "followwayline"):
            heading_mode_for_export = "fixed"

    export_kmz(
        out_path=str(kmz_output_path),
        template_kml=template_kml,
        template_wpml=template_wpml,
        waypoints=waypoints,
        height=height,
        auto_speed=float(auto_speed),
        action_library=raw_params.get("action_library"),
        segment_start_indices=segment_start_indices,
        action_template_id=action_template_id,
        mission_config=mission_config,
        overlap_lateral=merged.get("overlap_lateral"),
        overlap_longitudinal=merged.get("overlap_longitudinal"),
        overlap_lateral_inclined=merged.get("overlap_lateral_inclined"),
        overlap_longitudinal_inclined=merged.get("overlap_longitudinal_inclined"),
        margin=merged.get("margin"),
        direction=(
            merged.get("direction")
            if merged.get("direction") is not None
            else raw_params.get("direction")
        ),
        height_mode=merged.get("height_mode"),
        execute_height_mode=merged.get("execute_height_mode"),
        surface_follow=surface_follow,
        capture_mode=merged.get("capture_mode"),
        gimbal_pitch=(
            merged.get("camera_pitch")
            if merged.get("camera_pitch") is not None
            else raw_params.get("camera_pitch")
        ),
        heading_mode=heading_mode_for_export,
        heading_angle=merged.get("heading_angle"),
        polygon_vertex_count=polygon_vertex_count,
        extra_planning_params=_build_extra_planning_params_for_export(merged),
        template_height_mode_wpml=template_height_mode_wpml,
        template_type_tag=template_type_tag,
        patch_template_kml=patch_template_kml,
        waypoint_wpml_attrs=waypoint_wpml_attrs,
        wpml_export_source=wpml_export_source,
    )


def _waypoints_llh_from_route3d(route_3d: Dict[str, Any]) -> List[Tuple[float, float, float]]:
    raw = route_3d.get("waypoints_wgs84")
    if not isinstance(raw, list) or not raw:
        raise ValueError("route_3d.waypoints_wgs84 须为非空数组")
    out: List[Tuple[float, float, float]] = []
    for idx, p in enumerate(raw):
        if isinstance(p, dict):
            lon = p.get("lng", p.get("lon"))
            lat = p.get("lat")
            alt = p.get("alt", p.get("height", p.get("elevation", 0.0)))
            if lon is None or lat is None:
                raise ValueError(f"route_3d.waypoints_wgs84[{idx}] 缺少 lng/lon 或 lat")
            out.append((float(lon), float(lat), float(alt)))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            lon_f, lat_f = float(p[0]), float(p[1])
            alt_f = float(p[2]) if len(p) >= 3 else 0.0
            out.append((lon_f, lat_f, alt_f))
        else:
            raise ValueError(f"route_3d.waypoints_wgs84[{idx}] 格式无效")
    return out


def _segment_start_indices_from_route3d(route_3d: Dict[str, Any], n: int) -> List[int]:
    segs = route_3d.get("segments")
    if not isinstance(segs, list) or not segs:
        return [0]
    starts: List[int] = []
    for s in segs:
        if not isinstance(s, dict) or "start" not in s:
            continue
        try:
            si = int(s["start"])
        except (TypeError, ValueError):
            continue
        if 0 <= si < n:
            starts.append(si)
    if not starts:
        return [0]
    uniq = sorted(set(starts))
    if uniq[0] != 0:
        uniq = sorted(set([0] + uniq))
    return uniq


def export_generator_route_from_route3d_to_kmz(
    business_route_type: str,
    polygon_ll: List[List[float]],
    params: Dict[str, Any],
    route_3d: Dict[str, Any],
    kmz_output_path: Path,
) -> Dict[str, Any]:
    """与 calculate-area 相同的 options 合同 + ``route_3d.waypoints_wgs84`` → KMZ。"""
    req_params = dict(params or {})
    if req_params.get("height_mode") in (None, "") and req_params.get("execute_height_mode") in (None, ""):
        req_params["execute_height_mode"] = "relativeToStartPoint"
    mission = build_generator_mission_params(business_route_type, polygon_ll, req_params)
    for _tk in ("takeoff_ingress_x", "takeoff_ingress_y", "takeoff_ingress_z", "takeoff_ingress_heading_deg"):
        if mission.get(_tk) is not None:
            req_params[_tk] = mission[_tk]
    waypoints_ll = _waypoints_llh_from_route3d(route_3d)
    n = len(waypoints_ll)
    seg_idx = _segment_start_indices_from_route3d(route_3d, n)
    pvc_raw = route_3d.get("polygon_vertex_count")
    if pvc_raw is None and polygon_ll:
        nn = len(polygon_ll)
        if nn >= 2 and len(polygon_ll[0]) >= 2 and len(polygon_ll[-1]) >= 2:
            same = float(polygon_ll[0][0]) == float(polygon_ll[-1][0]) and float(polygon_ll[0][1]) == float(
                polygon_ll[-1][1]
            )
            pvc_raw = (nn - 1) if same else nn
        else:
            pvc_raw = nn
    try:
        pvc_i = int(pvc_raw) if pvc_raw is not None else None
    except (TypeError, ValueError):
        pvc_i = None

    wpml_attrs = route_3d.get("waypoint_wpml_attrs")
    if not isinstance(wpml_attrs, list):
        wpml_attrs = None
    elif len(wpml_attrs) != n:
        logger_.warning(
            "export-kmz: waypoint_wpml_attrs 与航点条数不一致（%s vs %s），忽略逐点姿态",
            len(wpml_attrs),
            n,
        )
        wpml_attrs = None

    _export_kmz_common(
        business_route_type,
        req_params,
        polygon_ll,
        waypoints_ll,
        seg_idx,
        pvc_i,
        kmz_output_path,
        template_vertices_llh=mission.get("template_vertices_llh"),
        template_prism_height=mission.get("template_prism_height"),
        waypoint_wpml_attrs=wpml_attrs,
        wpml_export_source="export-kmz",
    )
    out_route = dict(route_3d)
    out_route["waypoints_wgs84"] = [[float(a), float(b), float(c)] for a, b, c in waypoints_ll]
    return {
        "kmz_path": str(kmz_output_path),
        "count": n,
        "distance": None,
        "duration": None,
        "route_3d": out_route,
    }
