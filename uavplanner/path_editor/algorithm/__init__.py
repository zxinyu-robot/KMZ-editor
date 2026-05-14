# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 算法核心层 - 面状规划、几何体规划、斜面规划、贴近摄影规划
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""算法核心层：面状规划、几何体规划、斜面规划、贴近摄影规划。

对外接口：
- plan_polygon_route: 面状往复式扫线
- plan_cylinder_route: 几何体扫线
- plan_close_photography_route: 贴近摄影扫线
- plan_facade_route: 斜面扫线
"""

from typing import Optional

import numpy as np

from .polygon import plan_route as plan_polygon_route
from .cylinder import plan_cylinder_route, plan_cylinder_spiral, plan_cylinder_surface_sweep, plan_cylinder_local_path
from .corridor import plan_corridor_route, centerline_to_band_polygon_xy


def plan_close_photography_route(
    poly_xy: np.ndarray,
    spacing: float,
    direction_deg: float,
    start_xy: Optional[np.ndarray] = None,
    end_xy: Optional[np.ndarray] = None,
    longitudinal_spacing: Optional[float] = None,
) -> np.ndarray:
    """贴近摄影扫线入口（预留）。"""
    raise NotImplementedError("plan_close_photography_route 尚未在 algorithm 层实现。")


def plan_facade_route(
    centerline_xy: np.ndarray,
    half_width: float,
    lateral_spacing: float,
    baseline: Optional[float] = None,
    longitudinal_spacing: Optional[float] = None,
) -> np.ndarray:
    """斜面扫线入口（预留）。"""
    raise NotImplementedError("plan_facade_route 尚未在 algorithm 层实现。")


__all__ = [
    "plan_polygon_route",
    "plan_cylinder_route",
    "plan_cylinder_spiral",
    "plan_cylinder_surface_sweep",
    "plan_cylinder_local_path",
    "plan_close_photography_route",
    "plan_facade_route",
    "plan_corridor_route",
    "centerline_to_band_polygon_xy",
]
