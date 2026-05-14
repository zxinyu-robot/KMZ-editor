# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 规划输入几何回显（input_geojson / input_kml / input_kml_json）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""将规划输入几何规范为 echo：``input_geojson``（仅 geometry + properties）与 KML（``input_kml`` / ``input_kml_json``）。

``input_geojson`` **不含** RFC 7946 的 ``type: "Feature"``。
**Polygon / LineString / Point** 均带 ``geometry.coordinates``，供前端可编辑区域或折线顶点；
``input_kml*`` 与之一致（同源生成），便于非 GeoJSON 消费端解析。
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Tuple

KML_XMLNS = 'xmlns="http://www.opengis.net/kml/2.2"'


def _positions_2d(ll: Optional[List[List[float]]]) -> List[List[float]]:
    out: List[List[float]] = []
    for p in ll or []:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            out.append([float(p[0]), float(p[1])])
    return out


def _close_ring(ring: List[List[float]]) -> List[List[float]]:
    if not ring:
        return ring
    if len(ring) >= 2 and ring[0] == ring[-1]:
        return ring
    return ring + [ring[0]]


def _slim_geometry_for_api(geom: Dict[str, Any], route_type: str = "") -> Dict[str, Any]:
    """API 用 geometry：面/线/点均保留 ``coordinates``（前端可编辑区域顶点）。"""
    _ = route_type  # 保留参数以兼容旧调用；回显策略不再按题型裁掉坐标
    gtype = geom.get("type")
    if gtype == "Point":
        return {"type": "Point", "coordinates": geom.get("coordinates")}
    if gtype == "LineString":
        return {"type": "LineString", "coordinates": geom.get("coordinates")}
    if gtype == "Polygon":
        return {"type": "Polygon", "coordinates": geom.get("coordinates")}
    return dict(geom)


def _input_echo_geometry_full(
    route_type: str,
    polygon_ll: Optional[List[List[float]]],
    params: Optional[Dict[str, Any]],
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """内部使用：带完整 ``coordinates`` 的 geometry + properties（供 KML 生成）。"""
    rt = (route_type or "").strip().lower()
    params = dict(params or {})
    props: Dict[str, Any] = {"route_type": rt}

    if rt == "cylinder" and not polygon_ll:
        c = params.get("center_ll")
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            geom: Dict[str, Any] = {
                "type": "Point",
                "coordinates": [float(c[0]), float(c[1])],
            }
            for k in ("radius", "height", "pitch", "flight_height"):
                if k in params and params[k] is not None:
                    try:
                        props[k] = float(params[k])
                    except (TypeError, ValueError):
                        props[k] = params[k]
            if params.get("geometry_mode") is not None:
                props["geometry_mode"] = params["geometry_mode"]
            return geom, props
        return None

    pts = _positions_2d(polygon_ll)
    if not pts:
        return None

    if rt == "waypoint":
        if len(pts) == 1:
            geom = {"type": "Point", "coordinates": pts[0]}
        else:
            geom = {"type": "LineString", "coordinates": pts}
        return geom, props

    if rt in ("corridor", "facade"):
        if len(pts) < 2:
            return None
        geom = {"type": "LineString", "coordinates": pts}
        return geom, props

    if rt in ("polygon", "mapping2d", "close_photography", "cylinder"):
        if len(pts) >= 3:
            ring = _close_ring(pts)
            if len(ring) >= 4:
                geom = {"type": "Polygon", "coordinates": [ring]}
            else:
                geom = {"type": "LineString", "coordinates": pts}
        elif len(pts) == 2:
            geom = {"type": "LineString", "coordinates": pts}
        else:
            geom = {"type": "Point", "coordinates": pts[0]}
        return geom, props

    return None


def build_input_echo_feature(
    route_type: str,
    polygon_ll: Optional[List[List[float]]],
    params: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """构造 ``input_geojson``：**仅** ``geometry`` + ``properties``；无 ``type: "Feature"``。

    ``geometry`` 含完整 ``coordinates``（面/线/点），供前端编辑测区或路径顶点。
    """
    full = _input_echo_geometry_full(route_type, polygon_ll, params)
    if full is None:
        return None
    geom_full, props = full
    return {
        "geometry": _slim_geometry_for_api(geom_full, route_type=route_type),
        "properties": props,
    }


def _kml_coord_text_2d(pts: List[List[float]], sep: str = " ") -> str:
    """KML coordinates：空格分隔三元组，高程 echo 为 0。"""
    return sep.join(f"{float(p[0]):.8f},{float(p[1]):.8f},0" for p in pts)


def _polygon_ring_unique_vertices(ring: List[List[float]]) -> List[List[float]]:
    """闭合环去重末尾重复点，便于输出顶点 Placemark。"""
    if len(ring) >= 2 and ring[0] == ring[-1]:
        return ring[:-1]
    return ring


# KML color 为 aabbggrr；与常见示例一致：线红色、点蓝色、面描边红+浅填充
_STYLE_LINE = """<Style id="path_editor_line">
    <LineStyle>
      <color>ffff0000</color>
      <width>2</width>
    </LineStyle>
    <PolyStyle>
      <fill>0</fill>
    </PolyStyle>
  </Style>"""
_STYLE_POINT = """<Style id="path_editor_point">
    <IconStyle>
      <scale>1.0</scale>
    </IconStyle>
    <LabelStyle>
      <scale>0.9</scale>
    </LabelStyle>
  </Style>"""
_STYLE_POLYGON = """<Style id="path_editor_polygon">
    <LineStyle>
      <color>ffff0000</color>
      <width>2</width>
    </LineStyle>
    <PolyStyle>
      <color>660088ff</color>
      <fill>1</fill>
      <outline>1</outline>
    </PolyStyle>
  </Style>"""

DOC_ID = "path_editor_input_echo"
DOC_NAME = "input-echo"
DOC_DESCRIPTION = "规划输入几何 echo；OGC KML 2.2"

_STYLE_JSON_LINE: Dict[str, Any] = {
    "id": "path_editor_line",
    "LineStyle": {"color": "ffff0000", "width": 2},
    "PolyStyle": {"fill": 0},
}
_STYLE_JSON_POINT: Dict[str, Any] = {
    "id": "path_editor_point",
    "IconStyle": {"scale": 1.0},
    "LabelStyle": {"scale": 0.9},
}
_STYLE_JSON_POLYGON: Dict[str, Any] = {
    "id": "path_editor_polygon",
    "LineStyle": {"color": "ffff0000", "width": 2},
    "PolyStyle": {"color": "660088ff", "fill": 1, "outline": 1},
}


def _xe(s: str) -> str:
    return html.escape(s, quote=False)


def _build_input_echo_parts(
    feat: Dict[str, Any],
) -> Optional[
    Tuple[
        List[Dict[str, Any]],
        str,
        List[Dict[str, Any]],
        List[str],
    ]
]:
    """自同一套数据生成 JSON 与 XML：键名与 KML 元素一致，仅 ``coordinates`` 字符串（与 XML 文本逐字相同）。"""
    geom = feat.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    rt = (feat.get("properties") or {}).get("route_type", "")
    desc = f"route_type={rt}"
    desc_x = _xe(desc)

    if gtype == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
        lon, lat = float(coords[0]), float(coords[1])
        coord_str = f"{lon:.8f},{lat:.8f},0"
        styles_j: List[Dict[str, Any]] = [_STYLE_JSON_POINT]
        styles_x = _STYLE_POINT
        folder_j = {
            "name": "输入点",
            "Placemark": [
                {
                    "name": "输入位置",
                    "description": desc,
                    "styleUrl": "#path_editor_point",
                    "Point": {"coordinates": coord_str},
                }
            ],
        }
        folder_x = f"""<Folder>
    <name>输入点</name>
    <Placemark>
      <name>输入位置</name>
      <description>{desc_x}</description>
      <styleUrl>#path_editor_point</styleUrl>
      <Point><coordinates>{coord_str}</coordinates></Point>
    </Placemark>
  </Folder>"""
        return styles_j, styles_x, [folder_j], [folder_x]

    if gtype == "LineString" and isinstance(coords, list) and len(coords) >= 2:
        line_txt = _kml_coord_text_2d(coords)
        styles_j = [_STYLE_JSON_LINE, _STYLE_JSON_POINT]
        styles_x = _STYLE_LINE + "\n  " + _STYLE_POINT
        main_j = {
            "name": "输入路径",
            "description": desc,
            "styleUrl": "#path_editor_line",
            "LineString": {"coordinates": line_txt},
        }
        main_x = f"""<Placemark>
      <name>输入路径</name>
      <description>{desc_x}</description>
      <styleUrl>#path_editor_line</styleUrl>
      <LineString><coordinates>{line_txt}</coordinates></LineString>
    </Placemark>"""
        vert_j: List[Dict[str, Any]] = []
        vert_x: List[str] = []
        for i, p in enumerate(coords):
            lo, la = float(p[0]), float(p[1])
            cs = f"{lo:.8f},{la:.8f},0"
            vert_j.append(
                {
                    "name": f"折点 {i + 1}",
                    "styleUrl": "#path_editor_point",
                    "Point": {"coordinates": cs},
                }
            )
            vert_x.append(
                f"""<Placemark>
      <name>折点 {i + 1}</name>
      <styleUrl>#path_editor_point</styleUrl>
      <Point><coordinates>{cs}</coordinates></Point>
    </Placemark>"""
            )
        folder1_j = {"name": "输入线", "Placemark": [main_j]}
        folder2_j = {"name": "折点", "Placemark": vert_j}
        folder1_x = f"""<Folder>
    <name>输入线</name>
    {main_x}
  </Folder>"""
        folder2_x = f"""<Folder>
    <name>折点</name>
    {chr(10).join(vert_x)}
  </Folder>"""
        return styles_j, styles_x, [folder1_j, folder2_j], [folder1_x, folder2_x]

    if gtype == "Polygon" and isinstance(coords, list) and coords:
        ring = coords[0]
        if not (isinstance(ring, list) and len(ring) >= 3):
            return None
        ring_f = [list(map(float, p[:2])) for p in ring]
        coord_block = _kml_coord_text_2d(ring_f, sep="\n")
        styles_j = [_STYLE_JSON_POLYGON, _STYLE_JSON_POINT]
        styles_x = _STYLE_POLYGON + "\n  " + _STYLE_POINT
        poly_j = {
            "name": "输入测区",
            "description": desc,
            "styleUrl": "#path_editor_polygon",
            "Polygon": {
                "outerBoundaryIs": {
                    "LinearRing": {"coordinates": coord_block},
                }
            },
        }
        poly_x = f"""<Placemark>
      <name>输入测区</name>
      <description>{desc_x}</description>
      <styleUrl>#path_editor_polygon</styleUrl>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              {coord_block}
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>"""
        uniq = _polygon_ring_unique_vertices(ring_f)
        vert_j = []
        vert_x = []
        for i, p in enumerate(uniq):
            cs = f"{p[0]:.8f},{p[1]:.8f},0"
            vert_j.append(
                {
                    "name": f"顶点 {i + 1}",
                    "styleUrl": "#path_editor_point",
                    "Point": {"coordinates": cs},
                }
            )
            vert_x.append(
                f"""<Placemark>
      <name>顶点 {i + 1}</name>
      <styleUrl>#path_editor_point</styleUrl>
      <Point><coordinates>{cs}</coordinates></Point>
    </Placemark>"""
            )
        folder1_j = {"name": "输入面", "Placemark": [poly_j]}
        folder2_j = {"name": "顶点", "Placemark": vert_j}
        folder1_x = f"""<Folder>
    <name>输入面</name>
    {poly_x}
  </Folder>"""
        folder2_x = f"""<Folder>
    <name>顶点</name>
    {chr(10).join(vert_x)}
  </Folder>"""
        return styles_j, styles_x, [folder1_j, folder2_j], [folder1_x, folder2_x]

    return None


def build_input_kml_json(
    route_type: str,
    polygon_ll: Optional[List[List[float]]],
    params: Optional[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """与 ``input_kml`` 严格同构：键名与 OGC KML 2.2 元素一致，无 ``type``/``positions`` 等冗余字段。

    ``coordinates`` 取值与对应 XML ``<coordinates>`` 文本内容完全相同（含空格/换行规则）。"""
    full = _input_echo_geometry_full(route_type, polygon_ll, params)
    if full is None:
        return None
    geom_full, props = full
    parts = _build_input_echo_parts({"geometry": geom_full, "properties": props})
    if parts is None:
        return None
    styles_j, _, folders_j, _ = parts
    document: Dict[str, Any] = {
        "id": DOC_ID,
        "name": DOC_NAME,
        "description": DOC_DESCRIPTION,
        "Style": styles_j,
        "Folder": folders_j,
    }
    return [document]


def build_input_echo_kml(
    route_type: str,
    polygon_ll: Optional[List[List[float]]],
    params: Optional[Dict[str, Any]],
) -> Optional[str]:
    """OGC KML 2.2；与 ``build_input_kml_json`` 共用同一套坐标与层级数据。"""
    full = _input_echo_geometry_full(route_type, polygon_ll, params)
    if full is None:
        return None
    geom_full, props = full
    parts = _build_input_echo_parts({"geometry": geom_full, "properties": props})
    if parts is None:
        return None
    _, styles_x, _, folders_x = parts
    body = "\n  ".join(folders_x)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml {KML_XMLNS}>
  <Document id="{DOC_ID}">
    <name>{_xe(DOC_NAME)}</name>
    <description>{_xe(DOC_DESCRIPTION)}</description>
  {styles_x}
  {body}
  </Document>
</kml>
"""
