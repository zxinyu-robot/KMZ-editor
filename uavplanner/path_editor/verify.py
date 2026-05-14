#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: path_editor 验证与 KMZ 预览脚本
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""
path_editor 官方验证与预览脚本（测试节点）

功能定位：快速算法验证与 KMZ 可视化。覆盖面状（基础/相机+margin+优化）与圆柱两种规划，
使用固定测试多边形，不依赖外部数据。与 test/test_percise.py 的区别：本脚本专注「验证通过与否」；
test_percise 为专项仿真，支持 GeoJSON 中心解析、参数化仿真、航程统计、结果持久化。

两种模式：
  1. 验证模式（无参数）：运行算法测试，可选 -o 生成 4 子图预览
  2. 预览模式（传入 KMZ）：解析 KMZ 中的多边形和航线，生成单图预览

用法:
  python3 -m backend.app.utils.path_editor.verify                    # 仅验证
  python3 -m backend.app.utils.path_editor.verify -o out.png         # 验证 + 生成 4 子图
  python3 -m backend.app.utils.path_editor.verify path.kmz -o out.png # 预览 KMZ
  python3 -m backend.app.utils.path_editor.verify path.kmz           # 预览，输出 path.png

若 matplotlib 报错，可尝试: .venv/bin/python -m backend.app.utils.path_editor.verify ...
"""

import argparse
from pathlib import Path

import numpy as np

from .io import parse_polygon_from_kmz, parse_waypoints_from_kmz


def _polygon_ndarray(kmz_path: Path) -> np.ndarray:
    """从 KMZ 解析多边形，返回 (n,2) ndarray。"""
    pts = parse_polygon_from_kmz(str(kmz_path))
    return np.array(pts) if pts else np.empty((0, 2))


def _waypoints_ndarray(kmz_path: Path) -> np.ndarray:
    """从 KMZ 解析航点，返回 (n,2) ndarray（lon, lat）。"""
    pts = parse_waypoints_from_kmz(str(kmz_path))
    if not pts:
        return np.empty((0, 2))
    return np.array(pts)[:, :2]


# -----------------------------------------------------------------------------
# 绘图工具
# -----------------------------------------------------------------------------


def _init_mpl():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans", "sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False
        return plt
    except (ImportError, AttributeError) as e:
        print(f"⚠ 可视化失败: {e}。可尝试: .venv/bin/python ...")
        return None


def _plot_route_on_ax(ax, polygon_ll: np.ndarray, waypoints: np.ndarray, title: str):
    """在 ax 上绘制多边形 + 航线。"""
    if polygon_ll.size > 0:
        poly_closed = np.vstack([polygon_ll, polygon_ll[0:1]])
        ax.fill(poly_closed[:, 0], poly_closed[:, 1], color=[0.7, 0.85, 1.0], alpha=0.35,
                edgecolor=[0.2, 0.5, 0.9], linewidth=1.5, label="Survey area")
    if waypoints.size > 0:
        wp = waypoints[:, :2] if waypoints.shape[1] >= 2 else waypoints
        ax.plot(wp[:, 0], wp[:, 1], "o-", color="green", markersize=4, linewidth=1.8,
                markerfacecolor=[0, 0.8, 0.3], markeredgecolor="none", label="Route")
        ax.plot(wp[0, 0], wp[0, 1], "o", markersize=10, color="red", label="Start")
        ax.plot(wp[-1, 0], wp[-1, 1], "s", markersize=8, color="orange", label="End")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title)
    ax.axis("equal")
    ax.grid(True)
    ax.legend(loc="best")


def _plot_kmz_preview(kmz_path: Path, out_path: Path) -> bool:
    """KMZ 预览模式：单图。"""
    plt = _init_mpl()
    if plt is None:
        return False
    polygon_ll = _polygon_ndarray(kmz_path)
    waypoints = _waypoints_ndarray(kmz_path)
    fig, ax = plt.subplots(figsize=(10, 8), facecolor="white")
    _plot_route_on_ax(ax, polygon_ll, waypoints, f"KMZ Route Preview ({kmz_path.name})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] 预览图已保存: {out_path}")
    return True


def _plot_verify_results(poly, r_basic, r_camera, r_cylinder, out_path: Path) -> bool:
    """验证模式：4 子图。"""
    plt = _init_mpl()
    if plt is None:
        return False
    fig = plt.figure(figsize=(14, 10), facecolor="white")

    for idx, (title, waypoints) in enumerate([
        (f"面状-基础 ({r_basic.get('count', 0)} 航点)", r_basic.get("waypoints")),
        (f"面状-相机+margin+优化 ({r_camera.get('count', 0)} 航点)", r_camera.get("waypoints")),
        (f"圆柱 俯视 ({r_cylinder.get('count', 0)} 航点)", r_cylinder.get("waypoints")),
    ]):
        ax = fig.add_subplot(2, 2, idx + 1)
        poly_arr = np.array(poly) if poly else np.empty((0, 2))
        wp_arr = np.array(waypoints)[:, :2] if waypoints else np.empty((0, 2))
        if idx == 2:
            poly_arr = np.empty((0, 2))
        _plot_route_on_ax(ax, poly_arr, wp_arr, title)

    ax4 = fig.add_subplot(2, 2, 4, projection="3d")
    if r_cylinder.get("waypoints"):
        wp = np.array(r_cylinder["waypoints"])
        ax4.plot(wp[:, 0], wp[:, 1], wp[:, 2], "o-", color="purple", markersize=2,
                linewidth=0.8, markerfacecolor=[0.6, 0.4, 0.9], markeredgecolor="none")
        ax4.scatter(wp[0, 0], wp[0, 1], wp[0, 2], c="red", s=80, label="Start")
        ax4.scatter(wp[-1, 0], wp[-1, 1], wp[-1, 2], c="orange", s=60, label="End")
    ax4.set_title("圆柱 螺旋线 3D")
    ax4.set_xlabel("Longitude")
    ax4.set_ylabel("Latitude")
    ax4.set_zlabel("Height (m)")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n[OK] 可视化已保存: {out_path}")
    return True


# -----------------------------------------------------------------------------
# 主逻辑
# -----------------------------------------------------------------------------


def run_verify_mode(args) -> None:
    """运行算法验证。"""
    from .api import plan_polygon, plan_cylinder

    print("=" * 50)
    print("path_editor 算法验证")
    print("=" * 50)

    poly = [[104.0, 30.0], [104.01, 30.0], [104.01, 30.01], [104.0, 30.01]]

    r_basic = plan_polygon(poly, {"spacing": 20, "height": 80, "use_camera": False})  # 固定 20m 间距
    status = "OK" if r_basic["error"] is None else "FAIL"
    print(f"\n[面状-基础] {status} - {r_basic['count']} 个航点")
    if r_basic["error"]:
        print(f"  错误: {r_basic['error']}")
    elif r_basic["waypoints"]:
        print(f"  首点: {r_basic['waypoints'][0]}")

    r_camera = plan_polygon(poly, {
        "use_camera": True, "camera_preset": "m3e", "height": 80,
        "overlap_lateral": 0.7, "margin": 2, "optimize_path": True,
    })
    status = "OK" if r_camera["error"] is None else "FAIL"
    print(f"[面状-相机+margin+优化] {status} - {r_camera['count']} 个航点")

    r_cylinder = plan_cylinder({
        "center_ll": [104.0, 30.0], "radius": 10, "height": 50,
        "pitch": 5, "points_per_rev": 24,
    })
    status = "OK" if r_cylinder["error"] is None else "FAIL"
    print(f"\n[圆柱] {status} - {r_cylinder['count']} 个航点")
    if r_cylinder["error"]:
        print(f"  错误: {r_cylinder['error']}")
    elif r_cylinder["waypoints"]:
        print(f"  首点: {r_cylinder['waypoints'][0]}, 末点: {r_cylinder['waypoints'][-1]}")

    print("\n" + "=" * 50)
    print("验证完成")
    print("=" * 50)

    if args.output:
        _plot_verify_results(poly, r_basic, r_camera, r_cylinder, Path(args.output).resolve())


def run_preview_mode(kmz_path: Path, out_path: Path) -> None:
    """KMZ 预览模式。"""
    _plot_kmz_preview(kmz_path, out_path)


def main():
    ap = argparse.ArgumentParser(
        description="path_editor 验证与 KMZ 预览",
        epilog="无 KMZ 时运行算法验证；传入 KMZ 时预览其航线。",
    )
    ap.add_argument("kmz", nargs="?", default=None, help="可选：KMZ 文件路径（预览模式）")
    ap.add_argument("-o", "--output", default=None, help="输出 PNG 路径")
    args = ap.parse_args()

    if args.kmz:
        kmz_path = Path(args.kmz).resolve()
        if not kmz_path.exists():
            print(f"错误: 文件不存在 {kmz_path}")
            sys.exit(1)
        out_path = Path(args.output).resolve() if args.output else kmz_path.with_suffix(".png")
        run_preview_mode(kmz_path, out_path)
    else:
        run_verify_mode(args)


if __name__ == "__main__":
    main()
