# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: calculate-area 几何体合同 — 白名单、sanitize、path_generator 过滤、点云默认
# ------------------------------------------------------------ #
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

# 与 waylines 原 GENERATOR_FIRST_ROUTE_TYPES 一致；供 sanitize 与路由判断共用。
GENERATOR_FIRST_ROUTE_TYPES = frozenset({"polygon", "cylinder", "close_photography", "facade"})

GEOMETRY_UI_OPTION_KEYS_COMMON = frozenset(
    {
        "height",
        "altitude",
        "flight_speed",
        "auto_speed",
        "speed_ms",
        "camera_pitch",
        "overlap_lateral",
        "overlap_longitudinal",
        "overlap_lateral_inclined",
        "overlap_longitudinal_inclined",
        "take_off_security_height",
        "height_mode",
        "execute_height_mode",
        "finish_action",
        "global_transitional_speed",
        "global_rth_height",
        "surface_follow",
        "use_enu_region_coordinates",
        "region_ground_z",
        "direction",
        "drone_model_key",
        "payload_model_keys",
        "model_file_id",
        "model_id",
        "pointcloud_path",
        "point_cloud_path",
        "tileset_path",
        "input_path",
        "capture_mode",
        "heading_mode",
        "heading_angle",
        "action_template_id",
        "gsd_cm_per_px",
        "camera_param",
        "camera_preset",
        "use_camera",
        "kml_json",
        "input_kml_json",
        "template_kml_json",
        "global_distance_m",
        "standoff_distance",
        "payloadLensIndex",
        "gsd",
        "ir_gsd",
        "start_z",
        "climb_mode",
        "survey_top_asl",
        "survey_bottom_asl",
        "side_flight_speed",
        "route_orientation",
        "home_ll",
        "include_top_cap",
        "coverage_yaw_offset",
        "geometry_mode",
        "pitch",
        "points_per_rev",
        "flight_height",
        "append_centroid",
        "with_timestamps",
        "reference_time",
        "vertical_climb_mode",
        "oblique_climb_mode",
        "coverage_ratio",
        "sweep_yaw_offset",
        "start_azimuth_deg",
        "payload_lens_index",
        "path_generator",
        "mission_config",
        # path_generator MissionConfig：点云裁剪与 tileset ENU 原点（与 api._coerce_field 对齐）
        "aabb_center",
        "aabb_size",
        "aabb_yaw_deg",
        "aabb_transform",
        "tiles_enu_origin_ecef",
        "tiles_bbox",
        "tiles_output_frame",
        "tiles_input_crs",
        "tiles_convert_coord_frame",
        "region_only_enabled",
        "data_source_type",
        # 起飞 ingress：与 path_generator 航迹同一规划帧（options / path_generator 内均可传）
        "takeoff_ingress_pose",
        "takeoffIngressPose",
        "takeoff_ingress_x",
        "takeoff_ingress_y",
        "takeoff_ingress_z",
        "takeoff_ingress_heading_deg",
    }
)

GEOMETRY_UI_OPTION_KEYS_BY_ROUTE: Dict[str, FrozenSet[str]] = {
    "cylinder": frozenset(),
    "facade": frozenset({"direction"}),
    "close_photography": frozenset({"surface_follow"}),
}

LEGACY_CYLINDER_DISCARD_KEYS = frozenset({"center_ll", "radius"})

_COVERAGE_MISSION_MERGE_KEYS: Optional[FrozenSet[str]] = None

# bridge / generator 侧进入 path_generator 的 mission 上、但不在 uav_planners.MissionConfig dataclass 中的键
_COVERAGE_MISSION_NON_DATACLASS_KEYS = frozenset(
    {
        "template_vertices_llh",
        "template_prism_height",
        "facade_plane_origin_enu",
        "facade_plane_along_unit_enu",
        "facade_plane_up_unit_enu",
        "facade_plane_normal_unit_enu",
    }
)


# 与 uav_planners.core.mission_config.MissionConfig 字段名对齐（本包不依赖 path_generator）。
_MISSION_CONFIG_FIELD_NAMES: FrozenSet[str] = frozenset(
    {
        "aabb_center",
        "aabb_size",
        "aabb_transform",
        "aabb_yaw_deg",
        "algorithm",
        "altitude",
        "camera",
        "capture_interpolation_factor",
        "coverage_area_polygon_xy",
        "coverage_area_rect_xy",
        "coverage_threshold",
        "data_source_type",
        "facade_plane_along_unit_enu",
        "facade_plane_height",
        "facade_plane_normal_unit_enu",
        "facade_plane_origin_enu",
        "facade_plane_up_unit_enu",
        "facade_plane_width",
        "facade_scan_gimbal_pitch_deg",
        "front_overlap",
        "global_distance_m",
        "gsd",
        "min_flight_altitude_m",
        "oblique_dst_srf",
        "oblique_min_altitude",
        "output_dir",
        "pointcloud_path",
        "pointcloud_preprocess_enable",
        "region_ground_z",
        "region_horizontal_frame",
        "region_only_enabled",
        "safety_distance",
        "side_overlap",
        "speed_ms",
        "takeoff_ingress_heading_deg",
        "takeoff_ingress_x",
        "takeoff_ingress_y",
        "takeoff_ingress_z",
        "template_base_vertices_enu",
        "template_prism_height",
        "template_top_vertices_enu",
        "tiles_bbox",
        "tiles_convert_coord_frame",
        "tiles_convert_to_ply",
        "tiles_convert_write_ascii",
        "tiles_converted_ply_path",
        "tiles_enu_origin_ecef",
        "tiles_input_crs",
        "tiles_kind",
        "tiles_lod_max",
        "tiles_max_points",
        "tiles_output_frame",
        "tileset_path",
        "transition_enable_theta_star_fallback",
        "transition_goal_tolerance",
        "transition_grid_resolution",
        "transition_lateral_max_candidates",
        "transition_lateral_offset_max_m",
        "transition_lateral_offset_min_m",
        "transition_lateral_offset_step_m",
        "transition_lateral_turn_penalty_weight",
        "transition_max_expansions",
        "transition_prefer_lateral_before_altitude",
        "transition_waypoint_spacing",
        "viewpoint_alpha",
        "viewpoint_beyond_altitude",
        "viewpoint_boundary_expand_m",
        "viewpoint_hull_roundness_m",
        "viewpoint_hull_use_full_points",
        "viewpoint_layer_area_jump_ratio",
        "viewpoint_layer_height_step_m",
        "viewpoint_layer_insert_max_global",
        "viewpoint_layer_order",
        "viewpoint_min_altitude",
        "viewpoint_min_points_per_layer",
        "viewpoint_ring_arc_step_m",
        "viewpoint_shape_method",
        "viewpoint_shape_roundness_m",
        "viewpoint_shape_use_full_points",
        "voxel_size",
        "waypoint_export_frame",
    }
)


def get_coverage_mission_merge_keys() -> FrozenSet[str]:
    """uav_planners.MissionConfig 字段名 + 桥接用扩展键（静态快照，避免依赖 path_generator）。"""
    global _COVERAGE_MISSION_MERGE_KEYS
    if _COVERAGE_MISSION_MERGE_KEYS is None:
        _COVERAGE_MISSION_MERGE_KEYS = _MISSION_CONFIG_FIELD_NAMES | _COVERAGE_MISSION_NON_DATACLASS_KEYS
    return _COVERAGE_MISSION_MERGE_KEYS


def filter_path_generator_nested(nested: Dict[str, Any]) -> Dict[str, Any]:
    """path_generator 嵌套对象仅保留 MissionConfig 可消费键，丢弃未知键。"""
    allowed = get_coverage_mission_merge_keys()
    return {str(k): v for k, v in nested.items() if str(k) in allowed}


def sanitize_geometry_ui_options(route_type: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """几何体 calculate-area 只接受 UI 合同字段，丢弃底层实现细节键。"""
    if not isinstance(options, dict):
        return {}
    rt = str(route_type or "").strip().lower()
    if rt not in GENERATOR_FIRST_ROUTE_TYPES:
        return dict(options)
    allowed = GEOMETRY_UI_OPTION_KEYS_COMMON | GEOMETRY_UI_OPTION_KEYS_BY_ROUTE.get(rt, frozenset())
    sanitized = {k: v for k, v in options.items() if k in allowed and v is not None}
    if rt == "cylinder":
        for legacy_key in LEGACY_CYLINDER_DISCARD_KEYS:
            sanitized.pop(legacy_key, None)
    return sanitized


def apply_pointcloud_mission_defaults(mission: Dict[str, Any]) -> None:
    """点云 / 倾斜 / 环绕类算法缺失键时 setdefault（不覆盖已有值）。

    规则对齐《航线工程化收敛计划》阶段 0：仅当算法为点云族且非「纯 region-only 无点云」时补齐。
    """
    algo = str(mission.get("algorithm", "")).strip().lower()
    region_only = bool(mission.get("region_only_enabled"))
    pc = mission.get("pointcloud_path") or mission.get("tileset_path")
    if algo not in ("oblique", "spiral", "viewpoint_optimized", "viewpoint_wrap"):
        return
    if region_only and not pc:
        return

    mission.setdefault("gsd", 0.01)
    mission.setdefault("global_distance_m", 5.0)
    mission.setdefault("min_flight_altitude_m", 2.0)
    mission.setdefault("pointcloud_preprocess_enable", True)
    mission.setdefault("waypoint_export_frame", "planning")
    mission.setdefault("safety_distance", 3.0)
    mission.setdefault("voxel_size", 1.0)
    mission.setdefault("capture_interpolation_factor", 1.0)

    mission.setdefault("tiles_kind", "auto")
    mission.setdefault("tiles_max_points", 5000000)
    mission.setdefault("tiles_lod_max", 3)
    mission.setdefault("tiles_output_frame", "enu")
    mission.setdefault("tiles_input_crs", "ecef")

    mission.setdefault("transition_grid_resolution", 1.0)
    mission.setdefault("transition_max_expansions", 30000)
    mission.setdefault("transition_goal_tolerance", 2.0)
    mission.setdefault("transition_waypoint_spacing", 4.0)
    mission.setdefault("transition_enable_theta_star_fallback", True)

    gd = mission.get("global_distance_m")
    if gd is not None:
        mission.setdefault("oblique_dst_srf", float(gd))
    else:
        mission.setdefault("oblique_dst_srf", 5.0)
    mfa = mission.get("min_flight_altitude_m")
    if mfa is not None:
        mission.setdefault("oblique_min_altitude", float(mfa))
    else:
        mission.setdefault("oblique_min_altitude", 2.0)

    if algo in ("viewpoint_optimized", "viewpoint_wrap"):
        gdm = float(mission.get("global_distance_m", 5.0))
        mission.setdefault("viewpoint_boundary_expand_m", gdm)
        mission.setdefault("viewpoint_min_points_per_layer", 4)
        mission.setdefault("viewpoint_layer_order", "bottom_up")
        if mfa is not None:
            mission.setdefault("viewpoint_min_altitude", float(mfa))
        else:
            mission.setdefault("viewpoint_min_altitude", 2.0)
        mission.setdefault("viewpoint_beyond_altitude", 3.0)
        mission.setdefault("viewpoint_layer_height_step_m", 3.3)
        mission.setdefault("viewpoint_ring_arc_step_m", 10)
        mission.setdefault("viewpoint_shape_use_full_points", True)
        mission.setdefault("viewpoint_shape_method", "convex")
        mission.setdefault("viewpoint_shape_roundness_m", 0.8)
        mission.setdefault("viewpoint_alpha", 2.0)
        mission.setdefault("viewpoint_layer_area_jump_ratio", 3.0)
        mission.setdefault("viewpoint_layer_insert_max_global", 8)

    cam = mission.get("camera")
    if isinstance(cam, dict):
        cam.setdefault("focal_length_mm", 24.0)
        cam.setdefault("sensor_width_mm", 36.0)
        cam.setdefault("sensor_height_mm", 24.0)
        cam.setdefault("resolution_x", 6000)
        cam.setdefault("resolution_y", 4000)
    elif cam is None:
        mission.setdefault(
            "camera",
            {
                "focal_length_mm": 24.0,
                "sensor_width_mm": 36.0,
                "sensor_height_mm": 24.0,
                "resolution_x": 6000,
                "resolution_y": 4000,
            },
        )
