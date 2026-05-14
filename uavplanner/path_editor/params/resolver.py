# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 规划参数解析层 - spacing 解析、边界内缩应用、参数合并
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-03
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""规划参数解析：resolve_spacing、apply_margin、merge_planning_params。

与 config 的关系：resolver 调用 config 中的 CAMERA_PRESETS、calculate_spacing、shrink_polygon。
数据驱动 + 模型驱动：merge_planning_params 实现 KMZ 优先、CLI 覆盖 的合并规则。
"""

from typing import Any, Dict, Optional
import numpy as np

from .config import CAMERA_PRESETS, calculate_spacing, shrink_polygon

# 面状航线规划参数默认值
_DEFAULT_POLYGON = {
    "direction": 0.0,
    "height": 120.0,
    "margin": 0.0,
    "overlap_lateral": 0.7,
    "overlap_longitudinal": 0.8,
    # 倾斜重叠率（用于 writer 写回 inclinedCameraOverlap*；规划几何仍使用正射 overlap_*）
    "overlap_lateral_inclined": None,
    "overlap_longitudinal_inclined": None,
    "spacing": 15.0,
    "use_camera": True,
    "camera_preset": "m3e",
    "optimize_path": True,
    "ortho_capture_enabled": True,
    "oblique_capture_enabled": False,
    # P02(GSD) 在合并阶段需要透传，供上层（plan_polygon）转成 spacing
    "gsd_cm_per_px": None,
    # P05/P06：合并后由 parse_polygon_params 将 flight_speed 写入 global_flight_speed（若仅传 flight_speed）
    "global_flight_speed": 10.0,
    "main_route_speed": None,
    "flight_speed": 10.0,  # 兼容旧键；与 schema 中 effective 速度对齐
    "auto_speed": None,  # reader 从 KML 读入的 autoFlightSpeed；解析时映射到 global_flight_speed
    "camera_pitch": None,  # 云台俯仰 (度)；mapping3d 模板 inclinedGimbalPitch 等
    "take_off_security_height": 120.0,
    "finish_action": "goHome",
    "with_timestamps": False,
    "reference_time": 0.0,
    "start_ll": None,  # (lon, lat)
    "end_ll": None,  # (lon, lat)
    # 与 docs/开发计划.md §十三、§十四 对齐；导出器见 output/kmz.resolve_height_export_modes
    "height_mode": None,  # relative_to_takeoff | relative_to_terrain | absolute | None（未传则走遗留 execute_height_mode）
    "execute_height_mode": None,  # WGS84 | relativeToStartPoint | realTimeFollowSurface（read_kmz / API 透传）
    # 贴近摄影 / 仿地参数（export_kmz 写入 surfaceFollowModeEnable 等）
    "surface_follow": None,
    # 导出 / 动作模板（桥接层 merged 须能吃到 API options）
    "action_template_id": None,
    "capture_mode": None,
    "heading_mode": None,
    "heading_angle": None,
    # generator 区域：ENU 水平框 + 前端 kml_json 航线高（merge 须透传）
    "kml_json": None,
    "input_kml_json": None,
    "template_kml_json": None,
    "use_enu_region_coordinates": None,
    # 相对被摄面距离（standoff，米）；供 generator / MissionConfig 透传。
    "global_distance_m": None,
    "standoff_distance": None,
    # calculate-area 几何体 / 任务项：须出现在此字典中 merge_planning_params 才会写入 merged
    "global_transitional_speed": None,
    "geometry_mode": None,
    "pitch": None,
    "start_z": None,
    "points_per_rev": None,
    "flight_height": None,
    "home_ll": None,
    "append_centroid": None,
    "survey_top_asl": None,
    "survey_bottom_asl": None,
    "route_orientation": None,
    "include_top_cap": None,
    "coverage_yaw_offset": None,
    "sweep_yaw_offset": None,
    "side_flight_speed": None,
    "ir_gsd": None,
    "climb_mode": None,
    "vertical_climb_mode": None,
    "oblique_climb_mode": None,
    "coverage_ratio": None,
    "start_azimuth_deg": None,
    "payload_lens_index": None,
    "payloadLensIndex": None,
    # 起飞 ingress：与 calculate-area / export-kmz 一致；读 KMZ ExtendedData 时见 takeoff_ingress_pose
    "takeoff_ingress_pose": None,
    "takeoff_ingress_x": None,
    "takeoff_ingress_y": None,
    "takeoff_ingress_z": None,
    "takeoff_ingress_heading_deg": None,
    # 司空 missionConfig 块：须在此出现 merge_planning_params 才会写入 merged（供 KMZ 导出）
    "mission_config": None,
}


def merge_planning_params(
    kmz_params: Optional[Dict[str, Any]] = None,
    cli_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """合并规划参数：优先级 默认 < KMZ 解析 < CLI 覆盖。

    Args:
        kmz_params: 从 KMZ/KML 解析的参数字典（direction、height、overlap、margin 等）。
        cli_params: CLI 或 API 传入的覆盖参数，仅非 None 的键会覆盖。

    Returns:
        合并后的参数字典，可直接传入 plan_polygon。
    """
    out = dict(_DEFAULT_POLYGON)
    if kmz_params:
        for k, v in kmz_params.items():
            if k in out and v is not None:
                out[k] = v
    if cli_params:
        for k, v in cli_params.items():
            if k in out and v is not None:
                out[k] = v
    return out


def resolve_spacing(
    spacing: float,
    height: float,
    camera: Optional[dict] = None,
    camera_preset: Optional[str] = None,
    overlap_lateral: float = 0.7,
    use_fixed_spacing: bool = False,
) -> float:
    """解析最终条带间距：默认按 GSD+重叠率计算，use_fixed_spacing 时使用固定 spacing。

    Args:
        spacing: 固定条带间距 (m)，use_fixed_spacing=True 时使用。
        height: 飞行高度 (m)。
        camera: 相机参数字典，或通过 camera_preset 指定。
        camera_preset: 预设名称 "m3e"|"m3t"|"m30t"|"m300"。
        overlap_lateral: 旁向重叠率 0~1。
        use_fixed_spacing: True 时强制使用 spacing，忽略 GSD。

    Returns:
        最终条带间距 (米)。
    """
    if use_fixed_spacing:
        return spacing
    cam = camera
    if camera_preset and camera_preset in CAMERA_PRESETS:
        cam = CAMERA_PRESETS[camera_preset]
    if cam:
        return calculate_spacing(height, cam, overlap_lateral, "lateral")
    return spacing


def resolve_longitudinal_spacing(
    spacing: float,
    height: float,
    camera: Optional[dict] = None,
    camera_preset: Optional[str] = None,
    overlap_longitudinal: float = 0.8,
    use_fixed_spacing: bool = False,
) -> Optional[float]:
    """解析沿航线采样间距（航向）：默认按 GSD+重叠率计算，use_fixed_spacing 时用 spacing 推导。

    Args:
        spacing: 条带间距 (m)，use_fixed_spacing=True 时作为基准。
        height: 飞行高度 (m)。
        camera: 相机参数字典。
        camera_preset: 预设名称。
        overlap_longitudinal: 航向重叠率 0~1。
        use_fixed_spacing: True 时用 spacing*(1-overlap) 推导。

    Returns:
        沿航线采样间距 (米)；None 表示不进行沿航线插值（保持端点のみ）。
    """
    if not use_fixed_spacing:
        cam = camera
        if camera_preset and camera_preset in CAMERA_PRESETS:
            cam = CAMERA_PRESETS[camera_preset]
        if cam:
            return calculate_spacing(height, cam, overlap_longitudinal, "longitudinal")
    return max(0.1, spacing * (1.0 - overlap_longitudinal))


def apply_margin(poly_xy: np.ndarray, margin: float) -> Optional[np.ndarray]:
    """对多边形应用边界内缩：margin>0 时收缩，若结果不足 3 点则返回 None。

    Args:
        poly_xy: 多边形顶点 (N, 2)，平面坐标 (米)。
        margin: 内缩距离 (米)。

    Returns:
        处理后的多边形顶点数组；无效时返回 None。
    """
    if margin <= 0:
        return poly_xy
    result = shrink_polygon(poly_xy, margin)
    if len(result) < 3:
        return None
    return result
