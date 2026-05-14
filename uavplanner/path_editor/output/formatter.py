# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 输出格式化 - 平面航点转 (lon, lat, alt)，航段时间语义
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""输出层：平面航点转为标准经纬度高程格式，支持航点/航段时间语义。"""

from typing import List, Tuple, Callable, Optional
import numpy as np

from ..geometry import segment_lengths_m


def to_waypoints(
    path_xy: np.ndarray,
    xy_to_ll: Callable[[float, float], Tuple[float, float]],
    height: float,
) -> List[Tuple[float, float, float]]:
    """将平面航点转为经纬度高程序列。

    Args:
        path_xy: 平面航点 (N, 2)，单位米。
        xy_to_ll: 平面坐标转经纬度的函数 (x, y) -> (lon, lat)。
        height: 高度 (米)，应用到所有航点。

    Returns:
        [(lon, lat, alt), ...] 航点序列。
    """
    waypoints = []
    for x, y in path_xy:
        lon, lat = xy_to_ll(x, y)
        waypoints.append((lon, lat, height))
    return waypoints


def to_waypoints_3d(
    path_xyz: List[Tuple[float, float, float]],
    xy_to_ll: Callable[[float, float], Tuple[float, float]],
) -> List[Tuple[float, float, float]]:
    """将三维路径（局部坐标）转为经纬度高程序列。

    Args:
        path_xyz: 路径 [(x, y, z), ...]，局部平面坐标 (米)，z 为高度 (米)。
        xy_to_ll: 平面坐标转经纬度的函数 (x, y) -> (lon, lat)。

    Returns:
        [(lon, lat, alt), ...] 航点序列。
    """
    waypoints = []
    for x, y, z in path_xyz:
        lon, lat = xy_to_ll(x, y)
        waypoints.append((lon, lat, z))
    return waypoints


def add_waypoint_timestamps(
    waypoints: List[Tuple[float, float, float]],
    speed: float = 10.0,
    reference_time: float = 0.0,
) -> Tuple[List[Tuple[float, float, float, float]], List[float]]:
    """为航点序列添加时间语义（到达各航点的累计时间）。

    按恒速、直线段距离估算各航段耗时，累加得到到达各航点的时间戳。
    用于与时间管理节点、微分代码节点（无 GPS 无人机）的时间维度对齐。

    Args:
        waypoints: [(lon, lat, alt), ...] 航点序列。
        speed: 飞行速度 (m/s)，默认 10.0。
        reference_time: 首航点参考时间 (秒)，通常为 0 或任务起始时间戳。

    Returns:
        (waypoints_with_time, segment_durations)
        - waypoints_with_time: [(lon, lat, alt, timestamp_s), ...]
        - segment_durations: 各航段耗时 [dt_0_1, dt_1_2, ...] (秒)
    """
    if len(waypoints) < 2:
        if waypoints:
            return [(w[0], w[1], w[2], reference_time) for w in waypoints], []
        return [], []

    seg_lens = segment_lengths_m(waypoints)
    speed = max(0.1, float(speed))
    seg_dts = [d / speed for d in seg_lens]

    result = []
    t = reference_time
    for i, (lon, lat, alt) in enumerate(waypoints):
        result.append((lon, lat, alt, t))
        if i < len(seg_dts):
            t += seg_dts[i]
    return result, seg_dts


def waypoints_with_time_to_list(
    waypoints_with_time: List[Tuple[float, float, float, float]],
) -> List[dict]:
    """将有时间的航点序列转为 JSON 可序列化格式。

    Returns:
        [{"lon": x, "lat": y, "alt": z, "timestamp_s": t}, ...]
    """
    return [
        {"lon": w[0], "lat": w[1], "alt": w[2], "timestamp_s": w[3]}
        for w in waypoints_with_time
    ]
