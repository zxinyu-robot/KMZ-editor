# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 面状 controls 转换（canonical -> PolygonParams）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""面状：canonical 字典 → `PolygonParams` → pipeline 控制量。"""

from __future__ import annotations

from typing import Any, Dict

from ..params.schema import PolygonParams, parse_polygon_params


def canonical_to_polygon_params(canonical: Dict[str, Any]) -> PolygonParams:
    """与 `parse_polygon_params` 一致；入口显式归属 controls 层。"""
    return parse_polygon_params(canonical)


def polygon_params_to_algo_controls(p: PolygonParams) -> Dict[str, Any]:
    """`pipeline.edit_route` / 规划内核使用的关键字参数。"""
    return p.to_edit_route_kwargs()
