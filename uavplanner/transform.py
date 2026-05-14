# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 经纬度与局部平面 XY 互转（委托 path_editor.geometry.coordinates）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""经纬度 <-> 平面 XY（米）。

实现统一委托给 ``path_editor.geometry.coordinates.build_ll_xy_transform``，
避免与几何层重复维护 UTM/pyproj 与等距退化逻辑。

用法（兼容旧接口）::

    ll_to_xy, xy_to_ll = build_ll_to_xy_funcs(las_crs, ref_lat, ref_lon)
    x, y = ll_to_xy((lon, lat))
    lon, lat = xy_to_ll((x, y))
"""

from typing import Callable, Tuple, Union

from uavplanner.path_editor.geometry.coordinates import build_ll_xy_transform


def build_ll_to_xy_funcs(
    las_crs: str | None,
    ref_lat: float | None,
    ref_lon: float | None,
) -> Tuple[
    Callable[[Union[tuple, list]], Tuple[float, float]],
    Callable[[Union[tuple, list]], Tuple[float, float]],
]:
    """构建 WGS84 经纬度与平面 XY（米）互转函数。

    Args:
        las_crs: 目标投影 CRS（如 ``EPSG:3857``）；为空或仅空白时由 ``build_ll_xy_transform``
            按参考点自动选 UTM（与几何层一致）。
        ref_lat, ref_lon: 参考点纬度、经度（度）；局部退化路径需要；为 ``None`` 时用 ``0.0``
            占位（与旧实现在未走 pyproj 分支时对 ``None`` 的行为相比，仅影响退化路径）。

    Returns:
        ``(ll_to_xy, xy_to_ll)``，二者参数均为 ``(lon, lat)`` 或 ``(x, y)`` 序列。
    """
    rl = float(ref_lon) if ref_lon is not None else 0.0
    rt = float(ref_lat) if ref_lat is not None else 0.0
    crs = las_crs.strip() if isinstance(las_crs, str) and las_crs.strip() else None
    ll2xy, xy2ll = build_ll_xy_transform(rl, rt, crs)

    def ll_to_xy(point: Union[tuple, list]) -> Tuple[float, float]:
        lon_deg = float(point[0])
        lat_deg = float(point[1])
        x, y = ll2xy(lon_deg, lat_deg)
        return (float(x), float(y))

    def xy_to_ll(point: Union[tuple, list]) -> Tuple[float, float]:
        x_m = float(point[0])
        y_m = float(point[1])
        lon, lat = xy2ll(x_m, y_m)
        return (float(lon), float(lat))

    return ll_to_xy, xy_to_ll
