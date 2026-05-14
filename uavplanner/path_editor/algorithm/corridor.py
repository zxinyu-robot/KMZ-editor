# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 带状航线算法 - 沿中心线扫线
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-03
# ------------------------------------------------------------ #

"""带状航线算法：中心线外扩、拐点向量计算、沿折线/中心线的带状扫线。

参考《面向条带状航测区域的无人机曲线航线设计方法探索》：
- 中心线由拐点 P₀, P₁, …, Pₖ 组成，向两侧扩展宽度 D 形成条带
- 拐点外扩公式：(xₚ,yₚ) = (xᵢ,yᵢ) + L/sinθ·(v₁ - v₂)，v₁、v₂ 为前后单位向量
- 按旁向间距 Dᵧ 计算航线条数，沿中心线两侧外扩生成多条曲线航线
- 在相邻拐点间按摄影基线 B 插值航摄点
"""

from typing import List, Optional, Tuple

import numpy as np


def _left_perp(v: np.ndarray) -> np.ndarray:
    """二维向量的左垂直（逆时针 90°）。"""
    return np.array([-v[1], v[0]])


def _segments_intersect(a1: np.ndarray, a2: np.ndarray, b1: np.ndarray, b2: np.ndarray) -> bool:
    """判断两线段是否相交（不含端点重合）。"""
    # 向量叉积：ab × ac 与 ad × ab 同号则 c、d 在 ab 两侧
    def cross(o: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    c1 = cross(a1, a2, b1)
    c2 = cross(a1, a2, b2)
    c3 = cross(b1, b2, a1)
    c4 = cross(b1, b2, a2)
    if c1 * c2 < 0 and c3 * c4 < 0:
        return True
    return False


def _polygon_self_intersects(poly_xy: np.ndarray) -> bool:
    """判断多边形是否自相交。"""
    n = len(poly_xy)
    if n < 4:
        return False
    for i in range(n):
        a1, a2 = poly_xy[i], poly_xy[(i + 1) % n]
        for j in range(i + 2, n):
            if (j + 1) % n == i:
                continue
            b1, b2 = poly_xy[j], poly_xy[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _expand_corner(
    p: np.ndarray,
    v_in: np.ndarray,
    v_out: np.ndarray,
    half_width: float,
    side: int,
) -> np.ndarray:
    """拐点外扩：按公式 (xₚ,yₚ) = (xᵢ,yᵢ) + L/sinθ·(v₁ - v₂)。

    Args:
        p: 拐点 (2,)。
        v_in: 入边单位向量 (2,)。
        v_out: 出边单位向量 (2,)。
        half_width: 半宽 L (m)。
        side: +1 为左侧外扩，-1 为右侧外扩。

    Returns:
        外扩点 (2,)。
    """
    diff = v_in - v_out
    diff_norm = np.linalg.norm(diff)
    if diff_norm < 1e-9:
        perp = _left_perp(v_in)
        return p + side * half_width * perp
    cos_theta = np.clip(np.dot(v_in, v_out), -1.0, 1.0)
    theta = np.arccos(cos_theta)
    sin_theta = np.sin(theta)
    if sin_theta < 1e-9:
        perp = _left_perp(v_in)
        return p + side * half_width * perp
    offset = (half_width / sin_theta) * (diff / diff_norm)
    return p + side * offset


def _expand_polyline(
    center_xy: np.ndarray,
    half_width: float,
    side: int,
) -> np.ndarray:
    """中心线折线向一侧外扩，得到一条边界线。

    Args:
        center_xy: 中心线顶点 (N, 2)。
        half_width: 半宽 (m)。
        side: +1 左侧，-1 右侧。

    Returns:
        外扩边界顶点 (N, 2)。
    """
    n = len(center_xy)
    if n < 2:
        return center_xy.copy()

    out = np.zeros_like(center_xy)
    for i in range(n):
        if i == 0:
            v_in = center_xy[1] - center_xy[0]
        else:
            v_in = center_xy[i] - center_xy[i - 1]
        if i == n - 1:
            v_out = center_xy[-1] - center_xy[-2]
        else:
            v_out = center_xy[i + 1] - center_xy[i]

        v_in_norm = np.linalg.norm(v_in)
        v_out_norm = np.linalg.norm(v_out)
        if v_in_norm < 1e-9:
            v_in = v_out.copy() if v_out_norm >= 1e-9 else np.array([1.0, 0.0])
        else:
            v_in = v_in / v_in_norm
        if v_out_norm < 1e-9:
            v_out = v_in.copy()
        else:
            v_out = v_out / v_out_norm

        out[i] = _expand_corner(center_xy[i], v_in, v_out, half_width, side)

    return out


def _interpolate_along_curve(
    curve_xy: np.ndarray,
    baseline: float,
) -> np.ndarray:
    """沿曲线按摄影基线 B 插值航摄点。

    Args:
        curve_xy: 曲线顶点 (N, 2)。
        baseline: 摄影基线 B (m)。

    Returns:
        插值后的航点 (M, 2)。
    """
    if len(curve_xy) < 2:
        return curve_xy.copy()

    seg_lengths = np.linalg.norm(np.diff(curve_xy, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg_lengths)])
    total = cum[-1]
    if total < 1e-9 or baseline < 1e-9:
        return curve_xy.copy()

    n_pts = max(2, int(total / baseline) + 1)
    t_target = np.linspace(0, total, n_pts, endpoint=True)
    out = []
    for t in t_target:
        if t <= 0:
            out.append(curve_xy[0])
            continue
        if t >= total:
            out.append(curve_xy[-1])
            continue
        idx = np.searchsorted(cum, t, side="right") - 1
        idx = min(idx, len(seg_lengths) - 1)
        local_t = (t - cum[idx]) / (seg_lengths[idx] + 1e-12)
        pt = (1 - local_t) * curve_xy[idx] + local_t * curve_xy[idx + 1]
        out.append(pt)
    return np.array(out)


def plan_corridor_route(
    center_xy: np.ndarray,
    half_width: float,
    lateral_spacing: float,
    baseline: Optional[float] = None,
    longitudinal_spacing: Optional[float] = None,
) -> np.ndarray:
    """沿中心线的带状扫线航线规划。

    中心线向两侧各扩展 half_width，按 lateral_spacing 生成多条平行曲线，
    在每条曲线上按 baseline 或 longitudinal_spacing 插值航摄点，
    采用 Z 字形往复（奇偶线反向）。

    Args:
        center_xy: 中心线顶点 (N, 2)，平面坐标 (米)。
        half_width: 半宽 (m)，中心线向每侧扩展距离。
        lateral_spacing: 旁向间距 Dᵧ (m)，相邻航线间距。
        baseline: 摄影基线 B (m)，沿航线插值间隔；与 longitudinal_spacing 二选一。
        longitudinal_spacing: 沿航线采样间距 (m)；若为 None 且 baseline 为 None，则不插值。

    Returns:
        航点序列 path_xy (M, 2)，平面坐标。

    Raises:
        ValueError: 带状区域边界交叉（中心线拐弯过急或半宽过大），司空无法识别。
    """
    center_xy = np.asarray(center_xy, dtype=float)
    if len(center_xy) < 2:
        return center_xy

    band = centerline_to_band_polygon_xy(center_xy, half_width)
    if len(band) >= 4 and _polygon_self_intersects(band):
        raise ValueError(
            "用户测区不支持交叉面，无法生成航线。"
            "中心线拐弯过急或半宽过大导致边界交叉，请减小 --half-width 或简化中心线（避免急转弯）。"
        )

    n_lines = max(1, int(2 * half_width / lateral_spacing))
    if n_lines == 1:
        offsets = [0.0]
    else:
        offsets = np.linspace(-half_width, half_width, n_lines)

    path_parts = []
    for idx, off in enumerate(offsets):
        side = 1 if off >= 0 else -1
        abs_off = abs(off)
        if abs_off < 1e-9:
            curve = center_xy.copy()
        else:
            curve = _expand_polyline(center_xy, abs_off, side)

        if baseline is not None and baseline > 0:
            curve = _interpolate_along_curve(curve, baseline)
        elif longitudinal_spacing is not None and longitudinal_spacing > 0:
            curve = _interpolate_along_curve(curve, longitudinal_spacing)

        if idx % 2 == 1:
            curve = curve[::-1]
        path_parts.append(curve)

    if not path_parts:
        return center_xy

    path = path_parts[0]
    for i in range(1, len(path_parts)):
        if np.linalg.norm(path[-1] - path_parts[i][0]) > np.linalg.norm(
            path[-1] - path_parts[i][-1]
        ):
            path_parts[i] = path_parts[i][::-1]
        path = np.vstack([path, path_parts[i][1:]])

    return path


def centerline_to_band_polygon_xy(
    center_xy: np.ndarray,
    half_width: float,
) -> np.ndarray:
    """中心线向两侧外扩形成带状多边形顶点（用于模板规划区域显示）。

    Args:
        center_xy: 中心线顶点 (N, 2)，平面坐标 (米)。
        half_width: 半宽 (m)。

    Returns:
        多边形顶点 (M, 2)，左边界 + 右边界逆序，闭合。
    """
    center_xy = np.asarray(center_xy, dtype=float)
    if len(center_xy) < 2:
        return center_xy
    left = _expand_polyline(center_xy, half_width, 1)
    right = _expand_polyline(center_xy, half_width, -1)
    return np.vstack([left, right[::-1], left[0:1]])
