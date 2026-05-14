# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 圆柱参数 canonical 化（cylinder）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""圆柱几何体：参数字典 canonical 化（类型与基本范围）。"""

from __future__ import annotations

from typing import Any, Dict, Tuple


def normalize_cylinder_params(raw: Dict[str, Any]) -> Dict[str, Any]:
    """返回新 dict：center_ll、数值字段转 float/int，未知键原样透传若已在白名单外由上层过滤。"""
    out: Dict[str, Any] = dict(raw)
    cl = out.get("center_ll")
    if cl is not None and isinstance(cl, (list, tuple)) and len(cl) >= 2:
        try:
            out["center_ll"] = (float(cl[0]), float(cl[1]))
        except (TypeError, ValueError):
            pass
    for k in ("radius", "height", "pitch", "start_z", "flight_height", "flight_speed", "reference_time"):
        if k in out and out[k] is not None:
            try:
                out[k] = float(out[k])
            except (TypeError, ValueError):
                pass
    if "points_per_rev" in out and out["points_per_rev"] is not None:
        try:
            out["points_per_rev"] = int(out["points_per_rev"])
        except (TypeError, ValueError):
            pass
    gm = out.get("geometry_mode")
    if isinstance(gm, str):
        out["geometry_mode"] = gm.strip().lower() or "surface_sweep"
    hl = out.get("home_ll")
    if hl is not None and isinstance(hl, (list, tuple)) and len(hl) >= 2:
        try:
            out["home_ll"] = (float(hl[0]), float(hl[1]))
        except (TypeError, ValueError):
            pass
    out["append_centroid"] = bool(out.get("append_centroid", False))
    out["with_timestamps"] = bool(out.get("with_timestamps", False))
    return out
