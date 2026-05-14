# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: LLH ↔ mission ENU world ↔ AABB 盒局部（辅助对接）
# ------------------------------------------------------------ #
"""地理坐标与规划用米制 frame 的衔接工具。

``build_llh_enu_transform`` 的实现源仍为 ``path_editor.geometry.coordinates``；
本模块仅组合「ENU world → inv(aabb_transform) → 盒局部」。"""
from __future__ import annotations

from typing import Sequence, Tuple

import numpy as np

from uavplanner.path_editor.geometry import build_llh_enu_transform


def llh_to_mission_enu(
    lon: float,
    lat: float,
    alt: float,
    ref_lon: float,
    ref_lat: float,
    ref_alt: float,
) -> Tuple[float, float, float]:
    """WGS84 LLH → 以 ``(ref_lon, ref_lat, ref_alt)`` 为原点的局部 ENU（米）。"""
    llh_to_enu, _ = build_llh_enu_transform(ref_lon, ref_lat, ref_alt)
    e, n, u = llh_to_enu(float(lon), float(lat), float(alt))
    return (float(e), float(n), float(u))


def world_xyz_to_aabb_local(
    x: float,
    y: float,
    z: float,
    aabb_transform: Sequence[Sequence[float]],
) -> Tuple[float, float, float]:
    """world（米）→ AABB 盒局部坐标。

    Args:
        x, y, z: 与 ``PointCloud.points`` / ``aabb_transform`` 一致的 world。
        aabb_transform: 4×4，**盒局部 → world**（与 ``pointcloud_aabb`` 一致）。
    """
    t = np.asarray(aabb_transform, dtype=np.float64)
    if t.shape != (4, 4):
        raise ValueError("aabb_transform 须为 4×4 矩阵")
    inv = np.linalg.inv(t)
    p = np.array([float(x), float(y), float(z), 1.0], dtype=np.float64)
    loc = inv @ p
    return (float(loc[0]), float(loc[1]), float(loc[2]))


def llh_to_aabb_local(
    lon: float,
    lat: float,
    alt: float,
    ref_lon: float,
    ref_lat: float,
    ref_alt: float,
    aabb_transform: Sequence[Sequence[float]],
) -> Tuple[float, float, float]:
    """WGS84 LLH → 先转 mission ENU world，再转 AABB 盒局部。"""
    e, n, u = llh_to_mission_enu(lon, lat, alt, ref_lon, ref_lat, ref_alt)
    return world_xyz_to_aabb_local(e, n, u, aabb_transform)
