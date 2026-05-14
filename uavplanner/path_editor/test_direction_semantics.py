#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 方向语义回归测试脚本（path_editor）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""方向语义回归测试（可直接 python3 执行）。"""

from collections import Counter

from .api import plan_polygon
from .geometry import heading_to_math_deg, bearing_deg


def _dominant_bearing_bins(waypoints):
    bins = []
    for i in range(1, len(waypoints)):
        b = bearing_deg((waypoints[i - 1][0], waypoints[i - 1][1]), (waypoints[i][0], waypoints[i][1]))
        bins.append(int(round(b / 10.0)) * 10 % 360)
    return Counter(bins)


def _assert_close(a, b, tol=1e-6):
    if abs(a - b) > tol:
        raise AssertionError(f"{a} != {b} (tol={tol})")


def run_tests():
    # 角度映射：heading(北0顺时针) <-> math(东0逆时针)
    _assert_close(heading_to_math_deg(0), 90.0)
    _assert_close(heading_to_math_deg(90), 0.0)
    _assert_close(heading_to_math_deg(180), 270.0)

    poly = [
        [116.0, 39.0],
        [116.002, 39.0],
        [116.002, 39.002],
        [116.0, 39.002],
        [116.0, 39.0],
    ]
    common = {
        "height": 100.0,
        "spacing": 30.0,
        "use_camera": False,
        "overlap_lateral": 0.7,
        "overlap_longitudinal": 0.8,
        "optimize_path": False,
    }
    r0 = plan_polygon(poly, {**common, "direction": 0})
    r90 = plan_polygon(poly, {**common, "direction": 90})
    if r0.get("error") or r90.get("error"):
        raise AssertionError(f"plan_polygon failed: {r0.get('error')} | {r90.get('error')}")

    c0 = _dominant_bearing_bins(r0.get("waypoints") or [])
    c90 = _dominant_bearing_bins(r90.get("waypoints") or [])
    # direction=0 期望主扫线接近南北向（0/180）；direction=90 期望主扫线接近东西向（90/270）
    major0 = (c0[0] + c0[180]) > (c0[90] + c0[270])
    major90 = (c90[90] + c90[270]) > (c90[0] + c90[180])
    if not (major0 and major90):
        raise AssertionError(f"direction semantics mismatch: c0={c0}, c90={c90}")

    # 面状默认应去掉扫线中的共线中间点；显式 optimize_path=false 时保留原始插值点。
    dense_params = {
        "height": 100.0,
        "spacing": 30.0,
        "use_camera": False,
        "overlap_lateral": 0.7,
        "overlap_longitudinal": 0.8,
        "direction": 0,
    }
    r_trimmed = plan_polygon(poly, dense_params)
    r_untrimmed = plan_polygon(poly, {**dense_params, "optimize_path": False})
    if r_trimmed.get("error") or r_untrimmed.get("error"):
        raise AssertionError(
            f"plan_polygon optimize_path regression failed: {r_trimmed.get('error')} | {r_untrimmed.get('error')}"
        )
    trimmed_waypoints = r_trimmed.get("waypoints") or []
    untrimmed_waypoints = r_untrimmed.get("waypoints") or []
    if len(trimmed_waypoints) >= len(untrimmed_waypoints):
        raise AssertionError(
            f"optimize_path should remove intermediate collinear waypoints: trimmed={len(trimmed_waypoints)}, "
            f"untrimmed={len(untrimmed_waypoints)}"
        )


if __name__ == "__main__":
    run_tests()
    print("ok")

