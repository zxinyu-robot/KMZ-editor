# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 仿地参数 - F-011 surfaceFollowModeEnable、surfaceRelativeHeight
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-09
# ------------------------------------------------------------ #

"""仿地参数：对应 wpml:waylineCoordinateSysParam 中的仿地相关字段。"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SurfaceFollowParams:
    """仿地参数。"""

    surface_follow_enable: bool = False  # surfaceFollowModeEnable: 0 | 1
    surface_relative_height: float = 100.0  # 相对地表高度 (m)
    is_realtime_surface_follow: bool = False  # 实时仿地（M3E/M3T 等）


def parse_surface_follow_params(params: Optional[Dict[str, Any]] = None) -> SurfaceFollowParams:
    """从字典解析仿地参数。"""
    cfg = SurfaceFollowParams()
    if not params:
        return cfg
    mapping = {
        "surface_follow_enable": "surface_follow_enable",
        "surfaceFollowModeEnable": "surface_follow_enable",
        "surface_relative_height": "surface_relative_height",
        "surfaceRelativeHeight": "surface_relative_height",
        "is_realtime_surface_follow": "is_realtime_surface_follow",
        "isRealtimeSurfaceFollow": "is_realtime_surface_follow",
    }
    for k, attr in mapping.items():
        v = params.get(k)
        if v is None:
            continue
        if attr == "surface_follow_enable" or attr == "is_realtime_surface_follow":
            cfg_val = bool(v) if isinstance(v, bool) else (str(v).strip() in ("1", "true", "yes"))
            setattr(cfg, attr, cfg_val)
        elif attr == "surface_relative_height":
            try:
                setattr(cfg, attr, float(v))
            except (TypeError, ValueError):
                pass
    return cfg
