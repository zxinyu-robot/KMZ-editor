# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: TIF 外接矩形 → WGS84（角点重投影，供多工具复用）
# ------------------------------------------------------------ #
from pathlib import Path
from typing import Any, List, Tuple


def load_tif_bounds_and_crs(tif_path: Path) -> Tuple[Tuple[float, float, float, float], Any]:
    """读取 TIF 外接矩形与源 CRS。

    Returns:
        (left, bottom, right, top), crs（可能为 None）
    """
    try:
        import rasterio
    except ImportError as e:
        raise RuntimeError(
            "未安装 rasterio，无法读取 TIF。请先运行：pip install rasterio"
        ) from e

    with rasterio.open(tif_path) as ds:
        b = ds.bounds
        return (b.left, b.bottom, b.right, b.top), ds.crs


def reproject_bounds_corners_to_wgs84_lonlat(
    bounds: Tuple[float, float, float, float],
    crs_src: Any,
) -> List[Tuple[float, float]]:
    """将矩形四角按源 CRS 重投影到 WGS84，返回闭合环 [(lon,lat), ...]（首尾重复）。"""
    try:
        from rasterio.crs import CRS
        from rasterio.warp import transform
    except ImportError as e:
        raise RuntimeError(
            "未安装 rasterio（含 warp），无法执行坐标重投影。请先运行：pip install rasterio"
        ) from e

    minx, miny, maxx, maxy = bounds
    if crs_src is None:
        return [
            (minx, miny),
            (maxx, miny),
            (maxx, maxy),
            (minx, maxy),
            (minx, miny),
        ]

    crs_src = CRS.from_user_input(crs_src)
    crs_wgs84 = CRS.from_epsg(4326)
    xs = [minx, maxx, maxx, minx, minx]
    ys = [miny, miny, maxy, maxy, miny]
    if crs_src == crs_wgs84:
        return list(zip(xs, ys))
    lon, lat = transform(crs_src, crs_wgs84, xs, ys)
    return list(zip(lon, lat))


def wgs84_axis_aligned_bounds_from_tif(tif_path: Path) -> Tuple[float, float, float, float]:
    """TIF → WGS84 下轴对齐外包框 (min_lon, min_lat, max_lon, max_lat)。

    与 ``reproject_bounds_corners_to_wgs84_lonlat`` 角点策略一致，与 ``tif_to_polygon`` 同源。
    """
    bounds, crs = load_tif_bounds_and_crs(tif_path)
    ring = reproject_bounds_corners_to_wgs84_lonlat(bounds, crs)
    corners = ring[:-1]
    lons = [p[0] for p in corners]
    lats = [p[1] for p in corners]
    return min(lons), min(lats), max(lons), max(lats)
