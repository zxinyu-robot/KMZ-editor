# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 几何输入层 - 多边形经纬度转平面坐标
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-03
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""几何输入层：多边形经纬度 → 平面坐标、转换函数。"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np

from .coordinates import ll_to_xy_func, xy_to_ll_func


@dataclass
class PolygonGeometry:
    """面状航线几何输入：平面坐标多边形与转换函数。"""

    poly_xy: np.ndarray  # (N, 2) 平面坐标 (米)
    xy2ll: Callable[[float, float], Tuple[float, float]]  # 平面 → 经纬度
    start_xy: Optional[Tuple[float, float]] = None
    end_xy: Optional[Tuple[float, float]] = None


def prepare_polygon(
    polygon_ll: List[Tuple[float, float]],
    start_ll: Optional[Tuple[float, float]] = None,
    end_ll: Optional[Tuple[float, float]] = None,
) -> PolygonGeometry:
    """将经纬度多边形转为平面坐标，供算法层使用。

    Args:
        polygon_ll: 多边形顶点 [(lon, lat), ...]。
        start_ll: 可选起点 (lon, lat)。
        end_ll: 可选终点 (lon, lat)。

    Returns:
        PolygonGeometry，含 poly_xy、xy2ll、start_xy、end_xy。
    """
    ref_lon, ref_lat = polygon_ll[0]
    ll2xy = ll_to_xy_func(ref_lon, ref_lat)
    xy2ll = xy_to_ll_func(ref_lon, ref_lat)

    poly_xy = np.array([ll2xy(lon, lat) for lon, lat in polygon_ll])
    start_xy = ll2xy(*start_ll) if start_ll else None
    end_xy = ll2xy(*end_ll) if end_ll else None

    return PolygonGeometry(poly_xy=poly_xy, xy2ll=xy2ll, start_xy=start_xy, end_xy=end_xy)
