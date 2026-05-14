# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 几何体算法 - 圆柱几何模式下的局部路径（ENU）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-04-03
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""几何体算法（圆柱几何模式）。

与 `docs/path_editor_docs/geometry/几何体前端对接接口文档.md` 对齐：仅处理 **几何形态**
（`geometry_mode`、`pitch` 语义、采样与高度基准），在 **局部 ENU**（x=东、y=北、z=向上，米）上输出路径。

**圆柱体航线**（圆心经纬度、投影到 WGS84 航点）见 `path_editor.algorithm.cylinder.plan_cylinder_route`。
"""

from __future__ import annotations

from math import cos, sin, pi
from typing import List, Tuple

_Z_TOL = 1e-6

GEOMETRY_SURFACE_SWEEP = "surface_sweep"
GEOMETRY_SPIRAL = "spiral"


def plan_cylinder_surface_sweep(
    radius: float,
    height: float,
    pitch: float,
    start_z: float = 25.0,
    points_per_rev: int = 36,
    flight_height: float = 0.0,
) -> List[Tuple[float, float, float]]:
    """圆柱表面分层扫掠：每层为完整水平圆，层间竖直步距为 pitch，圆周方向之字形。

    局部坐标：x=东、y=北、z=竖直向上（米）。圆柱轴线与 z 轴重合。

    Args:
        radius: 圆柱半径 (m)。
        height: 圆柱总高度 (m)，沿 z 从 start_z+flight_height 起向上覆盖。
        pitch: 相邻层之间的竖直间距 (m)，对应工程要范中的层向采样步长。
        start_z: 起始 z (m)。
        points_per_rev: 每层圆周采样点数。
        flight_height: 叠加到 z 的基准偏移 (m)。

    Returns:
        [(x, y, z), ...] 局部坐标路径。

    Raises:
        ValueError: 参数非法。
    """
    if radius <= 0 or height <= 0 or pitch <= 0:
        raise ValueError("radius, height, pitch 须为正数")
    if points_per_rev < 4:
        raise ValueError("points_per_rev 至少为 4")

    z_base = start_z + flight_height
    z_top = z_base + height

    # 竖直分层：从底面步进到顶面，**始终包含顶面 z_top**，避免出现 height==pitch 时只有一层、看起来像「只飞一圈」。
    zs: List[float] = []
    z = z_base
    while z < z_top - _Z_TOL:
        zs.append(z)
        z += pitch
    if not zs:
        zs.append(z_base)
    elif abs(zs[-1] - z_top) > _Z_TOL:
        zs.append(z_top)

    n = max(1, int(points_per_rev))
    dtheta = 2.0 * pi / float(n)

    path_xyz: List[Tuple[float, float, float]] = []
    for layer_idx, z in enumerate(zs):
        if layer_idx % 2 == 0:
            order = range(n)
        else:
            order = range(n - 1, -1, -1)
        for j in order:
            theta = float(j) * dtheta
            x = radius * cos(theta)
            y = radius * sin(theta)
            path_xyz.append((x, y, z))

    return path_xyz


def plan_cylinder_spiral(
    radius: float,
    height: float,
    pitch: float,
    start_z: float = 25.0,
    points_per_rev: int = 36,
    flight_height: float = 0.0,
) -> List[Tuple[float, float, float]]:
    """生成圆柱螺旋线路径（局部坐标）。兼容旧行为。

    参数方程：γ(t) = (r·cos(t), r·sin(t), z0 + b·t)，b = pitch/(2π)。
    """
    if radius <= 0 or height <= 0 or pitch <= 0:
        raise ValueError("radius, height, pitch 须为正数")

    b = pitch / (2 * pi)
    t_max = height / b
    dt = (2 * pi) / max(1, points_per_rev)

    path_xyz: List[Tuple[float, float, float]] = []
    t = 0.0
    z0 = start_z + flight_height
    while t <= t_max + 1e-9:
        x = radius * cos(t)
        y = radius * sin(t)
        z = z0 + b * t
        path_xyz.append((x, y, z))
        t += dt

    return path_xyz


def plan_cylinder_local_path(
    geometry_mode: str,
    radius: float,
    height: float,
    pitch: float,
    start_z: float = 25.0,
    points_per_rev: int = 36,
    flight_height: float = 0.0,
) -> List[Tuple[float, float, float]]:
    """按几何模式生成本地 (x,y,z) 路径。"""
    mode = (geometry_mode or GEOMETRY_SURFACE_SWEEP).strip().lower()
    if mode == GEOMETRY_SPIRAL:
        return plan_cylinder_spiral(
            radius=radius,
            height=height,
            pitch=pitch,
            start_z=start_z,
            points_per_rev=points_per_rev,
            flight_height=flight_height,
        )
    return plan_cylinder_surface_sweep(
        radius=radius,
        height=height,
        pitch=pitch,
        start_z=start_z,
        points_per_rev=points_per_rev,
        flight_height=flight_height,
    )
