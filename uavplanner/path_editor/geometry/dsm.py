# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: DSM 加载与采样 - 仿地高度查询
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-09
# ------------------------------------------------------------ #

"""DSM 模块：加载 .npy DSM 与 meta.json，按 (lon, lat) 采样地表高度。"""

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

NODATA = np.float32(-9999.0)


def load_dsm(dsm_path: Path, meta_path: Optional[Path] = None) -> Tuple[Optional[np.ndarray], Optional[Dict]]:
    """加载 DSM 与元数据。

    Args:
        dsm_path: DSM .npy 文件路径，或目录（含 dsm_*.npy 与 meta.json）。
        meta_path: meta.json 路径，若为 None 则从 dsm_path 同目录推断。

    Returns:
        (dsm, meta) 或 (None, None)。
    """
    p = Path(dsm_path)
    if p.is_dir():
        npys = sorted(p.glob("*.npy"), key=lambda x: x.name, reverse=True)
        if not npys:
            return None, None
        dsm_file = npys[0]
        stem = dsm_file.stem
        if stem.endswith("_dsm"):
            meta_file = dsm_file.parent / f"{stem}_meta.json"
        else:
            meta_file = dsm_file.parent / "meta.json"
    else:
        dsm_file = p
        if meta_path is None:
            meta_file = dsm_file.parent / f"{dsm_file.stem}_meta.json"
        else:
            meta_file = Path(meta_path)

    if not dsm_file.exists() or not meta_file.exists():
        return None, None
    dsm = np.load(dsm_file, mmap_mode="r")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if "cell" not in meta and "cell_size" in meta:
        meta["cell"] = meta["cell_size"]
    return dsm, meta


def sample_dsm_at(
    dsm: np.ndarray,
    meta: Dict,
    x: float,
    y: float,
) -> Optional[float]:
    """在 DSM 平面坐标 (x, y) 处采样地表高度。

    Args:
        dsm: DSM 数组 (height, width)。
        meta: 含 xmin, ymin, cell, width, height。
        x, y: 平面坐标 (米)，与 meta 同 CRS（通常 UTM）。

    Returns:
        地表高度 (m)，越界或 NODATA 返回 None。
    """
    xmin = float(meta.get("xmin", 0.0))
    ymin = float(meta.get("ymin", 0.0))
    cell = float(meta.get("cell", meta.get("cell_size", 1.0)))
    w = int(meta.get("width", 0))
    h = int(meta.get("height", 0))
    if w <= 0 or h <= 0:
        return None
    ix = int((x - xmin) / cell)
    iy = int((y - ymin) / cell)
    if ix < 0 or ix >= w or iy < 0 or iy >= h:
        return None
    val = float(dsm[iy, ix])
    if val <= NODATA or np.isnan(val):
        return None
    return val


def apply_dsm_to_waypoints(
    waypoints: List[Tuple[float, float, float]],
    dsm: np.ndarray,
    meta: Dict,
    ll_to_xy: Callable[[float, float], Tuple[float, float]],
    surface_relative_height: float = 100.0,
) -> List[Tuple[float, float, float]]:
    """用 DSM 为航点设置仿地高度。

    Args:
        waypoints: [(lon, lat, alt), ...] 原始航点。
        dsm: DSM 数组。
        meta: DSM 元数据。
        ll_to_xy: 经纬度转平面坐标（与 DSM 同 CRS）。
        surface_relative_height: 相对地表高度 (m)。

    Returns:
        新航点 [(lon, lat, new_alt), ...]，DSM 未覆盖处保留原高度。
    """
    out = []
    for lon, lat, alt in waypoints:
        x, y = ll_to_xy(lon, lat)
        surf = sample_dsm_at(dsm, meta, x, y)
        if surf is not None:
            new_alt = surf + surface_relative_height
        else:
            new_alt = alt
        out.append((lon, lat, new_alt))
    return out
