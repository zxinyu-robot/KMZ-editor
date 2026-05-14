# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 路径后处理 - 共线点剔除
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""后处理层：路径优化，剔除共线冗余点。"""

import numpy as np


def optimize_route_path(path_xy: np.ndarray, tol: float = 0.01) -> np.ndarray:
    """剔除共线冗余点，使用叉积判断三点共线。

    Args:
        path_xy: 路径点序列 (N, 2)，平面坐标。
        tol: 叉积容差，小于此值视为共线，默认 0.01。

    Returns:
        优化后的路径点序列。
    """
    if len(path_xy) <= 2:
        return path_xy
    out = [path_xy[0]]
    for i in range(1, len(path_xy) - 1):
        prev = path_xy[i - 1]
        curr = path_xy[i]
        next_pt = path_xy[i + 1]
        dx1 = curr[0] - prev[0]
        dy1 = curr[1] - prev[1]
        dx2 = next_pt[0] - curr[0]
        dy2 = next_pt[1] - curr[1]
        cross = abs(dx1 * dy2 - dy1 * dx2)
        if cross > tol:
            out.append(curr)
    out.append(path_xy[-1])
    return np.array(out)
