# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 规划参数配置 - 相机预设、间距计算、多边形内缩
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""规划参数配置：相机预设、间距计算、多边形内缩（底层）。

解析逻辑（resolve_spacing、apply_margin）在 params.resolver。
"""

import numpy as np


CAMERA_PRESETS: dict = {
    "m3e": {
        "name": "Mavic 3E",
        # 统一采用全画幅等效口径，避免“物理传感器尺寸 + 等效焦距”混算。
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 24.0,
        "image_width": 5280,
        "image_height": 3956,
    },
    "m3t": {
        "name": "Mavic 3T Wide",
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 24.0,
        "image_width": 1920,
        "image_height": 1440,
    },
    "m30t": {
        "name": "M30T Wide",
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 24.0,
        "image_width": 1920,
        "image_height": 1440,
    },
    "m300": {
        "name": "M300 RTK + P1",
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 35.0,
        "image_width": 8192,
        "image_height": 5460,
    },
    "m4t_wide": {
        "name": "Mavic 4T Wide",
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 24.0,
        "image_width": 8064,
        "image_height": 6048,
    },
    "m4t_medium_tele": {
        "name": "Mavic 4T Medium Tele",
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 70.0,
        "image_width": 8064,
        "image_height": 6048,
    },
    "m4t_tele": {
        "name": "Mavic 4T Tele",
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 168.0,
        "image_width": 8064,
        "image_height": 6048,
    },
    "m4t_thermal": {
        "name": "Mavic 4T Thermal",
        "sensor_width": 36.0,
        "sensor_height": 24.0,
        "focal_length": 53.0,
        "image_width": 640,
        "image_height": 512,
    },
}


def calculate_spacing(
    height: float,
    camera: dict,
    overlap_rate: float,
    direction: str = "lateral",
) -> float:
    """根据相机参数和重叠率计算条带间距。

    公式：GSD = (H * sensor) / (f * imageSize)，
         spacing = coverage_width * (1 - overlap_rate)

    Args:
        height: 飞行高度 (m)。
        camera: 相机参数字典 (sensor_width, focal_length, image_width 等)。
        overlap_rate: 重叠率 0~1。
        direction: "lateral" 或 "longitudinal"，默认 "lateral"。

    Returns:
        条带间距 (米)。
    """
    sensor = camera.get("sensor_width", 17.3) if direction == "lateral" else camera.get("sensor_height", 13.0)
    focal = float(camera.get("focal_length", 24.0))
    img_size = float(camera.get("image_width", 5280) if direction == "lateral" else camera.get("image_height", 3956))
    gsd = (height * sensor) / (focal * img_size)
    coverage = gsd * img_size
    return coverage * (1.0 - overlap_rate)


def calculate_gsd_cm_per_px(
    height: float,
    camera: dict,
    direction: str = "lateral",
) -> float:
    """根据飞行高度与相机参数计算 GSD（cm/px）。

    公式（与 calculate_spacing 内部一致）：
      gsd(m/px) = (H * sensor) / (f * imageSize)
      gsd(cm/px) = gsd(m/px) * 100

    Args:
        height: 飞行高度 (m)。
        camera: 相机参数字典（sensor_width/height, focal_length, image_width/height）。
        direction: "lateral" 或 "longitudinal"；决定使用宽/高维参数。

    Returns:
        GSD（cm/px）。
    """
    if direction == "lateral":
        sensor = camera.get("sensor_width", 17.3)
        img_size = camera.get("image_width", 5280)
    else:
        sensor = camera.get("sensor_height", 13.0)
        img_size = camera.get("image_height", 3956)
    focal = float(camera.get("focal_length", 24.0))
    gsd_m_per_px = (height * sensor) / (focal * float(img_size))
    return gsd_m_per_px * 100.0


def shrink_polygon(poly_xy: np.ndarray, margin: float) -> np.ndarray:
    """多边形向内收缩指定距离，采用中心缩放法。

    Args:
        poly_xy: 多边形顶点 (N, 2)，平面坐标 (米)。
        margin: 内缩距离 (米)。

    Returns:
        收缩后的多边形顶点数组。
    """
    if margin <= 0:
        return poly_xy
    center = poly_xy.mean(axis=0)
    dists = np.linalg.norm(poly_xy - center, axis=1)
    avg_dist = float(np.mean(dists))
    if avg_dist < 1e-9:
        return poly_xy
    scale = max(0.1, (avg_dist - margin) / avg_dist)
    return center + (poly_xy - center) * scale
