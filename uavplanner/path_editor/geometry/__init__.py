# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 几何输入层 - 坐标系转换、几何预处理
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""几何输入层：坐标系转换、几何预处理。

对外接口：
- prepare_polygon: 多边形经纬度 → 平面坐标（几何输入层入口）
- ll_to_xy_func, xy_to_ll_func: WGS84 <-> 平面米坐标
- geod_distance, path_length_m: 大地线距离、航程
"""

from .coordinates import (
    WGS84,
    ll_to_xy_func,
    xy_to_ll_func,
    build_ll_xy_transform,
    build_llh_enu_transform,
    geod_distance,
    path_length_m,
    segment_lengths_m,
    infer_sweep_segment_starts,
)
from .spatial_math import (
    deg2rad,
    rad2deg,
    normalize_angle_deg,
    normalize_delta_deg,
    heading_to_math_deg,
    math_to_heading_deg,
    bearing_deg,
    distance_2d_m,
    project_point_by_heading,
    rotate_xy,
    polygon_area_signed,
    is_clockwise,
)
from .prepare import PolygonGeometry, prepare_polygon
from .dsm import load_dsm, apply_dsm_to_waypoints, sample_dsm_at
from .safety import (
    octant_check_segment,
    check_route_safety,
    build_route_buffer_3d,
)

__all__ = [
    "WGS84",
    "ll_to_xy_func",
    "xy_to_ll_func",
    "build_ll_xy_transform",
    "build_llh_enu_transform",
    "geod_distance",
    "path_length_m",
    "segment_lengths_m",
    "infer_sweep_segment_starts",
    "deg2rad",
    "rad2deg",
    "normalize_angle_deg",
    "normalize_delta_deg",
    "heading_to_math_deg",
    "math_to_heading_deg",
    "bearing_deg",
    "distance_2d_m",
    "project_point_by_heading",
    "rotate_xy",
    "polygon_area_signed",
    "is_clockwise",
    "PolygonGeometry",
    "prepare_polygon",
    "load_dsm",
    "apply_dsm_to_waypoints",
    "sample_dsm_at",
    "octant_check_segment",
    "check_route_safety",
    "build_route_buffer_3d",
]
