# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 圆柱题型 slot 定义与参数白名单
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""圆柱体几何航线（圆柱绕飞）参数白名单与题型标识。

算法实现位于 `path_editor.algorithm.cylinder`；本模块仅做 **slot/协议层** 约束。
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, List, Mapping, Tuple

TEMPLATE_KIND = "cylinder_geometry"
SLOT_VERSION = "v1"


class CylinderSlotCategory(str, Enum):
    HARD = "hard"
    STRATEGY = "strategy"


# 与 `CylinderParams` / HTTP 入参对齐的允许键（非 Pxx 体系，用几何参数字典）
ALLOWED_PARAM_KEYS: FrozenSet[str] = frozenset(
    {
        "center_ll",
        "radius",
        "height",
        "pitch",
        "start_z",
        "points_per_rev",
        "flight_height",
        "geometry_mode",
        "home_ll",
        "append_centroid",
        "with_timestamps",
        "flight_speed",
        "reference_time",
    }
)

REQUIRED_FOR_PLAN: FrozenSet[str] = frozenset({"center_ll", "radius", "height", "pitch"})


def validate_cylinder_keys(params: Mapping[str, object]) -> Tuple[bool, List[str]]:
    """未知键拒绝（便于及早发现拼写错误）。"""
    bad = [k for k in params if k not in ALLOWED_PARAM_KEYS]
    return len(bad) == 0, bad
