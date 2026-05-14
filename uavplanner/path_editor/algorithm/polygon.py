# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 面状航线算法 - 平面栅格 + A*/D* Lite + Z 字形往复式扫线
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""面状航线算法：栅格地图、A*/D* 路径搜索、往复式扫线。"""

import heapq
import math
from typing import List, Tuple, Optional
import numpy as np

from ..geometry import heading_to_math_deg

def point_in_polygon(pt: Tuple[float, float], poly: np.ndarray) -> bool:
    """射线法判断点是否在多边形内。

    Args:
        pt: 待测点 (x, y)。
        poly: 多边形顶点数组 (N, 2)。

    Returns:
        点是否在多边形内部。
    """
    x, y = pt
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def xy_to_ij(xy: np.ndarray, xmin: float, ymin: float, d_grid: float, ny: int, nx: int) -> np.ndarray:
    """平面坐标 (x,y) 转栅格索引 (i,j)。"""
    j = int(round((xy[0] - xmin) / d_grid))
    i = int(round((xy[1] - ymin) / d_grid))
    return np.array([max(0, min(ny - 1, i)), max(0, min(nx - 1, j))])


def ij_to_xy(ij: np.ndarray, xmin: float, ymin: float, d_grid: float) -> np.ndarray:
    """栅格索引 (i,j) 转平面坐标 (x,y)。"""
    return np.array([xmin + ij[1] * d_grid, ymin + ij[0] * d_grid])


def nearest_free_ij(
    map_arr: np.ndarray, i0: int, j0: int
) -> Tuple[np.ndarray, bool]:
    """从 (i0,j0) 找最近的自由格（0=可通行）。"""
    ny, nx = map_arr.shape
    if map_arr[i0, j0] == 0:
        return np.array([i0, j0]), True
    for r in range(1, max(ny, nx) + 1):
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if abs(di) != r and abs(dj) != r:
                    continue
                i, j = i0 + di, j0 + dj
                if 0 <= i < ny and 0 <= j < nx and map_arr[i, j] == 0:
                    return np.array([i, j]), True
    return np.array([i0, j0]), False


def heuristic(a_ij: np.ndarray, b_ij: np.ndarray, d_grid: float) -> float:
    """D* 启发式。"""
    return d_grid * np.sqrt((a_ij[0] - b_ij[0]) ** 2 + (a_ij[1] - b_ij[1]) ** 2)


def _dstar_grid(
    map_arr: np.ndarray,
    start_ij: np.ndarray,
    goal_ij: np.ndarray,
    xmin: float, ymin: float, d_grid: float,
) -> Tuple[List, np.ndarray, bool]:
    """D* Lite 栅格搜索。"""
    ny, nx = map_arr.shape
    path_ij, path_xy, found = [], np.array([]), False
    si, sj = int(start_ij[0]), int(start_ij[1])
    gi, gj = int(goal_ij[0]), int(goal_ij[1])
    if map_arr[si, sj] == 1 or map_arr[gi, gj] == 1:
        return path_ij, path_xy, found

    dy = [-1, -1, -1, 0, 0, 1, 1, 1]
    dx = [-1, 0, 1, -1, 1, -1, 0, 1]
    cost_scale = [np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)]

    g = np.full((ny, nx), np.inf)
    rhs = np.full((ny, nx), np.inf)
    g[gi, gj] = rhs[gi, gj] = 0
    open_list = [[gi, gj, heuristic(np.array([si, sj]), np.array([gi, gj]), d_grid), 0]]

    while open_list:
        open_arr = np.array(open_list)
        idx = int(np.argmin(open_arr[:, 2] + 1e-6 * open_arr[:, 3]))
        u = open_list.pop(idx)
        i, j = int(u[0]), int(u[1])
        if i == si and j == sj and rhs[i, j] == g[i, j]:
            found = True
            break
        if g[i, j] <= rhs[i, j]:
            continue
        g[i, j] = rhs[i, j]
        for n in range(8):
            pi, pj = i - dy[n], j - dx[n]
            if pi < 0 or pi >= ny or pj < 0 or pj >= nx or map_arr[pi, pj] == 1:
                continue
            move_cost = cost_scale[n] * d_grid
            trhs = move_cost + g[i, j]
            if trhs < rhs[pi, pj]:
                rhs[pi, pj] = trhs
                k1 = rhs[pi, pj] + heuristic(np.array([pi, pj]), np.array([si, sj]), d_grid)
                open_list.append([pi, pj, k1, rhs[pi, pj]])

    if not found:
        return path_ij, path_xy, found

    path_ij = [[si, sj]]
    i, j = si, sj
    while i != gi or j != gj:
        best = np.inf
        next_ij = [i, j]
        for n in range(8):
            ni, nj = i + dy[n], j + dx[n]
            if ni < 0 or ni >= ny or nj < 0 or nj >= nx or map_arr[ni, nj] == 1:
                continue
            move_cost = cost_scale[n] * d_grid
            t = move_cost + g[ni, nj]
            if t < best:
                best, next_ij = t, [ni, nj]
        i, j = next_ij[0], next_ij[1]
        path_ij.append([i, j])
    path_ij = np.array(path_ij)
    path_xy = np.column_stack([xmin + path_ij[:, 1] * d_grid, ymin + path_ij[:, 0] * d_grid])
    return path_ij.tolist(), path_xy, found


def _astar_grid(
    map_arr: np.ndarray,
    start_ij: np.ndarray,
    goal_ij: np.ndarray,
    xmin: float, ymin: float, d_grid: float,
) -> Tuple[List, np.ndarray, bool]:
    """A* 栅格搜索。"""
    ny, nx = map_arr.shape
    si, sj = int(start_ij[0]), int(start_ij[1])
    gi, gj = int(goal_ij[0]), int(goal_ij[1])
    if map_arr[si, sj] == 1 or map_arr[gi, gj] == 1:
        return [], np.array([]), False

    dy = [-1, -1, -1, 0, 0, 1, 1, 1]
    dx = [-1, 0, 1, -1, 1, -1, 0, 1]
    cost_scale = [np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)]

    def h(i: int, j: int) -> float:
        return np.sqrt((i - gi) ** 2 + (j - gj) ** 2) * d_grid

    open_heap = []
    heapq.heappush(open_heap, (h(si, sj), 0.0, si, sj))
    g_score = np.full((ny, nx), np.inf)
    g_score[si, sj] = 0.0
    came_from = np.full((ny, nx, 2), -1, dtype=int)
    in_open = np.zeros((ny, nx), dtype=bool)
    in_open[si, sj] = True

    found = False
    while open_heap:
        f, g_curr, i, j = heapq.heappop(open_heap)
        in_open[i, j] = False
        if (i, j) == (gi, gj):
            found = True
            break
        if g_curr > g_score[i, j]:
            continue
        for n in range(8):
            ni, nj = i + dy[n], j + dx[n]
            if ni < 0 or ni >= ny or nj < 0 or nj >= nx or map_arr[ni, nj] == 1:
                continue
            move_cost = cost_scale[n] * d_grid
            tentative_g = g_curr + move_cost
            if tentative_g < g_score[ni, nj]:
                g_score[ni, nj] = tentative_g
                came_from[ni, nj] = [i, j]
                heapq.heappush(open_heap, (tentative_g + h(ni, nj), tentative_g, ni, nj))
                in_open[ni, nj] = True

    if not found:
        return [], np.array([]), False

    path_ij = []
    i, j = gi, gj
    path_ij.append([i, j])
    while not (i == si and j == sj):
        pi, pj = came_from[i, j]
        if pi < 0:
            break
        i, j = int(pi), int(pj)
        path_ij.append([i, j])
    path_ij = np.array(path_ij[::-1])
    path_xy = np.column_stack([xmin + path_ij[:, 1] * d_grid, ymin + path_ij[:, 0] * d_grid])
    return path_ij.tolist(), path_xy, True


def build_grid_map(
    poly_xy: np.ndarray,
    d_grid: float,
    obs_radius_scale: float = 0.0,
    obs_xy: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, float, float, float, float, int, int]:
    """构建栅格地图：0=可通行，1=障碍。"""
    xmin, ymin = poly_xy.min(axis=0)
    xmax, ymax = poly_xy.max(axis=0)
    xmin -= d_grid
    ymin -= d_grid
    xmax += d_grid
    ymax += d_grid
    xg = np.arange(xmin, xmax + 1e-9, d_grid)
    yg = np.arange(ymin, ymax + 1e-9, d_grid)
    nx, ny = len(xg), len(yg)
    grid_map = np.zeros((ny, nx))

    for i in range(ny):
        for j in range(nx):
            x = xmin + j * d_grid
            y = ymin + i * d_grid
            if not point_in_polygon((x, y), poly_xy):
                grid_map[i, j] = 1

    if obs_xy is not None and len(obs_xy) > 0 and obs_radius_scale > 0:
        obs_radius = obs_radius_scale * d_grid
        for k in range(len(obs_xy)):
            j = int(round((obs_xy[k, 0] - xmin) / d_grid))
            i = int(round((obs_xy[k, 1] - ymin) / d_grid))
            for di in range(-2, 4):
                for dj in range(-2, 4):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < ny and 0 <= jj < nx:
                        if (di * d_grid) ** 2 + (dj * d_grid) ** 2 <= obs_radius ** 2:
                            grid_map[ii, jj] = 1

    return grid_map, xmin, ymin, xmax, ymax, nx, ny


def plan_route(
    poly_xy: np.ndarray,
    spacing: float,
    direction_deg: float,
    start_xy: Optional[Tuple[float, float]] = None,
    end_xy: Optional[Tuple[float, float]] = None,
    obs_xy: Optional[np.ndarray] = None,
    obs_radius_scale: float = 1.5,
    longitudinal_spacing: Optional[float] = None,
) -> np.ndarray:
    """面状规划主入口：平面栅格 + A* 进场 + Z 字形往复式扫线。

    Args:
        poly_xy: 多边形顶点 (N, 2)，平面坐标（米），需已做 margin 预处理。
        spacing: 栅格等间距 (米)。
        direction_deg: 航线主方向 (度)，北=0，顺时针为正（不再按最长边重算）。
        start_xy: 可选起点。
        end_xy: 可选终点（未使用）。
        obs_xy: 可选障碍点 (M, 2)。
        obs_radius_scale: 障碍膨胀系数 * spacing。
        longitudinal_spacing: 沿航线采样间距 (米)，用于按航向重叠率增加中间航点；None 则不插值。

    Returns:
        航点序列 path_xy (K, 2)，平面坐标。
    """
    d_grid = spacing
    grid_map, xmin, ymin, xmax, ymax, nx, ny = build_grid_map(
        poly_xy, d_grid, obs_radius_scale, obs_xy
    )

    if start_xy is None:
        start_xy = (xmin + 1.5 * d_grid, ymin + 1.5 * d_grid)
    start_ij = xy_to_ij(np.array(start_xy[:2]), xmin, ymin, d_grid, ny, nx)
    if grid_map[start_ij[0], start_ij[1]] == 1:
        start_ij, _ = nearest_free_ij(grid_map, start_ij[0], start_ij[1])
        start_xy = tuple(ij_to_xy(start_ij, xmin, ymin, d_grid))

    poly_diffs = poly_xy - np.array(start_xy[:2])
    poly_dists = np.linalg.norm(poly_diffs, axis=1)
    nearest_idx = int(np.argmin(poly_dists))
    nearest_xy = poly_xy[nearest_idx]
    nearest_ij = xy_to_ij(nearest_xy, xmin, ymin, d_grid, ny, nx)
    if grid_map[nearest_ij[0], nearest_ij[1]] == 1:
        nearest_ij, _ = nearest_free_ij(grid_map, nearest_ij[0], nearest_ij[1])
        nearest_xy = ij_to_xy(nearest_ij, xmin, ymin, d_grid)

    route_full = [np.array(start_xy)]
    current_ij = xy_to_ij(np.array(start_xy[:2]), xmin, ymin, d_grid, ny, nx)
    if grid_map[current_ij[0], current_ij[1]] == 1:
        current_ij, _ = nearest_free_ij(grid_map, current_ij[0], current_ij[1])

    _, seg_xy, found_lead = _astar_grid(
        grid_map, current_ij, nearest_ij, xmin, ymin, d_grid
    )
    if found_lead and len(seg_xy) > 0:
        route_full.extend(seg_xy[1:].tolist())
    else:
        route_full.append(nearest_xy.copy())
    current_ij = nearest_ij.copy()

    # 方向语义统一：输入 direction 为 heading（北0顺时针），算法旋转使用数学角（东0逆时针）
    direction_math_deg = heading_to_math_deg(direction_deg)
    theta = -np.deg2rad(direction_math_deg)
    cos_t, sin_t = np.cos(theta), np.sin(theta)

    def rotate_xy(xy: np.ndarray) -> np.ndarray:
        x, y = xy[..., 0], xy[..., 1]
        return np.stack([cos_t * x - sin_t * y, sin_t * x + cos_t * y], axis=-1)

    def inv_rotate_xy(xy_r: np.ndarray) -> np.ndarray:
        xr, yr = xy_r[..., 0], xy_r[..., 1]
        return np.stack([cos_t * xr + sin_t * yr, -sin_t * xr + cos_t * yr], axis=-1)

    poly_r = rotate_xy(poly_xy)
    y_min, y_max = float(poly_r[:, 1].min()), float(poly_r[:, 1].max())
    if y_max - y_min < 1e-6:
        return np.array(route_full)

    margin = 0.1 * d_grid
    y_start = y_min + margin
    y_end = y_max - margin
    if y_end <= y_start:
        y_start, y_end = y_min, y_max
    n_lines = int(np.floor((y_end - y_start) / d_grid)) + 1

    def scanline_segments(poly: np.ndarray, y: float, eps: float = 1e-9):
        """扫描线与多边形交段（半开区间规则，避免顶点重复计数）。"""
        xs: List[float] = []
        n_poly_local = len(poly)
        for i in range(n_poly_local):
            p1 = poly[i]
            p2 = poly[(i + 1) % n_poly_local]
            x1, y1 = float(p1[0]), float(p1[1])
            x2, y2 = float(p2[0]), float(p2[1])
            # 忽略水平边，避免重复交点
            if abs(y2 - y1) <= eps:
                continue
            # 半开区间规则：[min, max)，防止命中顶点时被相邻两边重复计数
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1)
                xs.append(x1 + t * (x2 - x1))
        if not xs:
            return []
        xs.sort()
        # 去除近重合交点，增强数值稳定性
        uniq_xs: List[float] = []
        for x in xs:
            if not uniq_xs or abs(x - uniq_xs[-1]) > eps:
                uniq_xs.append(x)
        segs: List[Tuple[np.ndarray, np.ndarray]] = []
        if len(uniq_xs) < 2:
            return segs
        pair_cnt = len(uniq_xs) // 2
        for i in range(pair_cnt):
            xa = uniq_xs[2 * i]
            xb = uniq_xs[2 * i + 1]
            if xb - xa <= eps:
                continue
            segs.append(
                (
                    np.array([xa, y], dtype=float),
                    np.array([xb, y], dtype=float),
                )
            )
        return segs

    path_inside_r: list = []
    n_poly = len(poly_r)
    for idx_line in range(n_lines):
        y = y_start + idx_line * d_grid
        segs = scanline_segments(poly_r, y)
        if not segs:
            continue
        for seg_i, (seg_a, seg_b) in enumerate(segs):
            p_start, p_end = seg_a, seg_b
            if idx_line % 2 == 1:
                p_start, p_end = p_end, p_start
            if not path_inside_r:
                path_inside_r.append(p_start.tolist())
            else:
                path_inside_r.append(p_start.tolist())
            # 按 longitudinal_spacing 沿航线插值，增加中间航点
            if longitudinal_spacing and longitudinal_spacing > 0:
                seg_vec = p_end - p_start
                seg_len = float(np.linalg.norm(seg_vec))
                if seg_len > longitudinal_spacing:
                    n_inter = int(seg_len / longitudinal_spacing)
                    for i in range(1, n_inter + 1):
                        t = i * longitudinal_spacing / seg_len
                        pt = p_start + t * seg_vec
                        path_inside_r.append(pt.tolist())
            path_inside_r.append(p_end.tolist())

    if path_inside_r:
        inside_xy = inv_rotate_xy(np.array(path_inside_r))
        if route_full:
            last = route_full[-1]
            if np.linalg.norm(inside_xy[0] - last) < 1e-6:
                route_full.extend(inside_xy[1:].tolist())
            else:
                route_full.extend(inside_xy.tolist())

    return np.array(route_full)
