# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: Canonical 聚合导出（slot/http -> canonical）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""Canonical 层：slot / HTTP 混写 → 单位统一、参考系一致、合法性裁剪。

不调用算法；可安全在 reader 之后、parse_polygon_params 之前调用。
"""

from . import mapping2d, cylinder

__all__ = ["mapping2d", "cylinder"]
