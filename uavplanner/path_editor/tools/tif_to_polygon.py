#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: TIF 外接矩形转测区多边形（GeoJSON）工具
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""
小工具：从 TIF 影像生成测区多边形（GeoJSON），用于配合 `path_editor` CLI 做航线规划测试。

设计目标：
- 尽量简单、健壮，不做复杂影像分析；
- 先支持「用影像外接矩形」作为测区多边形（足够测试算法逻辑）；
- 若影像是投影坐标系，尝试自动重投影到 WGS84 (EPSG:4326)。

依赖：
- rasterio  (如果未安装：pip install rasterio)

用法示例（在项目根目录）：
    python3 backend/app/utils/path_editor/tools/tif_to_polygon.py /path/to/input.tif \\
        -o work_dir/test_outputs/polygon.geojson

然后即可调用 path_editor 做航线规划：
    python3 -m backend.app.utils.path_editor.cli work_dir/test_outputs/polygon.geojson \\
        -o work_dir/kmz_exports/pathEdited.kmz --spacing 15
"""

import argparse
import json
from pathlib import Path
from typing import List, Tuple

from .raster_extent import load_tif_bounds_and_crs, reproject_bounds_corners_to_wgs84_lonlat


def polygon_to_geojson(coords_ll: List[Tuple[float, float]], name: str = "") -> dict:
    """
    将经纬度多边形封装为 GeoJSON Feature。
    """
    # GeoJSON 要求 Polygon coordinates 为 [[[lon, lat], ...]]
    return {
        "type": "Feature",
        "properties": {
            "name": name or "tif_extent",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[list(pt) for pt in coords_ll]],
        },
    }


def main():
    ap = argparse.ArgumentParser(
        description="从 TIF 影像外接矩形生成测区多边形（GeoJSON），用于 path_editor 测试"
    )
    ap.add_argument("tif", help="输入 TIF 影像路径")
    ap.add_argument(
        "-o",
        "--output",
        help="输出 GeoJSON 文件路径（默认与 TIF 同名，扩展名为 .geojson）",
    )
    args = ap.parse_args()

    tif_path = Path(args.tif).resolve()
    if not tif_path.exists():
        raise FileNotFoundError(tif_path)

    out_path = (
        Path(args.output).resolve()
        if args.output
        else tif_path.with_suffix(".geojson")
    )

    bounds, crs = load_tif_bounds_and_crs(tif_path)
    coords_ll = reproject_bounds_corners_to_wgs84_lonlat(bounds, crs)
    gj = polygon_to_geojson(coords_ll, name=tif_path.stem)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False, indent=2)

    print(f"[OK] 已生成测区多边形 GeoJSON: {out_path}")
    print("     可直接用于 scripts/path_editor.py 作为输入。")


if __name__ == "__main__":
    main()
