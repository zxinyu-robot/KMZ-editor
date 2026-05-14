# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 航线流水线 - 串联五层
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""
航线流水线：纯编排，委托各层处理。
几何输入 → 规划参数 → 算法 → 后处理 → 输出
"""

from typing import List, Optional, Tuple

import numpy as np

from .geometry import prepare_polygon, ll_to_xy_func, xy_to_ll_func, infer_sweep_segment_starts
from .params import (
    resolve_spacing,
    resolve_longitudinal_spacing,
    apply_margin,
    CAMERA_PRESETS,
    calculate_spacing,
)
from .algorithm import plan_polygon_route, plan_corridor_route
from .algorithm.cylinder import plan_cylinder_local_path
from .postprocess import optimize_route_path
from .output import to_waypoints, to_waypoints_3d, add_waypoint_timestamps


def edit_route(
    polygon_ll: List[Tuple[float, float]],
    spacing: float,
    direction: float,
    height: float = 100.0,
    start_ll: Optional[Tuple[float, float]] = None,
    end_ll: Optional[Tuple[float, float]] = None,
    margin: float = 0.0,
    use_camera: bool = True,
    camera: Optional[dict] = None,
    camera_preset: Optional[str] = None,
    overlap_lateral: float = 0.7,
    overlap_longitudinal: float = 0.8,
    optimize_path: bool = False,
    with_timestamps: bool = False,
    flight_speed: float = 10.0,
    reference_time: float = 0.0,
) -> Tuple[List[Tuple[float, float, float]], List[int]]:
    """面状航线流水线：几何输入 → 规划参数 → 算法 → 后处理 → 输出。

    Args:
        polygon_ll: 多边形顶点 [(lon, lat), ...]。
        spacing: 条带间距 (m)，use_camera=True 时可由相机覆盖。
        direction: 航线方向 (度)。
        height: 飞行高度 (m)。
        start_ll: 可选起点。
        end_ll: 可选终点。
        margin: 边界内缩 (m)。
        use_camera: 是否按相机自动算间距。
        camera: 相机参数字典，或通过 camera_preset 指定。
        camera_preset: 预设 "m3e"|"m3t"|"m30t"|"m300"。
        overlap_lateral: 旁向重叠率 0~1。
        overlap_longitudinal: 航向重叠率 0~1。
        optimize_path: 是否剔除共线冗余点。
        with_timestamps: 是否在返回中加入时间语义（见下方返回说明）。
        flight_speed: 飞行速度 (m/s)，用于估算航段时间。
        reference_time: 首航点参考时间 (秒)。

    Returns:
        (waypoints, segment_start_indices) 元组。
        若 with_timestamps=False: waypoints 为 [(lon, lat, alt), ...]
        若 with_timestamps=True: waypoints 为 [(lon, lat, alt, timestamp_s), ...]
        segment_start_indices 为各航段首航点索引，如 [0, 15, 32]。
    """
    # 几何输入层（委托 geometry）
    geo = prepare_polygon(polygon_ll, start_ll, end_ll)

    # 规划参数层（委托 params）：默认 GSD，use_camera=False 时用固定 spacing
    use_fixed = not use_camera
    final_spacing = resolve_spacing(
        spacing, height, camera, camera_preset, overlap_lateral, use_fixed_spacing=use_fixed
    )
    longitudinal_spacing = resolve_longitudinal_spacing(
        spacing, height, camera, camera_preset, overlap_longitudinal, use_fixed_spacing=use_fixed
    )
    poly_xy = apply_margin(geo.poly_xy, margin)
    if poly_xy is None:
        return [], [0]

    # 算法核心层
    path_xy = plan_polygon_route(
        poly_xy, final_spacing, direction, geo.start_xy, geo.end_xy,
        longitudinal_spacing=longitudinal_spacing,
    )

    # 后处理层：导出侧通过 actionGroup 连续触发拍照，中间共线点不承担拍照语义，统一剔除。
    if optimize_path and len(path_xy) > 2:
        path_xy = optimize_route_path(path_xy)

    # 输出层
    waypoints = to_waypoints(path_xy, geo.xy2ll, height)
    if with_timestamps and len(waypoints) > 0:
        wps_with_time, _ = add_waypoint_timestamps(
            waypoints, speed=flight_speed, reference_time=reference_time
        )
        segment_starts = infer_sweep_segment_starts(path_xy)
        return wps_with_time, segment_starts
    segment_starts = infer_sweep_segment_starts(path_xy)
    return waypoints, segment_starts


def edit_corridor_route(
    centerline_ll: List[Tuple[float, float]],
    half_width: float,
    lateral_spacing: float,
    height: float = 100.0,
    baseline: Optional[float] = None,
    longitudinal_spacing: Optional[float] = None,
    use_camera: bool = False,
    camera: Optional[dict] = None,
    camera_preset: Optional[str] = None,
    overlap_lateral: float = 0.7,
    overlap_longitudinal: float = 0.8,
    with_timestamps: bool = False,
    flight_speed: float = 10.0,
    reference_time: float = 0.0,
) -> Tuple[List[Tuple[float, float, float]], List[int]]:
    """带状航线流水线：中心线 → 拐点外扩 → 带状扫线 → 输出。

    Args:
        centerline_ll: 中心线顶点 [(lon, lat), ...]。
        half_width: 半宽 (m)。
        lateral_spacing: 旁向间距 (m)，use_camera=True 时可由相机覆盖计算。
        height: 飞行高度 (m)。
        baseline: 摄影基线 (m)，沿航线插值；与 longitudinal_spacing 二选一。
        longitudinal_spacing: 沿航线采样间距 (m)。
        use_camera: 是否按相机自动算间距。
        camera: 相机参数字典。
        camera_preset: 预设 "m3e"|"m3t"|"m30t"|"m300"。
        overlap_lateral: 旁向重叠率。
        overlap_longitudinal: 航向重叠率。
        with_timestamps: 是否输出时间语义。
        flight_speed: 飞行速度 (m/s)。
        reference_time: 首航点参考时间 (秒)。

    Returns:
        (waypoints, segment_start_indices)。
    """
    if len(centerline_ll) < 2:
        return [], [0]

    ref_lon, ref_lat = centerline_ll[0]
    ll2xy = ll_to_xy_func(ref_lon, ref_lat)
    xy2ll = xy_to_ll_func(ref_lon, ref_lat)
    center_xy = np.array([ll2xy(lon, lat) for lon, lat in centerline_ll])

    if use_camera and (camera or camera_preset):
        cam = camera or CAMERA_PRESETS.get(camera_preset or "m3e", {})
        lateral_spacing = calculate_spacing(height, cam, overlap_lateral, "lateral")
        if longitudinal_spacing is None and baseline is None:
            longitudinal_spacing = calculate_spacing(
                height, cam, overlap_longitudinal, "longitudinal"
            )

    path_xy = plan_corridor_route(
        center_xy,
        half_width=half_width,
        lateral_spacing=lateral_spacing,
        baseline=baseline,
        longitudinal_spacing=longitudinal_spacing,
    )

    waypoints = to_waypoints(path_xy, xy2ll, height)
    if with_timestamps and len(waypoints) > 0:
        wps_with_time, _ = add_waypoint_timestamps(
            waypoints, speed=flight_speed, reference_time=reference_time
        )
        segment_starts = infer_sweep_segment_starts(path_xy)
        return wps_with_time, segment_starts
    segment_starts = infer_sweep_segment_starts(path_xy)
    return waypoints, segment_starts


def edit_cylinder_route(
    center_ll: Tuple[float, float],
    radius: float,
    height: float,
    pitch: float,
    start_z: float = 25.0,
    points_per_rev: int = 36,
    flight_height: float = 0.0,
    geometry_mode: str = "surface_sweep",
    home_ll: Optional[Tuple[float, float]] = None,
    append_centroid: bool = False,
    with_timestamps: bool = False,
    flight_speed: float = 10.0,
    reference_time: float = 0.0,
) -> List[Tuple[float, float, float]]:
    """圆柱体航线流水线：几何输入 → 规划参数 → 算法 → 输出。

    Args:
        center_ll: 底面圆心 (lon, lat)。
        radius: 飞行半径 (m)。
        height: 圆柱高度 (m)。
        pitch: surface_sweep 模式下为层间距 (m)；spiral 模式下为每圈螺距 (m/圈)。
        start_z: 起始高度 (m)，默认 25 以满足司空近地 20m 安全阈值。
        points_per_rev: 每圈采样点数。
        flight_height: 叠加到 z 的基准高度。
        geometry_mode: 几何体路径模式：surface_sweep（默认）| spiral（兼容）。
        home_ll: 可选起飞参考点 (lon, lat)，插入为首航点，高度与首条规划航点一致。
        append_centroid: True 时在末尾追加圆心 (center_ll) 航点，高度与末条规划航点一致。
        with_timestamps: 是否在返回中加入时间语义。
        flight_speed: 飞行速度 (m/s)。
        reference_time: 首航点参考时间 (秒)。

    Returns:
        若 with_timestamps=False: [(lon, lat, alt), ...]
        若 with_timestamps=True: [(lon, lat, alt, timestamp_s), ...]
    """
    # 几何输入层：坐标转换
    ref_lon, ref_lat = center_ll
    xy2ll = xy_to_ll_func(ref_lon, ref_lat)

    # 算法核心层
    path_xyz = plan_cylinder_local_path(
        geometry_mode=geometry_mode,
        radius=radius,
        height=height,
        pitch=pitch,
        start_z=start_z,
        points_per_rev=points_per_rev,
        flight_height=flight_height,
    )

    # 输出层
    waypoints = to_waypoints_3d(path_xyz, xy2ll)
    if home_ll is not None and len(home_ll) >= 2:
        home_lon, home_lat = float(home_ll[0]), float(home_ll[1])
        if waypoints:
            alt0 = float(waypoints[0][2])
        else:
            alt0 = float(start_z + flight_height)
        waypoints = [(home_lon, home_lat, alt0)] + list(waypoints)
    if append_centroid and waypoints:
        last_alt = float(waypoints[-1][2])
        waypoints = list(waypoints) + [(float(center_ll[0]), float(center_ll[1]), last_alt)]
    if with_timestamps and len(waypoints) > 0:
        wps_with_time, _ = add_waypoint_timestamps(
            waypoints, speed=flight_speed, reference_time=reference_time
        )
        return wps_with_time
    return waypoints
