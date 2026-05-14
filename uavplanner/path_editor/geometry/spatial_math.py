#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 空间数学基础方法（角度语义与坐标变换）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""空间计算基础方法（统一口径）。

角度契约（全模块统一）：
- heading/bearing: 北=0°，顺时针为正，范围 [0, 360)
- math_angle: 东=0°，逆时针为正，范围 [0, 360)
- 局部平面坐标: x=东向，y=北向（米）
"""

from __future__ import annotations

from math import atan2, cos, pi, sin, sqrt
from typing import Iterable, Sequence, Tuple


def deg2rad(deg: float) -> float:
    return float(deg) * pi / 180.0


def rad2deg(rad: float) -> float:
    return float(rad) * 180.0 / pi


def normalize_angle_deg(angle: float) -> float:
    """归一化到 [0, 360)。"""
    return float(angle) % 360.0


def normalize_delta_deg(delta: float) -> float:
    """归一化到 (-180, 180]。"""
    d = (float(delta) + 180.0) % 360.0 - 180.0
    if d <= -180.0:
        return 180.0
    return d


def heading_to_math_deg(heading_deg: float) -> float:
    """heading(北0顺时针) -> math_angle(东0逆时针)。"""
    return normalize_angle_deg(90.0 - float(heading_deg))


def math_to_heading_deg(math_deg: float) -> float:
    """math_angle(东0逆时针) -> heading(北0顺时针)。"""
    return normalize_angle_deg(90.0 - float(math_deg))


def bearing_deg(p1: Sequence[float], p2: Sequence[float]) -> float:
    """局部平面方位角（北0顺时针）。"""
    dx = float(p2[0]) - float(p1[0])
    dy = float(p2[1]) - float(p1[1])
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return 0.0
    return normalize_angle_deg(rad2deg(atan2(dx, dy)))


def distance_2d_m(p1: Sequence[float], p2: Sequence[float]) -> float:
    dx = float(p2[0]) - float(p1[0])
    dy = float(p2[1]) - float(p1[1])
    return sqrt(dx * dx + dy * dy)


def project_point_by_heading(
    p: Sequence[float], heading_deg: float, distance_m: float
) -> Tuple[float, float]:
    """已知点+航向角+距离，推算未知点（局部平面）。"""
    h = deg2rad(normalize_angle_deg(heading_deg))
    x = float(p[0]) + float(distance_m) * sin(h)
    y = float(p[1]) + float(distance_m) * cos(h)
    return (x, y)


def rotate_xy(point: Sequence[float], center: Sequence[float], angle_deg: float) -> Tuple[float, float]:
    """绕 center 旋转点（数学角：东0逆时针为正）。"""
    a = deg2rad(angle_deg)
    px = float(point[0]) - float(center[0])
    py = float(point[1]) - float(center[1])
    ca, sa = cos(a), sin(a)
    rx = ca * px - sa * py + float(center[0])
    ry = sa * px + ca * py + float(center[1])
    return (rx, ry)


def polygon_area_signed(points: Iterable[Sequence[float]]) -> float:
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 3:
        return 0.0
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def is_clockwise(points: Iterable[Sequence[float]]) -> bool:
    """x=东,y=北坐标系下，带符号面积 < 0 视为顺时针。"""
    return polygon_area_signed(points) < 0.0

