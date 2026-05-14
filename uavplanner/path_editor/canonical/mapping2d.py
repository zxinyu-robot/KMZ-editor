# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 面状参数 canonical 化（mapping2d）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""面状 mapping2d：原始参数字典 → canonical（与 `PolygonParams` / merge 键兼容）。"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _rate_0_to_1(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x > 1.0:
        x = x / 100.0
    return max(0.0, min(1.0, x))


def normalize_mapping2d_params(raw: Dict[str, Any]) -> Dict[str, Any]:
    """对已与 reader 合并的平面 dict 做数值规范化（不删键）。"""
    out = dict(raw)
    if "direction" in out and out["direction"] is not None:
        try:
            out["direction"] = float(out["direction"]) % 360.0
        except (TypeError, ValueError):
            pass
    for k in ("overlap_lateral", "overlap_longitudinal"):
        if k in out:
            r = _rate_0_to_1(out.get(k))
            if r is not None:
                out[k] = r
    return out
