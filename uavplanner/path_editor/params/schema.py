# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 规划参数 Schema - 统一校验与默认值
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-28
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""规划参数 Schema：统一校验、默认值、与后期参数标准对齐。"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .mission_config import FINISH_ACTIONS


def _normalize_overlap_ratio(value: Any) -> Any:
    """兼容 70/80 百分数输入，统一折算为 0~1。"""
    if value is None:
        return None
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return value
    if 1.0 < ratio <= 100.0:
        ratio = ratio / 100.0
    return ratio


# ---------- 面状航线参数 ----------
@dataclass
class PolygonParams:
    """面状航线规划参数。"""

    # 规划/算法侧字段（canonical 层）。这些字段与协议 Pxx 的语义映射如下（以 Pxx 为主）：
    # - P02(GSD cm/px) -> 派生 spacing（m）
    # - P04(安全起飞高度) -> take_off_security_height；航点高度 -> height
    # - P11/P12(重叠率) -> overlap_lateral/overlap_longitudinal（0~1）
    # - P13(边距) -> margin（m）
    # - P19(主航线角度) -> direction（deg）
    # - P05 全局航线速度 -> global_flight_speed；P06 主航线速度 -> main_route_speed（规划用有效速度见 effective_flight_speed）
    # - P08 完成动作 -> finish_action
    spacing: float = 15.0  # 条带间距 (m)；由 P02 派生或外部直接指定
    direction: float = 0.0  # P19 主航线角度 (deg)，北=0、顺时针为正，建议整数 0~359
    height: float = 120.0  # 航点/作业高度 (m)，算法层 edit_route 使用
    margin: float = 0.0  # 边界内缩距离 (m)
    # 若前端直接传 P02，可通过 gsd_cm_per_px 触发上层把它退化为 spacing；
    # 产品默认 1.5 cm/px，允许范围 0.5~2.5（±1），步长 0.1（见 validate）。
    gsd_cm_per_px: Optional[float] = None  # P02：GSD（cm/px）；可选

    # 采集模式（元数据/导出；mapping2d 与 mapping3d 题型开关，算法层面状仍以 polygon 为主）
    ortho_capture_enabled: bool = True  # 正射采集（mapping2d 相关）
    oblique_capture_enabled: bool = False  # 倾斜采集（mapping3d 相关；与立体航线模板配合）

    # use_camera 决定 spacing 的生成来源：
    # - use_camera=true：使用 height + 相机预设 + 重叠率计算 spacing（算法用）
    # - use_camera=false：使用 spacing 直接作为条带间距
    use_camera: bool = True
    camera: Optional[Dict[str, Any]] = None  # 相机参数字典，或通过 camera_preset 指定
    camera_preset: Optional[str] = "m3e"  # "m3e"|"m3t"|"m30t"|"m300"，默认广角
    overlap_lateral: float = 0.7  # P11：旁向重叠率（0~1，物理量）
    overlap_longitudinal: float = 0.8  # P12：航向重叠率（0~1，物理量）
    # O05/O06（倾斜重叠率）：目前规划几何仍使用正射 overlap_*，但 writer 可按此写回 inclinedCameraOverlap*。
    overlap_lateral_inclined: Optional[float] = None
    overlap_longitudinal_inclined: Optional[float] = None
    optimize_path: bool = True  # 是否剔除共线冗余点
    with_timestamps: bool = False  # 是否输出航段时间语义
    # P05 全局航线速度；P06 主航线速度（未传时规划使用 P05）
    global_flight_speed: float = 10.0  # m/s
    main_route_speed: Optional[float] = None  # m/s；None 表示与 global 相同
    take_off_security_height: float = 120.0  # P04 安全起飞高度 (m)，默认 120，允许 20~220（±100）
    finish_action: str = "goHome"  # P08，与 MissionConfig / wpml:finishAction 字面量一致
    reference_time: float = 0.0  # 首航点参考时间 (s)
    start_ll: Optional[Tuple[float, float]] = None  # 可选起点 (lon, lat)
    end_ll: Optional[Tuple[float, float]] = None  # 可选终点 (lon, lat)

    def effective_flight_speed(self) -> float:
        """P05/P06 编译后的规划速度（m/s）：主航线速度优先，否则全局速度。"""
        if self.main_route_speed is not None:
            return float(self.main_route_speed)
        return float(self.global_flight_speed)

    def validate(self) -> List[str]:
        """校验参数，返回错误列表。"""
        errs = []
        if self.spacing <= 0:
            errs.append("spacing 需大于 0")
        if self.height < 12 or self.height > 15000:
            errs.append("height 需在 12~15000 之间（m）")
        # P02：产品侧 GSD 默认 1.5，允许 0.5~2.5（±1），步长 0.1 cm/px
        if self.gsd_cm_per_px is not None:
            try:
                gsd = float(self.gsd_cm_per_px)
                if gsd < 0.5 or gsd > 2.5:
                    errs.append("gsd_cm_per_px 需在 0.5~2.5 之间（cm/px，产品口径）")
                else:
                    q = round(gsd * 10.0) / 10.0
                    if abs(gsd - q) > 1e-6:
                        errs.append("gsd_cm_per_px 步长应为 0.1（cm/px）")
            except (TypeError, ValueError):
                errs.append("gsd_cm_per_px 需为数字（cm/px）")
        if not 0 <= self.overlap_lateral <= 1:
            errs.append("overlap_lateral 需在 0~1 之间")
        if not 0 <= self.overlap_longitudinal <= 1:
            errs.append("overlap_longitudinal 需在 0~1 之间")
        if self.overlap_lateral_inclined is not None:
            if not 0 <= float(self.overlap_lateral_inclined) <= 1:
                errs.append("overlap_lateral_inclined 需在 0~1 之间")
        if self.overlap_longitudinal_inclined is not None:
            if not 0 <= float(self.overlap_longitudinal_inclined) <= 1:
                errs.append("overlap_longitudinal_inclined 需在 0~1 之间")
        if self.direction < 0 or self.direction > 359:
            errs.append("direction 需在 0~359 之间（deg）")
        if self.margin < 0 or self.margin > 200:
            errs.append("margin 需在 0~200 之间（m）")
        if self.global_flight_speed < 1 or self.global_flight_speed > 15:
            errs.append("global_flight_speed 需在 1~15 之间（m/s）")
        if self.main_route_speed is not None:
            if self.main_route_speed < 1 or self.main_route_speed > 15:
                errs.append("main_route_speed 需在 1~15 之间（m/s）")
        # P04：安全起飞高度，产品侧 120±100 m，步长 10 m
        if self.take_off_security_height < 20 or self.take_off_security_height > 220:
            errs.append("take_off_security_height 需在 20~220 之间（m）")
        else:
            h = float(self.take_off_security_height)
            if abs(h - round(h / 10.0) * 10.0) > 1e-6:
                errs.append("take_off_security_height 步长应为 10（m）")
        if self.finish_action not in FINISH_ACTIONS:
            errs.append(f"finish_action 需为 {FINISH_ACTIONS} 之一")
        return errs

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "spacing": self.spacing,
            "direction": self.direction,
            "height": self.height,
            "margin": self.margin,
            "ortho_capture_enabled": self.ortho_capture_enabled,
            "oblique_capture_enabled": self.oblique_capture_enabled,
            "use_camera": self.use_camera,
            "camera_preset": self.camera_preset,
            "overlap_lateral": self.overlap_lateral,
            "overlap_longitudinal": self.overlap_longitudinal,
            "overlap_lateral_inclined": self.overlap_lateral_inclined,
            "overlap_longitudinal_inclined": self.overlap_longitudinal_inclined,
            "optimize_path": self.optimize_path,
            "with_timestamps": self.with_timestamps,
            "global_flight_speed": self.global_flight_speed,
            "main_route_speed": self.main_route_speed,
            "flight_speed": self.effective_flight_speed(),
            "take_off_security_height": self.take_off_security_height,
            "finish_action": self.finish_action,
            "reference_time": self.reference_time,
        }
        if self.gsd_cm_per_px is not None:
            d["gsd_cm_per_px"] = self.gsd_cm_per_px
        if self.camera is not None:
            d["camera"] = self.camera
        if self.start_ll is not None:
            d["start_ll"] = list(self.start_ll)
        if self.end_ll is not None:
            d["end_ll"] = list(self.end_ll)
        return d

    def to_edit_route_kwargs(self) -> Dict[str, Any]:
        """转换为 pipeline.edit_route 所需的参数字典。"""
        start = self.start_ll
        if start is not None and not isinstance(start, tuple):
            start = tuple(start[:2]) if start else None
        end = self.end_ll
        if end is not None and not isinstance(end, tuple):
            end = tuple(end[:2]) if end else None
        return {
            "spacing": self.spacing,
            "direction": self.direction,
            "height": self.height,
            "margin": self.margin,
            "use_camera": self.use_camera,
            "camera": self.camera,
            "camera_preset": self.camera_preset,
            "overlap_lateral": self.overlap_lateral,
            "overlap_longitudinal": self.overlap_longitudinal,
            "optimize_path": self.optimize_path,
            "with_timestamps": self.with_timestamps,
            "flight_speed": self.effective_flight_speed(),
            "reference_time": self.reference_time,
            "start_ll": start,
            "end_ll": end,
        }


# ---------- 圆柱体航线参数 ----------
@dataclass
class CylinderParams:
    """圆柱体航线规划参数。

    geometry_mode:
    - surface_sweep: 圆柱表面分层圆周扫掠 + 之字形（默认，工程要范几何体航线）
    - spiral: 圆柱螺旋线（兼容旧版）
    """

    center_ll: tuple = (0.0, 0.0)  # (lon, lat)，由 parse_cylinder_params 填充
    radius: float = 0.0  # 飞行半径 (m)
    height: float = 0.0  # 圆柱高度 (m)
    pitch: float = 0.0  # 竖直方向层间距 (m)；spiral 模式下为每圈螺距 (m/圈)
    start_z: float = 25.0  # 起始高度 (m)，满足司空近地 20m 安全阈值
    points_per_rev: int = 36  # 每圈采样点数
    flight_height: float = 0.0  # 叠加到 z 的基准高度 (m)
    geometry_mode: str = "surface_sweep"  # surface_sweep | spiral
    # 起终点优化（可选）：在航线首插入起飞参考点、在末尾追加圆心收束点（圆柱轴心投影）
    home_ll: Optional[Tuple[float, float]] = None  # (lon, lat)，插入为首航点，高度取首条规划航点高度
    append_centroid: bool = False  # True 时在末尾追加 center_ll 处航点（高度取末条规划航点高度）
    with_timestamps: bool = False
    flight_speed: float = 10.0
    reference_time: float = 0.0

    def validate(self) -> List[str]:
        errs = []
        if len(self.center_ll) < 2:
            errs.append("center_ll 至少需要 lon, lat")
        if self.radius <= 0:
            errs.append("radius 需大于 0")
        if self.height <= 0:
            errs.append("height 需大于 0")
        if self.pitch <= 0:
            errs.append("pitch 需大于 0")
        if self.points_per_rev < 4:
            errs.append("points_per_rev 至少为 4")
        if self.flight_speed <= 0:
            errs.append("flight_speed 需大于 0")
        gm = str(self.geometry_mode or "").strip().lower()
        if gm not in ("surface_sweep", "spiral"):
            errs.append("geometry_mode 须为 surface_sweep 或 spiral")
        if self.home_ll is not None:
            if len(self.home_ll) < 2:
                errs.append("home_ll 需为 (lon, lat)")
            else:
                try:
                    float(self.home_ll[0])
                    float(self.home_ll[1])
                except (TypeError, ValueError):
                    errs.append("home_ll 的 lon/lat 需为数字")
        return errs

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "center_ll": list(self.center_ll),
            "radius": self.radius,
            "height": self.height,
            "pitch": self.pitch,
            "start_z": self.start_z,
            "points_per_rev": self.points_per_rev,
            "flight_height": self.flight_height,
            "geometry_mode": self.geometry_mode,
            "append_centroid": self.append_centroid,
            "with_timestamps": self.with_timestamps,
            "flight_speed": self.flight_speed,
            "reference_time": self.reference_time,
        }
        if self.home_ll is not None:
            d["home_ll"] = list(self.home_ll)
        return d


def parse_polygon_params(params: Optional[Dict[str, Any]] = None) -> PolygonParams:
    """从字典解析面状参数，未提供则用默认值。统一参数入口。"""
    p = PolygonParams()
    if not params:
        return p
    for k, v in params.items():
        if k == "flight_speed":
            continue
        if not hasattr(p, k):
            continue
        if k == "start_ll":
            p.start_ll = tuple(v[:2]) if v is not None and isinstance(v, (list, tuple)) and len(v) >= 2 else None
        elif k == "end_ll":
            p.end_ll = tuple(v[:2]) if v is not None and isinstance(v, (list, tuple)) and len(v) >= 2 else None
        elif k in {
            "overlap_lateral",
            "overlap_longitudinal",
            "overlap_lateral_inclined",
            "overlap_longitudinal_inclined",
        }:
            setattr(p, k, _normalize_overlap_ratio(v))
        else:
            setattr(p, k, v)
    # 兼容旧键 flight_speed、reader 的 auto_speed
    if params.get("auto_speed") is not None:
        if (
            "global_flight_speed" not in params
            and "main_route_speed" not in params
            and params.get("flight_speed") is None
        ):
            try:
                p.global_flight_speed = float(params["auto_speed"])
            except (TypeError, ValueError):
                pass
    if params.get("flight_speed") is not None:
        if "global_flight_speed" not in params and "main_route_speed" not in params:
            try:
                p.global_flight_speed = float(params["flight_speed"])
            except (TypeError, ValueError):
                pass
    return p


def parse_cylinder_params(params: Dict[str, Any]) -> CylinderParams:
    """从字典解析圆柱参数。"""
    center = params.get("center_ll") or (0.0, 0.0)
    gm = params.get("geometry_mode", "surface_sweep")
    if isinstance(gm, str):
        gm = gm.strip().lower() or "surface_sweep"
    else:
        gm = "surface_sweep"
    home_ll = None
    hl = params.get("home_ll")
    if hl is not None and isinstance(hl, (list, tuple)) and len(hl) >= 2:
        try:
            home_ll = (float(hl[0]), float(hl[1]))
        except (TypeError, ValueError):
            home_ll = None
    return CylinderParams(
        center_ll=tuple(center[:2]),
        radius=float(params.get("radius", 0)),
        height=float(params.get("height", 0)),
        pitch=float(params.get("pitch", 0)),
        start_z=float(params.get("start_z", 25.0)),
        points_per_rev=int(params.get("points_per_rev", 36)),
        flight_height=float(params.get("flight_height", 0.0)),
        geometry_mode=gm,
        home_ll=home_ll,
        append_centroid=bool(params.get("append_centroid", False)),
        with_timestamps=bool(params.get("with_timestamps", False)),
        flight_speed=float(params.get("flight_speed", 10.0)),
        reference_time=float(params.get("reference_time", 0.0)),
    )


# ---------- 带状航线参数 ----------
@dataclass
class CorridorParams:
    """带状航线规划参数。"""

    half_width: float = 25.0  # 半宽 (m)，中心线向每侧扩展
    lateral_spacing: float = 15.0  # 旁向间距 Dᵧ (m)
    baseline: Optional[float] = None  # 摄影基线 B (m)，沿航线插值
    longitudinal_spacing: Optional[float] = None  # 沿航线采样间距 (m)
    height: float = 100.0  # 飞行高度 (m)
    use_camera: bool = False  # 是否按相机自动算间距
    camera: Optional[Dict[str, Any]] = None
    camera_preset: Optional[str] = None
    overlap_lateral: float = 0.7
    overlap_longitudinal: float = 0.8
    with_timestamps: bool = False
    flight_speed: float = 10.0
    reference_time: float = 0.0

    def validate(self) -> List[str]:
        errs = []
        if self.half_width <= 0:
            errs.append("half_width 需大于 0")
        if self.lateral_spacing <= 0:
            errs.append("lateral_spacing 需大于 0")
        if self.height <= 0:
            errs.append("height 需大于 0")
        if self.flight_speed <= 0:
            errs.append("flight_speed 需大于 0")
        return errs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "half_width": self.half_width,
            "lateral_spacing": self.lateral_spacing,
            "baseline": self.baseline,
            "longitudinal_spacing": self.longitudinal_spacing,
            "height": self.height,
            "use_camera": self.use_camera,
            "camera_preset": self.camera_preset,
            "overlap_lateral": self.overlap_lateral,
            "overlap_longitudinal": self.overlap_longitudinal,
            "with_timestamps": self.with_timestamps,
            "flight_speed": self.flight_speed,
            "reference_time": self.reference_time,
        }


def parse_corridor_params(params: Optional[Dict[str, Any]] = None) -> CorridorParams:
    """从字典解析带状航线参数。"""
    p = CorridorParams()
    if not params:
        return p
    for k, v in params.items():
        if not hasattr(p, k):
            continue
        setattr(p, k, v)
    return p
