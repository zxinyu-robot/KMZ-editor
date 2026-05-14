#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 随机 ROI 生成工具（由全范围生成子区域）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""
在数据集范围内随机划定子区域（ROI），用于在子区域内做航线规划，而非全局规划。

输入：TIF 或 GeoJSON（表示数据集全范围）
输出：一个随机子区域多边形 GeoJSON，仅在该区域内规划航线

用法（在项目根目录）：
    # 从 TIF 全范围中随机划一个约 30% 大小的子区域
    python3 backend/app/utils/path_editor/tools/random_roi_from_extent.py input.tif \\
        -o work_dir/test_outputs/roi.geojson --size-ratio 0.3

    # 从已有 GeoJSON 全范围中随机划子区域
    python3 backend/app/utils/path_editor/tools/random_roi_from_extent.py polygon.geojson \\
        -o work_dir/test_outputs/roi.geojson --size-ratio 0.25

    # 指定随机种子，便于复现
    python3 backend/app/utils/path_editor/tools/random_roi_from_extent.py polygon.geojson \\
        -o work_dir/test_outputs/roi.geojson --size-ratio 0.3 --seed 42

然后在该子区域内规划：
    python3 -m backend.app.utils.path_editor.cli work_dir/test_outputs/roi.geojson \\
        -o work_dir/kmz_exports/pathEdited.kmz --spacing 15
"""

import argparse
import json
import random
from pathlib import Path
from typing import List, Optional, Tuple

from .raster_extent import wgs84_axis_aligned_bounds_from_tif


def _bounds_from_geojson(geojson_path: Path) -> Tuple[float, float, float, float]:
    """从 GeoJSON 多边形提取外接矩形 (minx, miny, maxx, maxy)。"""
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    geom = data.get("geometry") or data
    if data.get("type") == "Feature":
        geom = data.get("geometry") or {}
    coords = []
    if geom.get("type") == "Polygon":
        ring = (geom.get("coordinates") or [[]])[0]
        coords = [(float(p[0]), float(p[1])) for p in ring if len(p) >= 2]
    elif geom.get("type") == "MultiPolygon":
        polys = geom.get("coordinates") or []
        if polys and polys[0]:
            ring = polys[0][0]
            coords = [(float(p[0]), float(p[1])) for p in ring if len(p) >= 2]
    if len(coords) < 3:
        raise ValueError(f"GeoJSON 中未找到有效多边形: {geojson_path}")
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return min(xs), min(ys), max(xs), max(ys)


def _bounds_from_tif(tif_path: Path) -> Tuple[float, float, float, float]:
    """从 TIF 读取外接矩形并重投影到 WGS84，返回 (min_lon, min_lat, max_lon, max_lat)。"""
    return wgs84_axis_aligned_bounds_from_tif(tif_path)


def random_roi_in_bounds(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    size_ratio: float = 0.3,
    seed: Optional[int] = None,
) -> List[Tuple[float, float]]:
    """
    在给定矩形范围内随机生成一个子矩形（ROI）。

    size_ratio: 子矩形边长占原范围的比例，例如 0.3 表示宽高各约 30%
    """
    if seed is not None:
        random.seed(seed)
    w = maxx - minx
    h = maxy - miny
    sub_w = w * size_ratio
    sub_h = h * size_ratio
    # 随机中心点，保证子矩形完全在范围内
    cx_min = minx + sub_w / 2
    cx_max = maxx - sub_w / 2
    cy_min = miny + sub_h / 2
    cy_max = maxy - sub_h / 2
    if cx_min >= cx_max or cy_min >= cy_max:
        # 范围太小，直接用中心附近的小矩形
        cx = (minx + maxx) / 2
        cy = (miny + maxy) / 2
        sub_w = min(sub_w, w * 0.9)
        sub_h = min(sub_h, h * 0.9)
    else:
        cx = random.uniform(cx_min, cx_max)
        cy = random.uniform(cy_min, cy_max)
    x0 = cx - sub_w / 2
    x1 = cx + sub_w / 2
    y0 = cy - sub_h / 2
    y1 = cy + sub_h / 2
    return [
        (x0, y0),
        (x1, y0),
        (x1, y1),
        (x0, y1),
        (x0, y0),
    ]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="在数据集范围内随机划定子区域（ROI），用于子区域内航线规划"
    )
    ap.add_argument(
        "input",
        help="输入：TIF 影像路径 或 GeoJSON 多边形路径（表示数据集全范围）",
    )
    ap.add_argument(
        "-o",
        "--output",
        required=True,
        help="输出 GeoJSON 路径（随机子区域多边形）",
    )
    ap.add_argument(
        "--size-ratio",
        type=float,
        default=0.3,
        help="子区域边长占全范围的比例，默认 0.3（约 30%%）",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子，便于复现",
    )
    args = ap.parse_args()

    inp = Path(args.input).resolve()
    if not inp.exists():
        raise FileNotFoundError(inp)

    out_path = Path(args.output).resolve()
    size_ratio = max(0.05, min(1.0, args.size_ratio))

    suf = inp.suffix.lower()
    if suf in (".tif", ".tiff"):
        minx, miny, maxx, maxy = _bounds_from_tif(inp)
    elif suf in (".geojson", ".json"):
        minx, miny, maxx, maxy = _bounds_from_geojson(inp)
    else:
        raise ValueError(
            f"不支持的文件格式，请使用 .tif / .tiff / .geojson / .json: {inp}"
        )

    coords = random_roi_in_bounds(
        minx, miny, maxx, maxy,
        size_ratio=size_ratio,
        seed=args.seed,
    )

    gj = {
        "type": "Feature",
        "properties": {"name": "random_roi", "size_ratio": size_ratio},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[list(pt) for pt in coords]],
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已生成随机子区域 GeoJSON: {out_path}")
    print(f"     范围比例: {size_ratio:.0%}，可直接用于 path_editor 在子区域内规划。")


if __name__ == "__main__":
    main()
