# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: KMZ 导出 - 航点序列写入 WPML 格式
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""输出层：将航点序列导出为 DJI KMZ/WPML 格式。"""

import json
import logging
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..algorithm.corridor import centerline_to_band_polygon_xy
from ..geometry import ll_to_xy_func, path_length_m, xy_to_ll_func
from ..params.mission_config import MissionConfig, parse_mission_config
from ..params.surface_follow import SurfaceFollowParams, parse_surface_follow_params
from .action_library import ActionTemplate, get_default_photo_template, get_photo_only_template

NS_KML = "http://www.opengis.net/kml/2.2"
NS_WPML = "http://www.dji.com/wpmz/1.0.6"
K = "{%s}" % NS_KML
W = "{%s}" % NS_WPML

_logger_kmz = logging.getLogger(__name__)


def _apply_planning_params_to_template(
    template_kml: bytes,
    height: Optional[float] = None,
    direction: Optional[float] = None,
    overlap_lateral: Optional[float] = None,
    overlap_longitudinal: Optional[float] = None,
    overlap_lateral_inclined: Optional[float] = None,
    overlap_longitudinal_inclined: Optional[float] = None,
    margin: Optional[float] = None,
) -> bytes:
    """将 height、direction、overlap、margin 写入 template.kml，形成闭环。"""
    if all(
        x is None
        for x in (
            height,
            direction,
            overlap_lateral,
            overlap_longitudinal,
            overlap_lateral_inclined,
            overlap_longitudinal_inclined,
            margin,
        )
    ):
        return template_kml
    root = ET.fromstring(template_kml)
    for folder in root.iter():
        if "Folder" not in (folder.tag or ""):
            continue
        if height is not None:
            for tag in ("globalShootHeight", "ellipsoidHeight", "height", "surfaceRelativeHeight"):
                for elem in folder.iter():
                    if (elem.tag or "").endswith(tag) and elem.text:
                        elem.text = f"{height:.6f}"
                        break
        break
    for pm in root.iter():
        if "Placemark" not in (pm.tag or ""):
            continue
        if direction is not None:
            d = None
            for c in pm:
                if (c.tag or "").endswith("direction"):
                    d = c
                    break
            if d is None:
                d = ET.SubElement(pm, f"{W}direction")
            d.text = f"{direction:.0f}"
        if margin is not None:
            m = None
            for c in pm:
                if (c.tag or "").endswith("margin"):
                    m = c
                    break
            if m is None:
                m = ET.SubElement(pm, f"{W}margin")
            m.text = f"{margin:.0f}"
        if height is not None:
            for tag in ("ellipsoidHeight", "height"):
                sub = None
                for c in pm:
                    if (c.tag or "").endswith(tag):
                        sub = c
                        break
                if sub is not None:
                    sub.text = f"{height:.6f}"
        if (
            overlap_lateral is not None
            or overlap_longitudinal is not None
            or overlap_lateral_inclined is not None
            or overlap_longitudinal_inclined is not None
        ):
            # WPML 重叠口径（0~1 -> 0~99 整数）
            # 若只给了倾斜重叠率，orthoCameraOverlap* 也给一个合理回退，避免写入默认常量造成明显偏差。
            lat_ortho_base = overlap_lateral if overlap_lateral is not None else overlap_lateral_inclined
            lon_ortho_base = overlap_longitudinal if overlap_longitudinal is not None else overlap_longitudinal_inclined

            lat_ortho = int(((lat_ortho_base if lat_ortho_base is not None else 0.7)) * 100)  # orthoCameraOverlapW
            lon_ortho = int(((lon_ortho_base if lon_ortho_base is not None else 0.8)) * 100)  # orthoCameraOverlapH

            lat_incl = int(((overlap_lateral_inclined if overlap_lateral_inclined is not None else overlap_lateral) or 0.7) * 100)
            lon_incl = int(((overlap_longitudinal_inclined if overlap_longitudinal_inclined is not None else overlap_longitudinal) or 0.8) * 100)
            ov = None
            for c in pm:
                if (c.tag or "").endswith("overlap"):
                    ov = c
                    break
            if ov is None:
                ov = ET.SubElement(pm, f"{W}overlap")
            for tag in ("orthoCameraOverlapH", "orthoCameraOverlapW", "inclinedCameraOverlapH", "inclinedCameraOverlapW"):
                sub = None
                for s in ov:
                    if (s.tag or "").endswith(tag):
                        sub = s
                        break
                if sub is None:
                    sub = ET.SubElement(ov, f"{W}{tag}")
                # H -> 航向（longitudinal），W -> 旁向（lateral）
                if "inclinedCameraOverlap" in tag:
                    sub.text = str(lon_incl if "OverlapH" in tag else lat_incl)
                else:
                    sub.text = str(lon_ortho if "OverlapH" in tag else lat_ortho)
        break
    return _to_kml_bytes(root)


def resolve_height_export_modes(
    height_mode: Optional[str],
    execute_height_mode: Optional[str],
    surface_follow: Optional[SurfaceFollowParams],
) -> Tuple[str, str]:
    """统一解析「API height_mode / 遗留 execute_height_mode / 仿地」→ 导出器输出。

    与 `docs/开发计划.md` **§十三、§十四** 一致：
    - `waylines.wpml` 航线 Folder 的 `wpml:executeHeightMode`
    - `template.kml` 中 `Folder/wpml:waylineCoordinateSysParam/wpml:heightMode`（模板编辑/重编辑参考）

    Returns:
        (execute_height_mode_waylines, height_mode_template_kml)
    """
    hm = (height_mode or "").strip().lower().replace("-", "_")

    if hm == "relative_to_terrain":
        return ("realTimeFollowSurface", "realTimeFollowSurface")

    if hm == "absolute":
        # §十三：短期未实现时回退为 relative_to_takeoff 等价导出
        return ("relativeToStartPoint", "EGM96")

    if hm == "relative_to_takeoff":
        # 显式相对起飞口径：执行语义与模板显示语义保持一致，避免司空按模板显示为海拔口径。
        return ("relativeToStartPoint", "relativeToStartPoint")

    # height_mode 未传：兼容 KMZ/P03 遗留 execute_height_mode 与仿地推断
    if hm == "":
        if execute_height_mode:
            return _map_execute_height_to_export_pair(execute_height_mode)
        if surface_follow and surface_follow.surface_follow_enable:
            return ("realTimeFollowSurface", "realTimeFollowSurface")
        return ("relativeToStartPoint", "EGM96")

    # 未知 height_mode 字符串：回退遗留逻辑
    if execute_height_mode:
        return _map_execute_height_to_export_pair(execute_height_mode)
    if surface_follow and surface_follow.surface_follow_enable:
        return ("realTimeFollowSurface", "realTimeFollowSurface")
    return ("relativeToStartPoint", "EGM96")


def _map_execute_height_to_export_pair(execute_height_mode: str) -> Tuple[str, str]:
    """P03 / read_kmz 遗留：`WGS84` | `relativeToStartPoint` | `realTimeFollowSurface`。"""
    s = (execute_height_mode or "").strip()
    if s == "WGS84":
        return ("WGS84", "WGS84")
    if s == "relativeToStartPoint":
        return ("relativeToStartPoint", "relativeToStartPoint")
    if s == "realTimeFollowSurface":
        return ("realTimeFollowSurface", "realTimeFollowSurface")
    return ("relativeToStartPoint", "EGM96")


def _apply_height_mode_to_template(template_kml: bytes, height_mode_wpml: str) -> bytes:
    """写入 `template.kml` 中 `waylineCoordinateSysParam/wpml:heightMode`（不重写其它字段）。"""
    root = ET.fromstring(template_kml)
    for folder in root.iter():
        if "Folder" not in (folder.tag or ""):
            continue
        wcs = None
        for child in folder:
            if "waylineCoordinateSysParam" in (child.tag or ""):
                wcs = child
                break
        if wcs is None:
            wcs = ET.SubElement(folder, f"{W}waylineCoordinateSysParam")
        sub = None
        for c in wcs:
            if (c.tag or "").endswith("heightMode"):
                sub = c
                break
        if sub is None:
            sub = ET.SubElement(wcs, f"{W}heightMode")
        sub.text = height_mode_wpml
        break
    return _to_kml_bytes(root)


def _apply_surface_follow_to_template(template_kml: bytes, surface_follow: SurfaceFollowParams) -> bytes:
    """将仿地参数写入 template.kml 的 waylineCoordinateSysParam。"""
    root = ET.fromstring(template_kml)
    for folder in root.iter():
        if "Folder" not in (folder.tag or ""):
            continue
        wcs = None
        for child in folder:
            if "waylineCoordinateSysParam" in (child.tag or ""):
                wcs = child
                break
        if wcs is None:
            wcs = ET.SubElement(folder, f"{W}waylineCoordinateSysParam")
        for tag_name, value in [
            ("surfaceFollowModeEnable", "1" if surface_follow.surface_follow_enable else "0"),
            ("isRealtimeSurfaceFollow", "1" if surface_follow.is_realtime_surface_follow else "0"),
            ("surfaceRelativeHeight", f"{surface_follow.surface_relative_height:.6f}"),
        ]:
            sub = None
            for c in wcs:
                if (c.tag or "").endswith(tag_name):
                    sub = c
                    break
            if sub is None:
                sub = ET.SubElement(wcs, f"{W}{tag_name}")
            sub.text = str(value)
        break
    return _to_kml_bytes(root)


def _apply_polygon_vertex_count_to_template(template_kml: bytes, polygon_vertex_count: Optional[int]) -> bytes:
    """将多边形顶点数写入 template.kml 的 Document/ExtendedData。"""
    if polygon_vertex_count is None:
        return template_kml
    try:
        count = int(polygon_vertex_count)
    except (TypeError, ValueError):
        return template_kml
    if count <= 0:
        return template_kml

    root = ET.fromstring(template_kml)
    doc = root.find(f".//{K}Document")
    if doc is None:
        return template_kml

    ext = doc.find(f"{K}ExtendedData")
    if ext is None:
        ext = ET.SubElement(doc, f"{K}ExtendedData")

    data_elem = None
    for c in ext:
        if (c.tag or "").endswith("Data") and c.attrib.get("name") == "polygon_vertex_count":
            data_elem = c
            break
    if data_elem is None:
        data_elem = ET.SubElement(ext, f"{K}Data", {"name": "polygon_vertex_count"})

    value_elem = None
    for c in data_elem:
        if (c.tag or "").endswith("value"):
            value_elem = c
            break
    if value_elem is None:
        value_elem = ET.SubElement(data_elem, f"{K}value")
    value_elem.text = str(count)

    return _to_kml_bytes(root)


# 规划专用字段：传入参与规划但需写入 KMZ 以形成闭环的参数名列表（snake_case，与 calculate-area normalize 对齐）。
# bridge / reader 共用此元组，避免 ExtendedData 写入与读回键集合漂移。
EXTRA_PLANNING_FIELD_NAMES = (
    "gsd_cm_per_px",
    "spacing",
    "use_camera",
    "camera_preset",
    "optimize_path",
    "with_timestamps",
    "start_ll",
    "end_ll",
    "reference_time",
    "ortho_capture_enabled",
    "oblique_capture_enabled",
    # 几何体 / 司空扩展（圆柱、测区等）
    "ir_gsd",
    "start_z",
    "climb_mode",
    "vertical_climb_mode",
    "oblique_climb_mode",
    "survey_top_asl",
    "survey_bottom_asl",
    "side_flight_speed",
    "route_orientation",
    "home_ll",
    "include_top_cap",
    "coverage_yaw_offset",
    "sweep_yaw_offset",
    "geometry_mode",
    "pitch",
    "points_per_rev",
    "flight_height",
    "append_centroid",
    "coverage_ratio",
    "start_azimuth_deg",
    "payload_lens_index",
    # 起飞 ingress：JSON 对象字符串写回 template.kml，与 calculate-area / export-kmz options 对齐
    "takeoff_ingress_pose",
)

_EXTRA_PLANNING_FIELDS = EXTRA_PLANNING_FIELD_NAMES


def _apply_extra_planning_params_to_template(template_kml: bytes, extra: dict) -> bytes:
    """将规划专用参数写入 template.kml 的 Document/ExtendedData，供 KMZ 重导入时还原。

    序列化规则：
    - bool -> "true" / "false"
    - start_ll / end_ll (list/tuple) -> "lon,lat"
    - 其余数值/字符串 -> str()
    """
    if not extra:
        return template_kml

    def _serialize(v) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, dict):
            try:
                return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return None
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            try:
                return f"{float(v[0]):.8f},{float(v[1]):.8f}"
            except (TypeError, ValueError):
                return None
        try:
            return str(v)
        except Exception:
            return None

    entries = {}
    for k in _EXTRA_PLANNING_FIELDS:
        if k in extra and extra[k] is not None:
            s = _serialize(extra[k])
            if s is not None:
                entries[k] = s

    if not entries:
        return template_kml

    root = ET.fromstring(template_kml)
    doc = root.find(f".//{K}Document")
    if doc is None:
        return template_kml

    ext = doc.find(f"{K}ExtendedData")
    if ext is None:
        ext = ET.SubElement(doc, f"{K}ExtendedData")

    for name, value in entries.items():
        data_elem = None
        for c in ext:
            if (c.tag or "").endswith("Data") and c.attrib.get("name") == name:
                data_elem = c
                break
        if data_elem is None:
            data_elem = ET.SubElement(ext, f"{K}Data", {"name": name})
        value_elem = None
        for c in data_elem:
            if (c.tag or "").endswith("value"):
                value_elem = c
                break
        if value_elem is None:
            value_elem = ET.SubElement(data_elem, f"{K}value")
        value_elem.text = value

    return _to_kml_bytes(root)


def _apply_template_type_to_template(template_kml: bytes, template_type_tag: Optional[str]) -> bytes:
    """写回 `template.kml` 中 `Folder/wpml:templateType`。"""
    if template_type_tag is None or str(template_type_tag).strip() == "":
        return template_kml
    root = ET.fromstring(template_kml)
    for folder in root.iter():
        if "Folder" not in (folder.tag or ""):
            continue
        sub = None
        for c in folder:
            if (c.tag or "").endswith("templateType"):
                sub = c
                break
        if sub is None:
            sub = ET.SubElement(folder, f"{W}templateType")
        sub.text = str(template_type_tag).strip()
        break
    return _to_kml_bytes(root)


def _apply_mission_config(
    doc_elem: ET.Element,
    mission_config: MissionConfig,
    *,
    include_take_off_ref_fields: bool = True,
    include_auto_reroute_info: bool = False,
) -> None:
    """将任务配置写入 Document 下的 wpml:missionConfig，支持标量与嵌套结构。"""
    mc = None
    for child in doc_elem:
        if "missionConfig" in (child.tag or ""):
            mc = child
            break
    if mc is None:
        mc = ET.SubElement(doc_elem, f"{W}missionConfig")

    def _set_elem(parent: ET.Element, tag: str, val: object) -> None:
        sub = None
        for c in parent:
            if (c.tag or "").endswith(tag):
                sub = c
                break
        if sub is None:
            sub = ET.SubElement(parent, f"{W}{tag}")
        if isinstance(val, dict):
            for k, v in val.items():
                _set_elem(sub, k, v)
        else:
            sub.text = str(val)

    for tag_name, value in mission_config.to_wpml_dict(
        include_take_off_ref_fields=include_take_off_ref_fields,
        include_auto_reroute_info=include_auto_reroute_info,
    ).items():
        _set_elem(mc, tag_name, value)

# 司空解析要求：使用默认 xmlns 和 wpml: 前缀，移除 ns0/ns1
def _to_kml_bytes(elem: ET.Element) -> bytes:
    raw = ET.tostring(elem, encoding="utf-8", xml_declaration=True)
    s = raw.decode("utf-8")
    wpml_ns = re.search(r'xmlns:(ns\d+)="http://www\.dji\.com/wpmz/1\.0\.6"', s)
    kml_ns = re.search(r'xmlns:(ns\d+)="http://www\.opengis\.net/kml/2\.2"', s)
    if wpml_ns:
        w = wpml_ns.group(1)
        s = re.sub(rf'</{re.escape(w)}:([a-zA-Z][a-zA-Z0-9]*)', r'</wpml:\1', s)
        s = re.sub(rf'<{re.escape(w)}:([a-zA-Z][a-zA-Z0-9]*)', r'<wpml:\1', s)
    if kml_ns:
        k = kml_ns.group(1)
        s = re.sub(rf'</{re.escape(k)}:([a-zA-Z][a-zA-Z0-9]*)', r'</\1', s)
        s = re.sub(rf'<{re.escape(k)}:([a-zA-Z][a-zA-Z0-9]*)', r'<\1', s)
    s = re.sub(r'\sxmlns:ns\d+="http://www\.opengis\.net/kml/2\.2"', ' xmlns="http://www.opengis.net/kml/2.2"', s)
    s = re.sub(r'\sxmlns:ns\d+="http://www\.dji\.com/wpmz/1\.0\.6"', ' xmlns:wpml="http://www.dji.com/wpmz/1.0.6"', s)
    s = re.sub(r"encoding=['\"]utf-8['\"]", 'encoding="UTF-8"', s, flags=re.I)
    # 去除根元素重复的 xmlns 声明（司空解析要求）
    kml_match = re.search(r"<kml([^>]*)>", s)
    if kml_match:
        attrs = kml_match.group(1)
        attrs = re.sub(r'\s*xmlns(?::\w+)?="[^"]*"', '', attrs)
        attrs = attrs.strip()
        prefix = ' ' if attrs else ''
        new_tag = f'<kml xmlns="{NS_KML}" xmlns:wpml="{NS_WPML}"{prefix}{attrs}>'
        s = s[: kml_match.start()] + new_tag + s[kml_match.end() :]
    return s.encode("utf-8")


def _closed_vertices_llh(
    vertices_llh: Optional[List[Tuple[float, float, float]]],
) -> List[Tuple[float, float, float]]:
    """闭合 3D 顶点环；无效输入返回空列表。"""
    if not vertices_llh:
        return []
    pts: List[Tuple[float, float, float]] = []
    for p in vertices_llh:
        if not isinstance(p, (list, tuple)) or len(p) < 3:
            continue
        pts.append((float(p[0]), float(p[1]), float(p[2])))
    if len(pts) < 3:
        return []
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _coords_string_from_vertices_llh(
    vertices_llh: List[Tuple[float, float, float]],
) -> str:
    return "\n                ".join(
        f"{lon:.8f},{lat:.8f},{alt:.6f}" for lon, lat, alt in vertices_llh
    )


def _mapping2d_standard_template_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "mapping2d_standard"
        / "wpmz"
        / "template.kml"
    )


def _mapping2d_standard_waylines_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "mapping2d_standard"
        / "wpmz"
        / "waylines.wpml"
    )


def _build_mapping2d_template_from_standard(
    *,
    coords_str: str,
    height: float,
    auto_flight_speed: float,
    template_type_tag: str,
    ref_lat: float,
    ref_lon: float,
    timestamp_ms: int,
) -> bytes:
    tpl_path = _mapping2d_standard_template_path()
    if not tpl_path.is_file():
        raise FileNotFoundError(f"mapping2d 标准模板不存在: {tpl_path}")

    root = ET.fromstring(tpl_path.read_bytes())
    doc = root.find(f".//{K}Document") or root

    # 更新时间元信息，便于产物追踪。
    for tag_name in ("author", "createTime", "updateTime"):
        node = doc.find(f"{W}{tag_name}")
        if node is None:
            node = ET.SubElement(doc, f"{W}{tag_name}")
        if tag_name == "author":
            node.text = "path_editor"
        else:
            node.text = str(timestamp_ms)

    # missionConfig 关键字段与当前请求保持一致。
    mission = doc.find(f"{W}missionConfig")
    if mission is not None:
        for tag_name, value in (
            ("takeOffRefPoint", f"{ref_lat:.6f},{ref_lon:.6f},{float(height):.3f}"),
            ("takeOffRefPointAGLHeight", "0"),
            ("globalRTHHeight", f"{float(height):.0f}"),
        ):
            sub = mission.find(f"{W}{tag_name}")
            if sub is None:
                sub = ET.SubElement(mission, f"{W}{tag_name}")
            sub.text = value

    folder = doc.find(f"{K}Folder")
    if folder is not None:
        ttype = folder.find(f"{W}templateType")
        if ttype is None:
            ttype = ET.SubElement(folder, f"{W}templateType")
        ttype.text = str(template_type_tag)

        auto_sp = folder.find(f"{W}autoFlightSpeed")
        if auto_sp is None:
            auto_sp = ET.SubElement(folder, f"{W}autoFlightSpeed")
        auto_sp.text = f"{float(auto_flight_speed):.0f}"

        # Polygon coordinates
        coords = folder.find(f".//{K}Placemark/{K}Polygon/{K}outerBoundaryIs/{K}LinearRing/{K}coordinates")
        if coords is not None:
            coords.text = f"\n                {coords_str}\n              "

    # 复用现有参数写回器，统一 height/direction/overlap 等字段。
    return _to_kml_bytes(root)


def _is_action_library_folder(folder_elem: ET.Element) -> bool:
    name_elem = folder_elem.find(f"{K}name")
    if name_elem is not None:
        name_val = (name_elem.text or "").strip()
        if name_val in ("动作库", "ActionLibrary", "动作模板库"):
            return True
    for data in folder_elem.findall(f".//{K}Data"):
        data_name = (data.attrib.get("name") or "").strip()
        if data_name in ("actionTemplate", "action_template"):
            return True
    return False


def _remove_action_library_folders(parent: ET.Element) -> None:
    """最终 KMZ 不回写编辑器内部动作模板库 Folder。"""
    for folder in list(parent.findall(f"{K}Folder")):
        if _is_action_library_folder(folder):
            parent.remove(folder)


def _direct_child_text(parent: Optional[ET.Element], tag_suffix: str) -> Optional[str]:
    if parent is None:
        return None
    for child in list(parent):
        if (child.tag or "").endswith(tag_suffix):
            text = (child.text or "").strip()
            return text or None
    return None


def _extract_wpml_turn_profiles(
    folder_elem: Optional[ET.Element],
) -> Tuple[str, str, Dict[int, Dict[str, Optional[str]]]]:
    """提取旧 waylines Folder 中的全局/逐点转弯参数。"""
    global_turn_mode = _direct_child_text(folder_elem, "globalWaypointTurnMode")
    global_use_straight_line = _direct_child_text(folder_elem, "globalUseStraightLine")
    point_profiles: Dict[int, Dict[str, Optional[str]]] = {}
    if folder_elem is None:
        return (
            global_turn_mode or "toPointAndStopWithDiscontinuityCurvature",
            global_use_straight_line or "1",
            point_profiles,
        )

    for placemark in folder_elem.findall(f"{K}Placemark"):
        idx_text = _direct_child_text(placemark, "index")
        if idx_text is None:
            continue
        try:
            idx = int(idx_text)
        except (TypeError, ValueError):
            continue
        turn_param = None
        for child in list(placemark):
            if (child.tag or "").endswith("waypointTurnParam"):
                turn_param = child
                break
        point_profiles[idx] = {
            "use_global_turn_param": _direct_child_text(placemark, "useGlobalTurnParam"),
            "use_straight_line": _direct_child_text(placemark, "useStraightLine"),
            "turn_mode": _direct_child_text(turn_param, "waypointTurnMode"),
            "turn_damping_dist": _direct_child_text(turn_param, "waypointTurnDampingDist"),
        }

    return (
        global_turn_mode or "toPointAndStopWithDiscontinuityCurvature",
        global_use_straight_line or "1",
        point_profiles,
    )


def _build_template_placemark_xml(
    *,
    placemark_profile: Optional[str],
    template_type: str,
    coords_str: str,
    height: float,
    template_prism_height: Optional[float],
    direction: float,
    inclined_gimbal_pitch: Optional[float],
    inclined_flight_speed: Optional[float],
    overlap_ortho_h: Optional[int],
    overlap_ortho_w: Optional[int],
    overlap_inclined_h: Optional[int],
    overlap_inclined_w: Optional[int],
    auto_flight_speed: float,
) -> str:
    """按业务题型生成更贴近 DJI 官方结构的模板 Placemark。"""
    profile = (placemark_profile or template_type or "").strip().lower()

    ortho_h = int(overlap_ortho_h) if overlap_ortho_h is not None else 80
    ortho_w = int(overlap_ortho_w) if overlap_ortho_w is not None else 70
    inclined_h = int(overlap_inclined_h) if overlap_inclined_h is not None else 80
    inclined_w = int(overlap_inclined_w) if overlap_inclined_w is not None else 70
    inclined_pitch = float(inclined_gimbal_pitch) if inclined_gimbal_pitch is not None else -45.0
    inclined_speed = float(inclined_flight_speed) if inclined_flight_speed is not None else float(auto_flight_speed)

    if profile == "cylinder":
        prism_height = float(template_prism_height) if template_prism_height is not None else float(height)
        return f"""      <Placemark>
        <wpml:shootTopFaceEnable>1</wpml:shootTopFaceEnable>
        <wpml:shootType>distance</wpml:shootType>
        <wpml:trajectoryType>vert</wpml:trajectoryType>
        <wpml:startPositionType>top</wpml:startPositionType>
        <wpml:overlap>
          <wpml:orthoCameraOverlapH>{ortho_h}</wpml:orthoCameraOverlapH>
          <wpml:orthoCameraOverlapW>{ortho_w}</wpml:orthoCameraOverlapW>
        </wpml:overlap>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                {coords_str}
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
        <wpml:height>{prism_height:.6f}</wpml:height>
      </Placemark>"""

    if profile == "facade":
        return f"""      <Placemark>
        <wpml:caliFlightEnable>0</wpml:caliFlightEnable>
        <wpml:elevationOptimizeEnable>0</wpml:elevationOptimizeEnable>
        <wpml:smartObliqueEnable>0</wpml:smartObliqueEnable>
        <wpml:facadeWaylineEnable>1</wpml:facadeWaylineEnable>
        <wpml:shootType>time</wpml:shootType>
        <wpml:direction>{direction:.0f}</wpml:direction>
        <wpml:margin>0</wpml:margin>
        <wpml:efficiencyFlightModeEnable>0</wpml:efficiencyFlightModeEnable>
        <wpml:overlap>
          <wpml:orthoCameraOverlapH>{ortho_h}</wpml:orthoCameraOverlapH>
          <wpml:orthoCameraOverlapW>{ortho_w}</wpml:orthoCameraOverlapW>
          <wpml:inclinedCameraOverlapH>{inclined_h}</wpml:inclinedCameraOverlapH>
          <wpml:inclinedCameraOverlapW>{inclined_w}</wpml:inclinedCameraOverlapW>
        </wpml:overlap>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                {coords_str}
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
        <wpml:ellipsoidHeight>{height:.6f}</wpml:ellipsoidHeight>
        <wpml:height>{height:.6f}</wpml:height>
      </Placemark>"""

    if template_type == "mapping3d":
        return f"""      <Placemark>
        <wpml:caliFlightEnable>0</wpml:caliFlightEnable>
        <wpml:elevationOptimizeEnable>0</wpml:elevationOptimizeEnable>
        <wpml:inclinedGimbalPitch>{inclined_pitch:.0f}</wpml:inclinedGimbalPitch>
        <wpml:shootType>time</wpml:shootType>
        <wpml:direction>{direction:.0f}</wpml:direction>
        <wpml:margin>0</wpml:margin>
        <wpml:inclinedFlightSpeed>{inclined_speed:.0f}</wpml:inclinedFlightSpeed>
        <wpml:efficiencyFlightModeEnable>0</wpml:efficiencyFlightModeEnable>
        <wpml:overlap>
          <wpml:orthoCameraOverlapH>{ortho_h}</wpml:orthoCameraOverlapH>
          <wpml:orthoCameraOverlapW>{ortho_w}</wpml:orthoCameraOverlapW>
          <wpml:inclinedCameraOverlapH>{inclined_h}</wpml:inclinedCameraOverlapH>
          <wpml:inclinedCameraOverlapW>{inclined_w}</wpml:inclinedCameraOverlapW>
        </wpml:overlap>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                {coords_str}
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
        <wpml:ellipsoidHeight>{height:.6f}</wpml:ellipsoidHeight>
        <wpml:height>{height:.6f}</wpml:height>
      </Placemark>"""

    return f"""      <Placemark>
        <wpml:caliFlightEnable>0</wpml:caliFlightEnable>
        <wpml:elevationOptimizeEnable>0</wpml:elevationOptimizeEnable>
        <wpml:smartObliqueEnable>0</wpml:smartObliqueEnable>
        <wpml:shootType>time</wpml:shootType>
        <wpml:direction>{direction:.0f}</wpml:direction>
        <wpml:margin>0</wpml:margin>
        <wpml:efficiencyFlightModeEnable>0</wpml:efficiencyFlightModeEnable>
        <wpml:overlap>
          <wpml:orthoCameraOverlapH>{ortho_h}</wpml:orthoCameraOverlapH>
          <wpml:orthoCameraOverlapW>{ortho_w}</wpml:orthoCameraOverlapW>
          <wpml:inclinedCameraOverlapH>{inclined_h}</wpml:inclinedCameraOverlapH>
          <wpml:inclinedCameraOverlapW>{inclined_w}</wpml:inclinedCameraOverlapW>
        </wpml:overlap>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                {coords_str}
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
        <wpml:ellipsoidHeight>{height:.6f}</wpml:ellipsoidHeight>
        <wpml:height>{height:.6f}</wpml:height>
      </Placemark>"""


def build_minimal_template_kml(
    polygon_ll: List[Tuple[float, float]],
    height: float = 100.0,
    direction: float = 0.0,
    template_type: str = "mapping2d",
    *,
    inclined_gimbal_pitch: Optional[float] = None,
    inclined_flight_speed: Optional[float] = None,
    auto_flight_speed: Optional[float] = None,
    overlap_ortho_h: Optional[int] = None,
    overlap_ortho_w: Optional[int] = None,
    overlap_inclined_h: Optional[int] = None,
    overlap_inclined_w: Optional[int] = None,
    template_type_tag: Optional[str] = None,
    placemark_profile: Optional[str] = None,
    template_vertices_llh: Optional[List[Tuple[float, float, float]]] = None,
    template_prism_height: Optional[float] = None,
) -> bytes:
    """为非 KMZ 输入生成 KML 模板，兼容司空（含 missionConfig、templateType、waylineCoordinateSysParam 等）。

    Args:
        polygon_ll: 多边形顶点 [(lon, lat), ...]。
        height: 默认高度 (米)。
        direction: 默认航线方向 (度)。
        template_type: 模板题型（``mapping2d`` / ``mapping3d`` / ``waypoint`` 等）。
        inclined_gimbal_pitch: 斜拍云台俯仰 (度)，仅 ``mapping3d``。
        inclined_flight_speed: 斜拍航线速度 (m/s)，仅 ``mapping3d``。
        auto_flight_speed: Folder 级 ``autoFlightSpeed``；未传时默认 10。
        overlap_*: 重叠率整数 0~99，与司空 WPML 一致；仅 ``mapping3d`` 时与 oblique 模板对齐。

    Returns:
        KML 模板内容 (UTF-8 编码)。
    """
    if not polygon_ll:
        polygon_ll = [(120.15, 30.28), (120.16, 30.28), (120.16, 30.29), (120.15, 30.29)]

    # 兼容前端/调用方已传闭合环：避免重复追加首点，防止部分手柄对 Polygon 解析失败。
    ring_coords_2d = [(float(lon), float(lat)) for lon, lat in polygon_ll]
    if len(ring_coords_2d) >= 2:
        first_lon, first_lat = ring_coords_2d[0]
        last_lon, last_lat = ring_coords_2d[-1]
        if abs(first_lon - last_lon) < 1e-12 and abs(first_lat - last_lat) < 1e-12:
            ring_coords_2d = ring_coords_2d[:-1]
    if len(ring_coords_2d) < 3:
        ring_coords_2d = [(float(lon), float(lat)) for lon, lat in polygon_ll]

    coords_str_2d = "\n                ".join(
        f"{lon:.8f},{lat:.8f},0" for lon, lat in ring_coords_2d
    )
    lon0, lat0 = ring_coords_2d[0]
    coords_str_2d += f"\n                {lon0:.8f},{lat0:.8f},0"
    vertices_llh = _closed_vertices_llh(template_vertices_llh)
    coords_str = (
        _coords_string_from_vertices_llh(vertices_llh)
        if vertices_llh
        else coords_str_2d
    )
    ref_lat, ref_lon = polygon_ll[0][1], polygon_ll[0][0]
    ts = int(time.time() * 1000)

    tpl = (template_type or "mapping2d").strip()
    if not tpl:
        tpl = "mapping2d"
    tpl_tag = (template_type_tag or tpl).strip()
    if not tpl_tag:
        tpl_tag = tpl

    auto_sp = float(auto_flight_speed) if auto_flight_speed is not None else 10.0
    profile = (placemark_profile or "").strip().lower()

    # 面状 polygon 优先复用项目标准模板骨架（含动作库 Folder 等司空兼容结构）。
    if tpl == "mapping2d" and profile in ("", "polygon"):
        return _build_mapping2d_template_from_standard(
            coords_str=coords_str,
            height=height,
            auto_flight_speed=auto_sp,
            template_type_tag=tpl_tag,
            ref_lat=float(ref_lat),
            ref_lon=float(ref_lon),
            timestamp_ms=ts,
        )

    if tpl == "mapping3d":
        placemark_xml = _build_template_placemark_xml(
            placemark_profile=placemark_profile,
            template_type=tpl,
            coords_str=coords_str,
            height=height,
            template_prism_height=template_prism_height,
            direction=direction,
            inclined_gimbal_pitch=inclined_gimbal_pitch,
            inclined_flight_speed=inclined_flight_speed,
            overlap_ortho_h=overlap_ortho_h,
            overlap_ortho_w=overlap_ortho_w,
            overlap_inclined_h=overlap_inclined_h,
            overlap_inclined_w=overlap_inclined_w,
            auto_flight_speed=auto_sp,
        )
        kml = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{NS_KML}" xmlns:wpml="{NS_WPML}">
  <Document>
    <wpml:author>path_editor</wpml:author>
    <wpml:createTime>{ts}</wpml:createTime>
    <wpml:updateTime>{ts}</wpml:updateTime>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>goHome</wpml:finishAction>
      <wpml:exitOnRCLost>goContinue</wpml:exitOnRCLost>
      <wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>
      <wpml:takeOffSecurityHeight>120</wpml:takeOffSecurityHeight>
      <wpml:takeOffRefPoint>{ref_lat:.6f},{ref_lon:.6f},{height:.3f}</wpml:takeOffRefPoint>
      <wpml:takeOffRefPointAGLHeight>0</wpml:takeOffRefPointAGLHeight>
      <wpml:globalTransitionalSpeed>15</wpml:globalTransitionalSpeed>
      <wpml:globalRTHHeight>{height:.0f}</wpml:globalRTHHeight>
      <wpml:droneInfo>
        <wpml:droneEnumValue>99</wpml:droneEnumValue>
        <wpml:droneSubEnumValue>1</wpml:droneSubEnumValue>
      </wpml:droneInfo>
      <wpml:waylineAvoidLimitAreaMode>0</wpml:waylineAvoidLimitAreaMode>
      <wpml:payloadInfo>
        <wpml:payloadEnumValue>89</wpml:payloadEnumValue>
        <wpml:payloadSubEnumValue>0</wpml:payloadSubEnumValue>
        <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
      </wpml:payloadInfo>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateType>{tpl_tag}</wpml:templateType>
      <wpml:templateId>0</wpml:templateId>
      <wpml:waylineCoordinateSysParam>
        <wpml:coordinateMode>WGS84</wpml:coordinateMode>
        <wpml:heightMode>relativeToStartPoint</wpml:heightMode>
        <wpml:globalShootHeight>{height:.0f}</wpml:globalShootHeight>
        <wpml:surfaceFollowModeEnable>0</wpml:surfaceFollowModeEnable>
        <wpml:isRealtimeSurfaceFollow>0</wpml:isRealtimeSurfaceFollow>
        <wpml:surfaceRelativeHeight>{height:.0f}</wpml:surfaceRelativeHeight>
      </wpml:waylineCoordinateSysParam>
      <wpml:autoFlightSpeed>{auto_sp:.0f}</wpml:autoFlightSpeed>
{placemark_xml}
      <wpml:payloadParam>
        <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
        <wpml:focusMode>firstPoint</wpml:focusMode>
        <wpml:meteringMode>average</wpml:meteringMode>
        <wpml:returnMode>singleReturnStrongest</wpml:returnMode>
        <wpml:samplingRate>240000</wpml:samplingRate>
        <wpml:scanningMode>repetitive</wpml:scanningMode>
        <wpml:imageFormat>wide</wpml:imageFormat>
        <wpml:photoSize>default_l</wpml:photoSize>
      </wpml:payloadParam>
    </Folder>
  </Document>
</kml>'''
        return kml.encode("utf-8")

    placemark_xml = _build_template_placemark_xml(
        placemark_profile=placemark_profile,
        template_type=tpl,
        coords_str=coords_str,
        height=height,
        template_prism_height=template_prism_height,
        direction=direction,
        inclined_gimbal_pitch=inclined_gimbal_pitch,
        inclined_flight_speed=inclined_flight_speed,
        overlap_ortho_h=overlap_ortho_h,
        overlap_ortho_w=overlap_ortho_w,
        overlap_inclined_h=overlap_inclined_h,
        overlap_inclined_w=overlap_inclined_w,
        auto_flight_speed=auto_sp,
    )
    kml = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{NS_KML}" xmlns:wpml="{NS_WPML}">
  <Document>
    <wpml:author>path_editor</wpml:author>
    <wpml:createTime>{ts}</wpml:createTime>
    <wpml:updateTime>{ts}</wpml:updateTime>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>goHome</wpml:finishAction>
      <wpml:exitOnRCLost>goContinue</wpml:exitOnRCLost>
      <wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>
      <wpml:takeOffSecurityHeight>120</wpml:takeOffSecurityHeight>
      <wpml:takeOffRefPoint>{ref_lat:.6f},{ref_lon:.6f},{height:.3f}</wpml:takeOffRefPoint>
      <wpml:takeOffRefPointAGLHeight>0</wpml:takeOffRefPointAGLHeight>
      <wpml:globalTransitionalSpeed>15</wpml:globalTransitionalSpeed>
      <wpml:globalRTHHeight>{height:.0f}</wpml:globalRTHHeight>
      <wpml:droneInfo>
        <wpml:droneEnumValue>99</wpml:droneEnumValue>
        <wpml:droneSubEnumValue>1</wpml:droneSubEnumValue>
      </wpml:droneInfo>
      <wpml:waylineAvoidLimitAreaMode>0</wpml:waylineAvoidLimitAreaMode>
      <wpml:payloadInfo>
        <wpml:payloadEnumValue>89</wpml:payloadEnumValue>
        <wpml:payloadSubEnumValue>0</wpml:payloadSubEnumValue>
        <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
      </wpml:payloadInfo>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateType>{tpl_tag}</wpml:templateType>
      <wpml:templateId>0</wpml:templateId>
      <wpml:waylineCoordinateSysParam>
        <wpml:coordinateMode>WGS84</wpml:coordinateMode>
        <wpml:heightMode>EGM96</wpml:heightMode>
        <wpml:globalShootHeight>{height:.0f}</wpml:globalShootHeight>
        <wpml:surfaceFollowModeEnable>0</wpml:surfaceFollowModeEnable>
        <wpml:isRealtimeSurfaceFollow>0</wpml:isRealtimeSurfaceFollow>
        <wpml:surfaceRelativeHeight>{height:.0f}</wpml:surfaceRelativeHeight>
      </wpml:waylineCoordinateSysParam>
      <wpml:autoFlightSpeed>{auto_sp:.0f}</wpml:autoFlightSpeed>
{placemark_xml}
      <wpml:payloadParam>
        <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
        <wpml:focusMode>firstPoint</wpml:focusMode>
        <wpml:meteringMode>average</wpml:meteringMode>
        <wpml:returnMode>singleReturnStrongest</wpml:returnMode>
        <wpml:samplingRate>240000</wpml:samplingRate>
        <wpml:scanningMode>repetitive</wpml:scanningMode>
        <wpml:imageFormat>wide</wpml:imageFormat>
        <wpml:photoSize>default_l</wpml:photoSize>
      </wpml:payloadParam>
    </Folder>
  </Document>
</kml>'''
    return kml.encode("utf-8")


def build_minimal_waypoint_template(
    points_ll: List[Tuple[float, ...]],
    height: float = 100.0,
    auto_flight_speed: float = 10.0,
) -> bytes:
    """为点列表输入生成 waypoint 类型 KML 模板。

    Args:
        points_ll: 航点序列 [(lon, lat), ...] 或 [(lon, lat, alt), ...]。含 alt 时用于 3D 显示（圆柱螺旋等）。
        height: 默认高度 (米)，仅当点无 alt 时使用。

    Returns:
        KML 模板内容 (UTF-8 编码)。
    """
    def _coord(i: int, lon: float, lat: float, alt: Optional[float]) -> str:
        if alt is not None:
            return f"{lon:.8f},{lat:.8f},{alt:.6f}"
        return f"{lon:.8f},{lat:.8f}"

    def _h(i: int, lon: float, lat: float, alt: Optional[float]) -> str:
        return f"{alt:.6f}" if alt is not None else f"{height:.0f}"

    ref_alt = points_ll[0][2] if len(points_ll[0]) >= 3 else height
    placemarks = "\n".join(
        f'''      <Placemark>
        <Point><coordinates>{_coord(i, p[0], p[1], p[2] if len(p) >= 3 else None)}</coordinates></Point>
        <wpml:index>{i}</wpml:index>
        <wpml:useGlobalHeight>0</wpml:useGlobalHeight>
        <wpml:ellipsoidHeight>{_h(i, p[0], p[1], p[2] if len(p) >= 3 else None)}</wpml:ellipsoidHeight>
        <wpml:height>{_h(i, p[0], p[1], p[2] if len(p) >= 3 else None)}</wpml:height>
        <wpml:useGlobalSpeed>0</wpml:useGlobalSpeed>
        <wpml:waypointSpeed>{float(auto_flight_speed):.0f}</wpml:waypointSpeed>
        <wpml:useGlobalHeadingParam>0</wpml:useGlobalHeadingParam>
        <wpml:waypointHeadingParam>
          <wpml:waypointHeadingMode>followWayline</wpml:waypointHeadingMode>
          <wpml:waypointHeadingAngle>0</wpml:waypointHeadingAngle>
          <wpml:waypointPoiPoint>0.000000,0.000000,0.000000</wpml:waypointPoiPoint>
          <wpml:waypointHeadingAngleEnable>1</wpml:waypointHeadingAngleEnable>
          <wpml:waypointHeadingPathMode>followBadArc</wpml:waypointHeadingPathMode>
          <wpml:waypointHeadingPoiIndex>0</wpml:waypointHeadingPoiIndex>
        </wpml:waypointHeadingParam>
        <wpml:useGlobalTurnParam>1</wpml:useGlobalTurnParam>
        <wpml:waypointTurnParam>
          <wpml:waypointTurnMode>toPointAndStopWithDiscontinuityCurvature</wpml:waypointTurnMode>
          <wpml:waypointTurnDampingDist>0</wpml:waypointTurnDampingDist>
        </wpml:waypointTurnParam>
        <wpml:useStraightLine>1</wpml:useStraightLine>
        <wpml:gimbalPitchAngle>0</wpml:gimbalPitchAngle>
      </Placemark>'''
        for i, p in enumerate(points_ll)
    )
    kml = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{NS_KML}" xmlns:wpml="{NS_WPML}">
  <Document>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>goHome</wpml:finishAction>
      <wpml:exitOnRCLost>goContinue</wpml:exitOnRCLost>
      <wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>
      <wpml:takeOffSecurityHeight>120</wpml:takeOffSecurityHeight>
      <wpml:takeOffRefPoint>{points_ll[0][1]:.6f},{points_ll[0][0]:.6f},{ref_alt:.3f}</wpml:takeOffRefPoint>
      <wpml:takeOffRefPointAGLHeight>0</wpml:takeOffRefPointAGLHeight>
      <wpml:globalTransitionalSpeed>15</wpml:globalTransitionalSpeed>
      <wpml:globalRTHHeight>{height:.0f}</wpml:globalRTHHeight>
      <wpml:droneInfo>
        <wpml:droneEnumValue>99</wpml:droneEnumValue>
        <wpml:droneSubEnumValue>1</wpml:droneSubEnumValue>
      </wpml:droneInfo>
      <wpml:waylineAvoidLimitAreaMode>0</wpml:waylineAvoidLimitAreaMode>
      <wpml:payloadInfo>
        <wpml:payloadEnumValue>89</wpml:payloadEnumValue>
        <wpml:payloadSubEnumValue>0</wpml:payloadSubEnumValue>
        <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
      </wpml:payloadInfo>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateType>waypoint</wpml:templateType>
      <wpml:templateId>0</wpml:templateId>
      <wpml:waylineCoordinateSysParam>
        <wpml:coordinateMode>WGS84</wpml:coordinateMode>
        <wpml:heightMode>EGM96</wpml:heightMode>
      </wpml:waylineCoordinateSysParam>
      <wpml:autoFlightSpeed>{float(auto_flight_speed):.0f}</wpml:autoFlightSpeed>
      <wpml:globalHeight>{height:.0f}</wpml:globalHeight>
      <wpml:caliFlightEnable>0</wpml:caliFlightEnable>
      <wpml:gimbalPitchMode>manual</wpml:gimbalPitchMode>
      <wpml:globalWaypointHeadingParam>
        <wpml:waypointHeadingMode>followWayline</wpml:waypointHeadingMode>
        <wpml:waypointHeadingAngle>0</wpml:waypointHeadingAngle>
        <wpml:waypointPoiPoint>0.000000,0.000000,0.000000</wpml:waypointPoiPoint>
        <wpml:waypointHeadingPathMode>followBadArc</wpml:waypointHeadingPathMode>
        <wpml:waypointHeadingPoiIndex>0</wpml:waypointHeadingPoiIndex>
      </wpml:globalWaypointHeadingParam>
      <wpml:globalWaypointTurnMode>toPointAndStopWithDiscontinuityCurvature</wpml:globalWaypointTurnMode>
      <wpml:globalUseStraightLine>1</wpml:globalUseStraightLine>
{placemarks}
      <wpml:payloadParam>
        <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
        <wpml:imageFormat>wide</wpml:imageFormat>
      </wpml:payloadParam>
    </Folder>
  </Document>
</kml>'''
    return kml.encode("utf-8")


def build_minimal_corridor_template(
    centerline_ll: List[Tuple[float, float]],
    half_width: float,
    height: float = 100.0,
) -> bytes:
    """为带状航线生成 KML 模板，含规划区域多边形（中心线向两侧外扩的带状）。

    Args:
        centerline_ll: 中心线顶点 [(lon, lat), ...]。
        half_width: 半宽 (m)。
        height: 飞行高度 (米)。

    Returns:
        KML 模板内容 (UTF-8 编码)，mapping2d 类型，含带状 Polygon。
    """
    if len(centerline_ll) < 2:
        return build_minimal_template_kml(centerline_ll, height=height, direction=0.0)
    ref_lon, ref_lat = centerline_ll[0]
    ll2xy = ll_to_xy_func(ref_lon, ref_lat)
    xy2ll = xy_to_ll_func(ref_lon, ref_lat)
    center_xy = np.array([ll2xy(lon, lat) for lon, lat in centerline_ll])
    band_xy = centerline_to_band_polygon_xy(center_xy, half_width)
    polygon_ll = [xy2ll(float(x), float(y)) for x, y in band_xy[:-1]]
    return build_minimal_template_kml(polygon_ll, height=height, direction=0.0)


def _append_waypoint_planner_extended_data(
    pm: ET.Element,
    pt_attrs: Optional[Dict[str, Any]],
) -> None:
    """规划器局部坐标与机体 roll/pitch 写入 Placemark 的 KML ExtendedData。

    DJI 公开 WPML 航点元素无机体滚转/俯仰标准字段；云台 yaw 使用 ``waypointGimbalYawAngle``。
    """
    if pt_attrs is None:
        return
    rows: List[Tuple[str, str]] = []
    for attr_key, data_name in (
        ("enu_x", "planner_enu_x_m"),
        ("enu_y", "planner_enu_y_m"),
        ("enu_z", "planner_enu_z_m"),
        ("aircraft_roll_deg", "aircraft_roll_deg"),
        ("aircraft_pitch_deg", "aircraft_pitch_deg"),
    ):
        if pt_attrs.get(attr_key) is None:
            continue
        try:
            rows.append((data_name, f"{float(pt_attrs[attr_key]):.6f}"))
        except (TypeError, ValueError):
            continue
    if not rows:
        return
    ext = ET.SubElement(pm, f"{K}ExtendedData")
    for data_name, text in rows:
        de = ET.SubElement(ext, f"{K}Data", {"name": data_name})
        ET.SubElement(de, f"{K}value").text = text


def _gimbal_pitch_from_template(tpl: ActionTemplate) -> Optional[float]:
    """从动作模板中提取云台俯仰角（用于 waypointGimbalHeadingParam）。"""
    for act in tpl.actions:
        params = act.get("params") or {}
        if isinstance(params, dict) and "gimbalPitchRotateAngle" in params:
            try:
                return float(params["gimbalPitchRotateAngle"])
            except (TypeError, ValueError):
                pass
    return None


def export_kmz(
    out_path: str,
    template_kml: bytes,
    template_wpml: Optional[bytes],
    waypoints: List[Tuple[float, float, float]],
    height: float = 100.0,
    auto_speed: float = 10.0,
    action_library: Optional[Dict[str, ActionTemplate]] = None,
    segment_start_indices: Optional[List[int]] = None,
    action_template_id: Optional[str] = None,
    mission_config: Optional[MissionConfig] = None,
    surface_follow: Optional[SurfaceFollowParams] = None,
    overlap_lateral: Optional[float] = None,
    overlap_longitudinal: Optional[float] = None,
    overlap_lateral_inclined: Optional[float] = None,
    overlap_longitudinal_inclined: Optional[float] = None,
    margin: Optional[float] = None,
    direction: Optional[float] = None,
    height_mode: Optional[str] = None,
    execute_height_mode: Optional[str] = None,
    capture_mode: Optional[str] = None,
    gimbal_pitch: Optional[float] = None,
    heading_mode: Optional[str] = None,
    heading_angle: Optional[float] = None,
    polygon_vertex_count: Optional[int] = None,
    extra_planning_params: Optional[dict] = None,
    patch_template_kml: bool = True,
    template_height_mode_wpml: Optional[str] = None,
    template_type_tag: Optional[str] = None,
    waypoint_wpml_attrs: Optional[List[Optional[Dict[str, Any]]]] = None,
    wpml_export_source: Optional[str] = None,
) -> None:
    """将航点序列导出为 KMZ 文件。若 out_path 已存在则覆盖。

    Args:
        out_path: 输出文件路径，同名文件将被覆盖。
        template_kml: KML 模板内容。
        template_wpml: WPML 模板内容，可为 None。
        waypoints: [(lon, lat, alt), ...] 航点序列。
        height: 默认高度 (米)。
        auto_speed: 自动飞行速度 (m/s)。
        action_library: 动作库 {template_id: ActionTemplate}，来自 read_kmz。
        segment_start_indices: 各航段首航点索引，如 [0, 15, 32]。
        action_template_id: 要使用的动作模板 id，不指定则用 photo_45 或默认。
        mission_config: 任务配置（F-006~F-014），覆盖模板中的 missionConfig。
        surface_follow: 仿地参数，写入 template.kml 的 waylineCoordinateSysParam。
        overlap_lateral: 旁向重叠率 0~1，写回 template.kml 形成闭环。
        overlap_longitudinal: 航向重叠率 0~1，写回 template.kml 形成闭环。
        margin: 边界内缩 (m)，写回 template.kml 形成闭环。
        direction: 航线方向 (°)，写回 template.kml 形成闭环。
        height_mode: API 语义高度模式（`relative_to_takeoff` | `relative_to_terrain` | `absolute`），
            与 `execute_height_mode` 的解析见 `resolve_height_export_modes`；与 `docs/开发计划.md` §十三、§十四 对齐。
        execute_height_mode: 遗留 DJI 字符串（`WGS84` / `relativeToStartPoint` / `realTimeFollowSurface`），
            在未传 `height_mode` 时参与解析。
        polygon_vertex_count: 多边形顶点数，写入 template.kml 的 ExtendedData（name=polygon_vertex_count）。
        template_height_mode_wpml: 若指定，则覆盖写入 template.kml 的 ``waylineCoordinateSysParam/heightMode``
            （仍与 waylines 的 ``resolve_height_export_modes`` 第一分量独立）。用于自建 ``mapping3d`` 模板与
            oblique 标准一致、避免被默认 ``EGM96`` 覆盖。
        waypoint_wpml_attrs: 与 ``waypoints`` 等长；索引 i 为 dict 时可含 ``heading_deg`` / ``speed_ms`` /
            ``gimbal_pitch_deg`` / ``gimbal_yaw_deg``（写 ``waypointGimbalYawAngle``）/
            ``enu_x`` ``enu_y`` ``enu_z``（米，与规划导出帧一致，写入 KML ExtendedData）/
            ``aircraft_roll_deg`` ``aircraft_pitch_deg``（度，写入 ExtendedData；无标准 wpml 航点字段）；
            ``None`` 表示该点沿用全局 ``heading_angle`` / ``auto_speed`` / 模板云台逻辑。
        wpml_export_source: 非空时在 INFO 级别记录本次 WPML 写出上下文（如 ``path_generator``）。
    """
    exec_h, tmpl_hm = resolve_height_export_modes(
        height_mode, execute_height_mode, surface_follow
    )
    if template_height_mode_wpml is not None and str(template_height_mode_wpml).strip():
        tmpl_hm = str(template_height_mode_wpml).strip()

    if wpml_export_source:
        _logger_kmz.info(
            "WPML 导出 [%s] out=%s waypoint_count=%s template_type_tag=%s execute_height_mode=%s template_height_mode=%s",
            wpml_export_source,
            out_path,
            len(waypoints),
            template_type_tag or "",
            exec_h or "",
            tmpl_hm or "",
        )

    if waypoint_wpml_attrs is not None and len(waypoint_wpml_attrs) != len(waypoints):
        raise ValueError("waypoint_wpml_attrs 须与 waypoints 等长")

    # 重要：当输入来自 KMZ 且你要求“不修改原始 KML”时，
    # 这里应跳过对 template.kml 的任何写回（只覆盖生成新的 WPML）。
    if patch_template_kml:
        if any(
            x is not None
            for x in (
                height,
                direction,
                overlap_lateral,
                overlap_longitudinal,
                overlap_lateral_inclined,
                overlap_longitudinal_inclined,
                margin,
            )
        ):
            template_kml = _apply_planning_params_to_template(
                template_kml,
                height,
                direction,
                overlap_lateral,
                overlap_longitudinal,
                overlap_lateral_inclined,
                overlap_longitudinal_inclined,
                margin,
            )
        if surface_follow is not None:
            template_kml = _apply_surface_follow_to_template(template_kml, surface_follow)
        template_kml = _apply_height_mode_to_template(template_kml, tmpl_hm)
        # 手柄兼容优先：不向 template.kml 注入内部 ExtendedData 扩展字段（如 polygon_vertex_count）。
        # 部分固件对非官方扩展字段解析兼容性较差，可能导致区域模板不显示。
        # template_kml = _apply_polygon_vertex_count_to_template(template_kml, polygon_vertex_count)
        if extra_planning_params:
            template_kml = _apply_extra_planning_params_to_template(template_kml, extra_planning_params)
        template_kml = _apply_template_type_to_template(template_kml, template_type_tag)
    root = ET.fromstring(template_kml)
    # capture_mode 需要写回 template.kml 的 shootType（time/distance）
    if capture_mode is not None:
        cm = str(capture_mode).strip().lower()
        if cm in ("time", "distance"):
            for elem in root.iter():
                if (elem.tag or "").endswith("shootType"):
                    elem.text = cm
            # 重要：把 root 的修改反序列化回 bytes，后面写 zip 才会生效
            template_kml = _to_kml_bytes(root)
    doc = root.find(f".//{K}Document") or root
    _remove_action_library_folders(doc)

    wpml_template_bytes = template_wpml
    template_type_norm = str(template_type_tag or "").strip()
    if wpml_template_bytes is None and template_type_norm == "mapping2d":
        standard_wpml_path = _mapping2d_standard_waylines_path()
        if standard_wpml_path.is_file():
            wpml_template_bytes = standard_wpml_path.read_bytes()

    wpml_root = ET.fromstring(wpml_template_bytes) if wpml_template_bytes else None
    if wpml_root is None:
        wpml_root = ET.Element("kml", attrib={"xmlns": NS_KML, "xmlns:wpml": NS_WPML})
        doc_w = ET.SubElement(wpml_root, "Document")
        ET.SubElement(doc_w, f"{W}missionConfig")
    else:
        doc_w = wpml_root.find(f".//{K}Document") or wpml_root

    mission_config_to_apply: Optional[MissionConfig] = mission_config
    if mission_config_to_apply is None and template_wpml is None:
        mission_config_to_apply = MissionConfig()
        if waypoints:
            lon0, lat0, alt0 = waypoints[0]
            mission_config_to_apply = mission_config_to_apply.with_take_off_ref_point(lat0, lon0, alt0)

    if mission_config_to_apply is not None:
        _apply_mission_config(
            doc,
            mission_config_to_apply,
            include_take_off_ref_fields=True,
            include_auto_reroute_info=False,
        )
        _apply_mission_config(
            doc_w,
            mission_config_to_apply,
            include_take_off_ref_fields=True,
            include_auto_reroute_info=True,
        )

    source_wayline_folder: Optional[ET.Element] = None
    for old_folder in list(doc_w.findall(f"{K}Folder")):
        if not _is_action_library_folder(old_folder) and source_wayline_folder is None:
            source_wayline_folder = old_folder
        doc_w.remove(old_folder)
    global_turn_mode, global_use_straight_line, point_turn_profiles = _extract_wpml_turn_profiles(
        source_wayline_folder
    )

    folder = ET.SubElement(doc_w, f"{K}Folder")
    ET.SubElement(folder, f"{W}templateId").text = "0"
    ET.SubElement(folder, f"{W}executeHeightMode").text = exec_h
    ET.SubElement(folder, f"{W}waylineId").text = "0"
    dist = path_length_m(waypoints)
    ET.SubElement(folder, f"{W}distance").text = f"{dist:.6f}"
    ET.SubElement(folder, f"{W}duration").text = f"{dist / max(1, auto_speed):.6f}"
    ET.SubElement(folder, f"{W}autoFlightSpeed").text = str(auto_speed)
    ET.SubElement(folder, f"{W}globalWaypointTurnMode").text = global_turn_mode
    ET.SubElement(folder, f"{W}globalUseStraightLine").text = global_use_straight_line

    # 选择动作模板
    template: Optional[ActionTemplate] = None
    if action_library and (action_template_id or "photo_45"):
        tid = action_template_id or "photo_45"
        template = action_library.get(tid)
    if template is None and (action_template_id or action_library):
        template = (
            get_photo_only_template()
            if action_template_id == "photo_only"
            else get_default_photo_template()
        )

    # 对 action 模板做可选覆盖（用于 P14/P15）
    if template is not None:
        if capture_mode is not None:
            # 仅覆盖触发类型：time -> multipleTiming；distance -> multipleDistance（interval 仍沿用模板 trigger_param）
            if str(capture_mode).lower() == "time":
                template.trigger_type = "multipleTiming"
            elif str(capture_mode).lower() == "distance":
                template.trigger_type = "multipleDistance"
        if gimbal_pitch is not None:
            # 覆盖 gimbalRotate 动作中的俯仰角参数（wpml: gimbalPitchRotateAngle）
            for act in template.actions:
                if not isinstance(act, dict):
                    continue
                if (act.get("func") or "").lower() != "gimbalrotate":
                    continue
                p = act.get("params")
                if isinstance(p, dict):
                    # 兼容默认模板字段名
                    if "gimbalPitchRotateAngle" in p:
                        p["gimbalPitchRotateAngle"] = str(float(gimbal_pitch))

    # 构建航段 (start, end) 列表
    seg_pairs: List[Tuple[int, int]] = []
    if segment_start_indices and len(segment_start_indices) > 0:
        for i, start in enumerate(segment_start_indices):
            end = (
                segment_start_indices[i + 1] - 1
                if i + 1 < len(segment_start_indices)
                else len(waypoints) - 1
            )
            if start <= end:
                seg_pairs.append((start, end))
    # 有模板但无航段信息时，整条航线作为单航段
    if template and not seg_pairs and len(waypoints) > 0:
        seg_pairs = [(0, len(waypoints) - 1)]
    segment_first = {s[0] for s in seg_pairs} if seg_pairs else set()

    heading_mode_norm = str(heading_mode or "followWayline").strip()
    if heading_mode_norm.lower() == "followwayline":
        heading_mode_norm = "followWayline"
    elif heading_mode_norm.lower() == "fixed":
        heading_mode_norm = "fixed"
    else:
        heading_mode_norm = "followWayline"
    heading_angle_norm = 0.0 if heading_angle is None else (float(heading_angle) % 360.0)
    # 与 mapping2d 标准模板对齐：即便 followWayline 也写 1，提高手柄兼容性。
    heading_angle_enable = "1"

    for idx, (lon, lat, alt) in enumerate(waypoints):
        point_turn_profile = point_turn_profiles.get(idx) or {}
        use_global_turn_param = str(
            point_turn_profile.get("use_global_turn_param") or "1"
        ).strip()
        use_straight_line = str(
            point_turn_profile.get("use_straight_line") or global_use_straight_line
        ).strip()
        # 与 DJI waypoint 字段口径对齐：显式写出 useGlobal* 控制位，
        # 并同步写点级高度/速度/航向参数，避免终端按隐式默认推断。
        use_global_height = "0"
        use_global_speed = "0"
        use_global_heading_param = "0"
        pm = ET.SubElement(folder, f"{K}Placemark")
        pt = ET.SubElement(pm, f"{K}Point")
        ET.SubElement(pt, f"{K}coordinates").text = f"{lon:.8f},{lat:.8f}"
        ET.SubElement(pm, f"{W}index").text = str(idx)
        ET.SubElement(pm, f"{W}useGlobalHeight").text = use_global_height
        ET.SubElement(pm, f"{W}ellipsoidHeight").text = f"{alt:.6f}"
        ET.SubElement(pm, f"{W}height").text = f"{alt:.6f}"
        ET.SubElement(pm, f"{W}executeHeight").text = f"{alt:.6f}"
        ET.SubElement(pm, f"{W}useGlobalSpeed").text = use_global_speed
        pt_attrs: Optional[Dict[str, Any]] = None
        if waypoint_wpml_attrs is not None and idx < len(waypoint_wpml_attrs):
            raw_attr = waypoint_wpml_attrs[idx]
            if isinstance(raw_attr, dict):
                pt_attrs = raw_attr
        pt_speed = float(auto_speed)
        if pt_attrs is not None and pt_attrs.get("speed_ms") is not None:
            pt_speed = float(pt_attrs["speed_ms"])
        ET.SubElement(pm, f"{W}waypointSpeed").text = str(pt_speed)
        ET.SubElement(pm, f"{W}useGlobalHeadingParam").text = use_global_heading_param
        hdg = ET.SubElement(pm, f"{W}waypointHeadingParam")
        ET.SubElement(hdg, f"{W}waypointHeadingMode").text = heading_mode_norm
        pt_heading_angle = heading_angle_norm
        if pt_attrs is not None and pt_attrs.get("heading_deg") is not None:
            pt_heading_angle = float(pt_attrs["heading_deg"]) % 360.0
        ET.SubElement(hdg, f"{W}waypointHeadingAngle").text = f"{pt_heading_angle:.0f}"
        ET.SubElement(hdg, f"{W}waypointPoiPoint").text = "0.000000,0.000000,0.000000"
        ET.SubElement(hdg, f"{W}waypointHeadingAngleEnable").text = heading_angle_enable
        ET.SubElement(hdg, f"{W}waypointHeadingPathMode").text = "followBadArc"
        ET.SubElement(hdg, f"{W}waypointHeadingPoiIndex").text = "0"
        if use_global_turn_param != "1":
            turn = ET.SubElement(pm, f"{W}waypointTurnParam")
            turn_mode = point_turn_profile.get("turn_mode") or global_turn_mode
            turn_damping_dist = point_turn_profile.get("turn_damping_dist")
            ET.SubElement(turn, f"{W}waypointTurnMode").text = str(turn_mode).strip()
            if turn_damping_dist is not None:
                ET.SubElement(turn, f"{W}waypointTurnDampingDist").text = str(turn_damping_dist).strip()
        ET.SubElement(pm, f"{W}useGlobalTurnParam").text = use_global_turn_param
        ET.SubElement(pm, f"{W}useStraightLine").text = use_straight_line
        # 若为首航点且该航段有动作模板，注入 actionGroup
        if template and idx in segment_first:
            seg_pair = next((p for p in seg_pairs if p[0] == idx), None)
            if seg_pair:
                ag = template.build_wpml_action_group(
                    start_index=seg_pair[0],
                    end_index=seg_pair[1],
                    group_id=0,
                )
                pm.append(ag)
        gim = ET.SubElement(pm, f"{W}waypointGimbalHeadingParam")
        gim_pitch = "0"
        if pt_attrs is not None and pt_attrs.get("gimbal_pitch_deg") is not None:
            gim_pitch = f"{float(pt_attrs['gimbal_pitch_deg']):.0f}"
        elif idx in segment_first:
            if gimbal_pitch is not None:
                gim_pitch = f"{float(gimbal_pitch):.0f}"
            elif template:
                pitch = _gimbal_pitch_from_template(template)
                if pitch is not None:
                    gim_pitch = f"{pitch:.0f}"
        ET.SubElement(gim, f"{W}waypointGimbalPitchAngle").text = gim_pitch
        gim_yaw = "0"
        if pt_attrs is not None and pt_attrs.get("gimbal_yaw_deg") is not None:
            gim_yaw = f"{float(pt_attrs['gimbal_yaw_deg']):.0f}"
        ET.SubElement(gim, f"{W}waypointGimbalYawAngle").text = gim_yaw
        # checklist 口径字段（部分模板/机型文档使用 gimbalPitchAngle 命名）
        ET.SubElement(pm, f"{W}gimbalPitchAngle").text = gim_pitch
        ET.SubElement(pm, f"{W}isRisky").text = "0"
        ET.SubElement(pm, f"{W}waypointWorkType").text = "0"
        _append_waypoint_planner_extended_data(pm, pt_attrs)

    template_kml = _to_kml_bytes(root)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("wpmz/template.kml", template_kml)
        z.writestr("wpmz/waylines.wpml", _to_kml_bytes(wpml_root))
