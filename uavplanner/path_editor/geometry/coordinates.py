# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: WGS84 坐标系转换
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""WGS84 坐标系转换模块。

以 WGS84 (EPSG:4326) 为默认地理坐标系，使用 pyproj 进行高精度投影转换。
优先使用 UTM 投影（根据参考点自动选择分带），退化为局部等距近似（pyproj 不可用时）。
"""

from math import cos, pi, sqrt
from typing import Callable, List, Tuple, Union

# WGS84 地理坐标系
WGS84 = "EPSG:4326"


def _utm_zone_from_lonlat(lon: float, lat: float) -> str:
    """根据经度纬度自动确定 UTM 分带。

    Args:
        lon: 经度 (度)。
        lat: 纬度 (度)。

    Returns:
        EPSG 代码字符串，如 "EPSG:32650"。
    """
    zone = int((lon + 180) / 6) + 1
    zone = max(1, min(60, zone))
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return f"EPSG:{epsg}"


def _local_equirectangular(ref_lon: float, ref_lat: float) -> Tuple[Callable, Callable]:
    """局部等距近似（米），pyproj 不可用时的退化方案。

    Args:
        ref_lon: 参考经度 (度)。
        ref_lat: 参考纬度 (度)。

    Returns:
        (ll_to_xy, xy_to_ll) 转换函数对。
    """
    lat_rad = ref_lat * pi / 180.0
    m_lon = 111320.0 * cos(lat_rad)
    m_lat = 110574.0

    def ll_to_xy(lon: float, lat: float) -> Tuple[float, float]:
        x = (lon - ref_lon) * m_lon
        y = (lat - ref_lat) * m_lat
        return (x, y)

    def xy_to_ll(x: float, y: float) -> Tuple[float, float]:
        lon = ref_lon + x / m_lon
        lat = ref_lat + y / m_lat
        return (lon, lat)

    return ll_to_xy, xy_to_ll


def build_ll_xy_transform(
    ref_lon: float,
    ref_lat: float,
    crs: str | None = None,
) -> Tuple[Callable[[float, float], Tuple[float, float]], Callable[[float, float], Tuple[float, float]]]:
    """构建 WGS84 经纬度与平面坐标（米）的转换函数。

    Args:
        ref_lon: 参考经度 (度)。
        ref_lat: 参考纬度 (度)。
        crs: 目标投影 CRS。为 None 时根据 ref_lon/ref_lat 自动选择 UTM 分带。

    Returns:
        (ll_to_xy, xy_to_ll) 转换函数对。
            - ll_to_xy(lon, lat) -> (x, y) 平面坐标 (米)
            - xy_to_ll(x, y) -> (lon, lat) 经纬度 (度)
    """
    target_crs = crs or _utm_zone_from_lonlat(ref_lon, ref_lat)

    try:
        from pyproj import Transformer

        fwd = Transformer.from_crs(WGS84, target_crs, always_xy=True)
        inv = Transformer.from_crs(target_crs, WGS84, always_xy=True)

        def ll_to_xy(lon: float, lat: float) -> Tuple[float, float]:
            x, y = fwd.transform(lon, lat)
            return (float(x), float(y))

        def xy_to_ll(x: float, y: float) -> Tuple[float, float]:
            lon, lat = inv.transform(x, y)
            return (float(lon), float(lat))

        return ll_to_xy, xy_to_ll
    except Exception:
        return _local_equirectangular(ref_lon, ref_lat)


def build_llh_enu_transform(
    ref_lon: float,
    ref_lat: float,
    ref_alt: float = 0.0,
) -> Tuple[
    Callable[[float, float, float], Tuple[float, float, float]],
    Callable[[float, float, float], Tuple[float, float, float]],
]:
    """构建 WGS84 LLH 与局部 ENU 三维坐标（米）的转换函数。

    Args:
        ref_lon: ENU 原点经度 (度)。
        ref_lat: ENU 原点纬度 (度)。
        ref_alt: ENU 原点高程 (米)。

    Returns:
        (llh_to_enu, enu_to_llh)：
            - llh_to_enu(lon, lat, alt) -> (e, n, u)
            - enu_to_llh(e, n, u) -> (lon, lat, alt)
    """
    try:
        from pyproj import CRS, Transformer

        geodetic = CRS.from_epsg(4979)  # WGS84 3D
        enu = CRS.from_proj4(
            f"+proj=topocentric +ellps=WGS84 +lon_0={ref_lon} +lat_0={ref_lat} +h_0={ref_alt}"
        )
        fwd = Transformer.from_crs(geodetic, enu, always_xy=True)
        inv = Transformer.from_crs(enu, geodetic, always_xy=True)

        def llh_to_enu(lon: float, lat: float, alt: float) -> Tuple[float, float, float]:
            e, n, u = fwd.transform(lon, lat, alt)
            return (float(e), float(n), float(u))

        def enu_to_llh(e: float, n: float, u: float) -> Tuple[float, float, float]:
            lon, lat, alt = inv.transform(e, n, u)
            return (float(lon), float(lat), float(alt))

        return llh_to_enu, enu_to_llh
    except Exception:
        # 与 _local_equirectangular 一致：东向、北向米制偏移；u 为相对 ref_alt 的椭球高差。
        # 禁止退回 UTM 全值作「ENU」，否则 region_horizontal_frame=enu_horizontal 与投影坐标混用。
        lat_rad = ref_lat * pi / 180.0
        m_lon = 111320.0 * cos(lat_rad)
        m_lat = 110574.0
        ref_h = float(ref_alt)

        def llh_to_enu(lon: float, lat: float, alt: float) -> Tuple[float, float, float]:
            e = (lon - ref_lon) * m_lon
            n = (lat - ref_lat) * m_lat
            u = float(alt) - ref_h
            return (float(e), float(n), float(u))

        def enu_to_llh(e: float, n: float, u: float) -> Tuple[float, float, float]:
            lon = ref_lon + float(e) / m_lon
            lat = ref_lat + float(n) / m_lat
            return (float(lon), float(lat), ref_h + float(u))

        return llh_to_enu, enu_to_llh


def ll_to_xy_func(ref_lon: float, ref_lat: float, crs: str | None = None) -> Callable:
    """返回 WGS84 经纬度转平面坐标（米）的函数。

    Args:
        ref_lon: 参考经度 (度)。
        ref_lat: 参考纬度 (度)。
        crs: 目标投影 CRS，None 时自动选择。

    Returns:
        可调用对象 ll_to_xy(lon, lat) -> (x, y)。
    """
    ll2xy, _ = build_ll_xy_transform(ref_lon, ref_lat, crs)
    return ll2xy


def xy_to_ll_func(ref_lon: float, ref_lat: float, crs: str | None = None) -> Callable:
    """返回平面坐标（米）转 WGS84 经纬度的函数。

    Args:
        ref_lon: 参考经度 (度)。
        ref_lat: 参考纬度 (度)。
        crs: 目标投影 CRS，None 时自动选择。

    Returns:
        可调用对象 xy_to_ll(x, y) -> (lon, lat)。
    """
    _, xy2ll = build_ll_xy_transform(ref_lon, ref_lat, crs)
    return xy2ll


def geod_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """使用 WGS84 椭球计算两点间大地线距离。

    Args:
        lon1: 第一点经度 (度)。
        lat1: 第一点纬度 (度)。
        lon2: 第二点经度 (度)。
        lat2: 第二点纬度 (度)。

    Returns:
        两点间距离 (米)。
    """
    try:
        from pyproj import Geod

        geod = Geod(ellps="WGS84")
        _, _, dist = geod.inv(lon1, lat1, lon2, lat2)
        return abs(dist)
    except Exception:
        from math import radians

        lat_rad = radians(lat1)
        m_lon = 111320.0 * cos(lat_rad)
        m_lat = 110574.0
        dx = (lon2 - lon1) * m_lon
        dy = (lat2 - lat1) * m_lat
        return (dx**2 + dy**2) ** 0.5


def path_length_m(wpts: List[Tuple[float, float, float]]) -> float:
    """计算航点序列的总航程。

    Args:
        wpts: [(lon, lat, alt), ...] 航点序列。

    Returns:
        总航程 (米)。
    """
    if len(wpts) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(wpts)):
        total += geod_distance(wpts[i - 1][0], wpts[i - 1][1], wpts[i][0], wpts[i][1])
    return total


def segment_lengths_m(wpts: List[Tuple[float, float, float]]) -> List[float]:
    """计算航点序列各航段的长度。

    Args:
        wpts: [(lon, lat, alt), ...] 航点序列。

    Returns:
        各航段长度列表 [seg_0_1, seg_1_2, ...]，长度为 N-1。
    """
    if len(wpts) < 2:
        return []
    return [
        geod_distance(wpts[i][0], wpts[i][1], wpts[i + 1][0], wpts[i + 1][1])
        for i in range(len(wpts) - 1)
    ]


def infer_sweep_segment_starts(
    path_xy: Union[List[Tuple[float, float]], List[List[float]]],
    angle_threshold_deg: float = 120.0,
) -> List[int]:
    """从扫线路径推断各航段起始索引（用于按航段绑定动作模板）。

    通过检测路径中的 U 形转弯（方向突变）识别新航段起点。

    Args:
        path_xy: 平面航点序列 (N, 2)，可为 numpy 数组或列表。
        angle_threshold_deg: 判定为新航段的转角阈值（度），默认 120°。

    Returns:
        各航段首航点索引列表，如 [0, 15, 32, ...]。
    """
    if hasattr(path_xy, "tolist"):
        pts = path_xy.tolist()
    else:
        pts = list(path_xy)
    n = len(pts)
    if n < 2:
        return [0] if n == 1 else []
    cos_thresh = cos(angle_threshold_deg * pi / 180.0)
    starts = [0]
    for i in range(1, n - 1):
        p0 = pts[i - 1]
        p1 = pts[i]
        p2 = pts[i + 1]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        m1 = sqrt(v1[0] * v1[0] + v1[1] * v1[1])
        m2 = sqrt(v2[0] * v2[0] + v2[1] * v2[1])
        if m1 < 1e-9 or m2 < 1e-9:
            continue
        dot_val = (v1[0] * v2[0] + v1[1] * v2[1]) / (m1 * m2)
        if dot_val < cos_thresh:
            starts.append(i + 1)
    return starts
