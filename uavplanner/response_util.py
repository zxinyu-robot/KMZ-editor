# -*- coding: utf-8 -*-
"""path_editor / 规划失败时的统一 JSON 结构（自原工程拆出，供 api 使用）。"""

from __future__ import annotations

from typing import Any, List


def path_editor_plan_fail(message: str, *, segment_start_indices: List[int] | None = None) -> dict[str, Any]:
    """返回与成功分支对齐的失败载荷（空航点 + 错误文案）。"""
    seg: List[int] = list(segment_start_indices) if segment_start_indices is not None else []
    return {
        "waypoints": [],
        "count": 0,
        "segment_start_indices": seg,
        "error": str(message),
    }
