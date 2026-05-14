# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 规划参数层 - 相机预设、间距计算、多边形内缩
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""规划参数层：配置(config)、解析(resolver)、模型(schema)。

- config: 相机预设、间距计算、多边形内缩底层
- resolver: 参数解析（resolve_spacing、apply_margin）
- schema: PolygonParams、CylinderParams、parse_* 统一入口
"""

from .config import CAMERA_PRESETS, calculate_spacing, calculate_gsd_cm_per_px, shrink_polygon
from .resolver import resolve_spacing, resolve_longitudinal_spacing, apply_margin, merge_planning_params
from .schema import (
    PolygonParams,
    CylinderParams,
    CorridorParams,
    parse_polygon_params,
    parse_cylinder_params,
    parse_corridor_params,
)
from .mission_config import MissionConfig, parse_mission_config
from .surface_follow import SurfaceFollowParams, parse_surface_follow_params

__all__ = [
    "CAMERA_PRESETS",
    "calculate_spacing",
    "calculate_gsd_cm_per_px",
    "resolve_spacing",
    "resolve_longitudinal_spacing",
    "apply_margin",
    "merge_planning_params",
    "shrink_polygon",
    "PolygonParams",
    "CylinderParams",
    "parse_polygon_params",
    "parse_cylinder_params",
    "parse_corridor_params",
    "CorridorParams",
    "MissionConfig",
    "parse_mission_config",
    "SurfaceFollowParams",
    "parse_surface_follow_params",
]
