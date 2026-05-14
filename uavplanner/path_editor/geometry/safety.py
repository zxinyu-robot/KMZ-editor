# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 航线安全检测 - 八分角缓冲区与空间分析
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-03
# ------------------------------------------------------------ #

"""航线安全检测：八分角缓冲区构建、射线与 DEM 求交、航段安全隐患判定。

参考《面向条带状航测区域的无人机曲线航线设计方法探索》中的八分角算法：
在相邻航摄点 P₀、P₁ 间，沿 P₀P₁ 垂直方向取 8 个检测点（距离为安全缓冲 L），
在每个检测点沿 P₀P₁ 方向做射线与 DEM 求交，
若任一检测点到地形交点的距离小于 P₀P₁ 长度，则判定该段航线存在安全隐患。
算法逻辑可复用于 SLAM 激光场景的航线安全分析。
"""

from typing import Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from .dsm import sample_dsm_at


def _ray_dem_intersect(
    dsm: np.ndarray,
    meta: Dict,
    ray_origin_xy: Tuple[float, float],
    ray_origin_z: float,
    ray_dir_xy: Tuple[float, float],
    ray_dir_z: float,
    max_dist: float,
    sample_step: float = 0.5,
) -> Optional[Tuple[float, float, float]]:
    """沿射线方向采样，求射线与 DEM 表面的交点（首次穿入）。

    Args:
        dsm: DSM 数组。
        meta: DSM 元数据 (xmin, ymin, cell, width, height)。
        ray_origin_xy: 射线起点平面坐标 (x, y)。
        ray_origin_z: 射线起点高度。
        ray_dir_xy: 射线方向平面分量 (dx, dy)，需已归一化。
        ray_dir_z: 射线方向高度分量 dz。
        max_dist: 最大采样距离 (m)。
        sample_step: 沿射线采样步长 (m)。

    Returns:
        交点 (x, y, z)，未命中返回 None。
    """
    n_steps = max(1, int(max_dist / sample_step))
    dx, dy = ray_dir_xy
    for i in range(1, n_steps + 1):
        t = i * sample_step
        x = ray_origin_xy[0] + t * dx
        y = ray_origin_xy[1] + t * dy
        z = ray_origin_z + t * ray_dir_z
        dem_z = sample_dsm_at(dsm, meta, x, y)
        if dem_z is not None and z <= dem_z + 1e-6:
            return (x, y, dem_z)
    return None


def octant_check_segment(
    p0: Union[Tuple[float, float, float], List[float]],
    p1: Union[Tuple[float, float, float], List[float]],
    dsm: np.ndarray,
    meta: Dict,
    safety_buffer: float = 5.0,
    sample_step: float = 0.5,
) -> Tuple[bool, Optional[int], Optional[float]]:
    """八分角航线安全检测：单航段 P₀→P₁。

    在 P₀P₁ 中垂面内，取 8 个方向（每 45°）上距离线段 safety_buffer 的检测点，
    从每个检测点沿 P₀P₁ 方向发射射线与 DEM 求交，
    若任一到地形交点的距离 < |P₀P₁|，则判定不安全。

    Args:
        p0: 航段起点 (x, y, z) 或 (lon, lat, alt)，需与 DSM 同 CRS。
        p1: 航段终点。
        dsm: DSM 数组。
        meta: DSM 元数据。
        safety_buffer: 安全缓冲距离 L (m)。
        sample_step: 射线采样步长 (m)。

    Returns:
        (is_safe, failed_octant, min_clearance)
        - is_safe: 是否安全。
        - failed_octant: 若不安全，首次失败的八分角索引 0~7；否则 None。
        - min_clearance: 最小净空（检测点到地形距离），用于分析。
    """
    p0 = np.array(p0, dtype=float)
    p1 = np.array(p1, dtype=float)
    seg_vec = p1 - p0
    seg_len = float(np.linalg.norm(seg_vec))
    if seg_len < 1e-9:
        return True, None, float("inf")

    seg_dir = seg_vec / seg_len
    seg_dir_xy = np.array([seg_dir[0], seg_dir[1]])
    seg_dir_z = seg_dir[2] if len(seg_dir) > 2 else 0.0
    seg_len_xy = np.sqrt(seg_dir_xy[0] ** 2 + seg_dir_xy[1] ** 2)
    if seg_len_xy < 1e-9:
        perp_xy = np.array([1.0, 0.0])
    else:
        perp_xy = np.array([-seg_dir_xy[1], seg_dir_xy[0]]) / seg_len_xy

    mid = 0.5 * (p0 + p1)
    mid_xy = mid[:2]
    mid_z = mid[2] if len(mid) > 2 else (float(p0[2]) + float(p1[2])) / 2.0

    min_clearance = float("inf")
    failed_octant = None

    for i in range(8):
        angle = i * (2 * np.pi / 8)
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)
        perp_xy_i = cos_a * perp_xy + sin_a * np.array([-perp_xy[1], perp_xy[0]])
        det_xy = mid_xy + safety_buffer * perp_xy_i
        det_z = mid_z

        hit = _ray_dem_intersect(
            dsm,
            meta,
            tuple(det_xy),
            det_z,
            tuple(seg_dir_xy),
            seg_dir_z,
            max_dist=seg_len * 1.5,
            sample_step=sample_step,
        )
        if hit is None:
            clearance = float("inf")
        else:
            hit_xy = np.array(hit[:2])
            hit_z = hit[2]
            dist_xy = np.linalg.norm(hit_xy - det_xy)
            dist_z = hit_z - det_z
            clearance = np.sqrt(dist_xy**2 + dist_z**2)

        if clearance < min_clearance:
            min_clearance = clearance
        if clearance < seg_len - 1e-6:
            failed_octant = i
            return False, failed_octant, min_clearance

    return True, None, min_clearance


def check_route_safety(
    waypoints_xy: List[Tuple[float, float, float]],
    dsm: np.ndarray,
    meta: Dict,
    safety_buffer: float = 5.0,
    sample_step: float = 0.5,
) -> Tuple[List[bool], List[Optional[int]], List[Optional[float]]]:
    """对整条航线的各航段执行八分角安全检测。

    Args:
        waypoints_xy: 航点序列 [(x, y, z), ...]，平面坐标与 DSM 同 CRS。
        dsm: DSM 数组。
        meta: DSM 元数据。
        safety_buffer: 安全缓冲 L (m)。
        sample_step: 射线采样步长 (m)。

    Returns:
        (segment_safe, failed_octants, min_clearances)
        - segment_safe: 各航段是否安全 [bool, ...]。
        - failed_octants: 各航段失败八分角索引，安全段为 None。
        - min_clearances: 各航段最小净空 (m)。
    """
    n = len(waypoints_xy)
    segment_safe = []
    failed_octants = []
    min_clearances = []
    for i in range(n - 1):
        safe, failed, clearance = octant_check_segment(
            waypoints_xy[i],
            waypoints_xy[i + 1],
            dsm,
            meta,
            safety_buffer=safety_buffer,
            sample_step=sample_step,
        )
        segment_safe.append(safe)
        failed_octants.append(failed)
        min_clearances.append(clearance)
    return segment_safe, failed_octants, min_clearances


def build_route_buffer_3d(
    waypoints_xy: List[Tuple[float, float, float]],
    half_width: float,
    n_pts_per_seg: int = 8,
) -> np.ndarray:
    """构建航线的三维缓冲区（沿航段法向扩展的带状区域采样点）。

    用于可视化或进一步空间分析，不依赖 DEM。

    Args:
        waypoints_xy: 航点 [(x, y, z), ...]。
        half_width: 半宽 (m)，向两侧各扩展。
        n_pts_per_seg: 每段生成的缓冲区采样点数。

    Returns:
        缓冲区边界点 (M, 3)，左边界与右边界交替。
    """
    pts = np.array(waypoints_xy, dtype=float)
    if len(pts) < 2:
        return pts

    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        seg = p1 - p0
        seg_xy = seg[:2]
        l_xy = np.linalg.norm(seg_xy)
        if l_xy < 1e-9:
            perp = np.array([1.0, 0.0])
        else:
            perp = np.array([-seg_xy[1], seg_xy[0]]) / l_xy
        for j in range(n_pts_per_seg + 1):
            t = j / n_pts_per_seg
            mid = (1 - t) * p0 + t * p1
            left = mid.copy()
            left[:2] += half_width * perp
            right = mid.copy()
            right[:2] -= half_width * perp
            out.append(left)
            out.append(right)
    return np.array(out)
