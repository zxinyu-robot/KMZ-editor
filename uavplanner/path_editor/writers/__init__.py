# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: Writers 聚合导出（模板构建与 KMZ 导出）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""写回器：canonical / 规划结果 → 模板空格（KML/WPML）。

实现位于 `output/kmz.py` 等；本包提供与工程要范 §七 `writers/` 对齐的 **聚合导出**。
"""

from ..output.kmz import (
    build_minimal_corridor_template,
    build_minimal_template_kml,
    build_minimal_waypoint_template,
    export_kmz,
)

__all__ = [
    "export_kmz",
    "build_minimal_template_kml",
    "build_minimal_waypoint_template",
    "build_minimal_corridor_template",
]
