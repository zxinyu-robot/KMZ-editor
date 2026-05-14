# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 圆柱 controls 转换（canonical -> CylinderParams）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""圆柱几何体：canonical → `CylinderParams`（算法控制量）。"""

from __future__ import annotations

from typing import Any, Dict

from ..params.schema import CylinderParams, parse_cylinder_params


def canonical_to_cylinder_params(canonical: Dict[str, Any]) -> CylinderParams:
    return parse_cylinder_params(canonical)
