# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: path_editor 后端调用接口
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""path_editor 后端调用接口。

供后端统一调用的入口，参数与返回值均为 JSON 可序列化结构。
算法按五层封装：geometry, params, algorithm, postprocess, output。
"""

from typing import List, Dict, Any, Optional, Union
from importlib import import_module

from .params import (
    parse_polygon_params,
    parse_cylinder_params,
    parse_corridor_params,
    parse_surface_follow_params,
)
from .params import CAMERA_PRESETS, calculate_gsd_cm_per_px, merge_planning_params
from .pipeline import (
    edit_route,
    edit_cylinder_route,
    edit_corridor_route,
)
from .echo_geojson import build_input_echo_feature, build_input_echo_kml, build_input_kml_json
from .io.reader import read_input
from ..response_util import path_editor_plan_fail


def _with_input_echo(
    route_type: str,
    polygon_ll: Optional[List[List[float]]],
    params: Optional[Dict[str, Any]],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(result)
    out["input_geojson"] = build_input_echo_feature(route_type, polygon_ll, params)
    out["input_kml"] = build_input_echo_kml(route_type, polygon_ll, params)
    out["input_kml_json"] = build_input_kml_json(route_type, polygon_ll, params)
    return out


def _polygon_vertex_count(polygon_ll: List[List[float]]) -> int:
    """返回多边形顶点数（若已闭合则不重复计数首尾点）。"""
    pts = [tuple(p[:2]) for p in (polygon_ll or []) if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        return len(pts) - 1
    return len(pts)


def _apply_gsd_cm_per_px_to_spacing(params: Dict[str, Any], camera_preset: str) -> None:
    """把 P02(GSD cm/px) 退化为固定条带间距 spacing（m）。

    当前面状算法只支持用 spacing + use_camera 控制条带间距生成。
    因此：如果用户提供 gsd_cm_per_px，就通过相机图幅宽度推导 spacing，并设置 use_camera=False。
    """
    gsd_cm_per_px = params.get("gsd_cm_per_px")
    if gsd_cm_per_px is None:
        return
    try:
        gsd_cm_per_px = float(gsd_cm_per_px)
    except (TypeError, ValueError):
        return
    if gsd_cm_per_px <= 0:
        return

    cam = CAMERA_PRESETS.get(camera_preset, {}) or {}
    if not cam:
        return

    # lateral 方向：使用 image_width 对应的覆盖宽度
    gsd_m_per_px = gsd_cm_per_px / 100.0
    img_w_px = float(cam.get("image_width", 5280))
    overlap_lateral = params.get("overlap_lateral", 0.7)
    try:
        overlap_lateral = float(overlap_lateral)
    except (TypeError, ValueError):
        overlap_lateral = 0.7
    if 1.0 < overlap_lateral <= 100.0:
        overlap_lateral = overlap_lateral / 100.0
    overlap_lateral = max(0.0, min(1.0, overlap_lateral))

    coverage_width_m = gsd_m_per_px * img_w_px
    spacing_m = coverage_width_m * (1.0 - overlap_lateral)
    params["spacing"] = float(spacing_m)
    params["use_camera"] = False


def _plan_generator_route(
    business_route_type: str,
    polygon_ll: List[List[float]],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """在 path_editor 内调用 path_generator 进行题型规划。"""
    try:
        gm = import_module("app.utils.path_planner.generator_mission")
        build_mission = gm.build_generator_mission_params
        ref_lon_lat_from_polygon_ll = gm.ref_lon_lat_from_polygon_ll
        project_waypoints = import_module("app.utils.path_planner.path_editor_bridge").project_generator_waypoints_to_llh
        plan_coverage = import_module("app.utils.path_generator.api").plan_coverage
    except ModuleNotFoundError as e:
        name = getattr(e, "name", None) or str(e)
        return _with_input_echo(
            business_route_type,
            polygon_ll,
            params,
            path_editor_plan_fail(
                f"无法加载 path_generator 依赖: {name}",
                segment_start_indices=[],
            ),
        )

    mission = build_mission(business_route_type, polygon_ll, dict(params or {}))
    result = plan_coverage(mission)
    if result.get("error"):
        return _with_input_echo(
            business_route_type,
            polygon_ll,
            params,
            path_editor_plan_fail(str(result.get("error")), segment_start_indices=[]),
        )

    ref_lon, ref_lat = ref_lon_lat_from_polygon_ll(polygon_ll)
    ref_alt = float(mission.get("region_ground_z", 0.0) or 0.0)
    _waypoints_enu, waypoints_ll = project_waypoints(
        result=result,
        ref_lon=ref_lon,
        ref_lat=ref_lat,
        ref_alt=ref_alt,
        region_only_enabled=bool(mission.get("region_only_enabled")),
        region_horizontal_frame=str(mission.get("region_horizontal_frame") or "projected_xy"),
    )
    out = [[float(lon), float(lat), float(alt)] for lon, lat, alt in waypoints_ll]

    if not out:
        return _with_input_echo(
            business_route_type,
            polygon_ll,
            params,
            path_editor_plan_fail("path_generator 未产生有效航点", segment_start_indices=[]),
        )
    return _with_input_echo(
        business_route_type,
        polygon_ll,
        params,
        {"waypoints": out, "count": len(out), "segment_start_indices": [0], "error": None},
    )


def edit_waypoints(
    waypoints: List[Union[List[float], tuple]],
    operations: List[Dict[str, Any]],
    default_height: float = 100.0,
) -> Dict[str, Any]:
    """逐点编辑航点：支持 add、delete、move、reorder 操作。

    Args:
        waypoints: 航点 [(lon, lat, alt), ...] 或 [[lon, lat, alt], ...]。
        operations: 操作列表，按顺序执行。
            - add: {"op": "add", "index": i, "lon": x, "lat": y, "alt": z} 在 index 处插入
            - delete: {"op": "delete", "index": i}
            - move: {"op": "move", "index": i, "lon": x, "lat": y, "alt": z}
            - reorder: {"op": "reorder", "indices": [2,0,1]} 按旧索引重排
        default_height: 新增航点默认高度。

    Returns:
        成功时 {"waypoints": [...], "count": N, "error": None}；
        失败时 {"waypoints": [], "count": 0, "error": "错误信息"}。
    """
    try:
        wps = [(float(w[0]), float(w[1]), float(w[2]) if len(w) >= 3 else default_height) for w in waypoints]
    except (IndexError, TypeError, ValueError) as e:
        return {"waypoints": [], "count": 0, "error": f"航点格式错误: {e}"}

    for op in operations:
        op_type = (op.get("op") or "").lower()
        if op_type == "add":
            idx = int(op.get("index", len(wps)))
            lon = float(op.get("lon", 0))
            lat = float(op.get("lat", 0))
            alt = float(op.get("alt", default_height))
            idx = max(0, min(idx, len(wps)))
            wps.insert(idx, (lon, lat, alt))
        elif op_type == "delete":
            idx = int(op.get("index", -1))
            if 0 <= idx < len(wps):
                wps.pop(idx)
        elif op_type == "move":
            idx = int(op.get("index", -1))
            if 0 <= idx < len(wps):
                lon = op.get("lon")
                lat = op.get("lat")
                alt = op.get("alt")
                old = wps[idx]
                wps[idx] = (
                    float(lon) if lon is not None else old[0],
                    float(lat) if lat is not None else old[1],
                    float(alt) if alt is not None else old[2],
                )
        elif op_type == "reorder":
            indices = op.get("indices") or []
            if len(indices) != len(wps):
                return {"waypoints": [], "count": 0, "error": "reorder 的 indices 数量须与航点数一致"}
            try:
                new_wps = [wps[int(i)] for i in indices]
            except (IndexError, ValueError):
                return {"waypoints": [], "count": 0, "error": "reorder indices 无效"}
            wps = new_wps

    return {
        "waypoints": [[float(x), float(y), float(z)] for x, y, z in wps],
        "count": len(wps),
        "error": None,
    }


def plan_waypoint(
    points_ll: List[List[float]],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """航点航线规划：点序列直接转为航点，无扫线算法。

    Args:
        points_ll: 航点序列 [[lon, lat], ...]，至少 1 个点。
        params: 可选参数字典，含 height（默认 100）。

    Returns:
        成功时 {"waypoints": [...], "count": N, "segment_start_indices": [0], "error": None}；
        失败时 {"waypoints": [], "count": 0, "error": "错误信息"}。
    """
    pts = [tuple(p[:2]) for p in points_ll]
    if len(pts) < 1:
        return _with_input_echo(
            "waypoint",
            [list(p[:2]) for p in (points_ll or [])],
            params,
            {"waypoints": [], "count": 0, "segment_start_indices": [], "error": "航点至少需要1个点"},
        )

    height = 100.0
    if params:
        height = float(params.get("height", height))

    waypoints = [(float(lon), float(lat), height) for lon, lat in pts]
    wps = [[float(x), float(y), float(z)] for x, y, z in waypoints]
    return _with_input_echo(
        "waypoint",
        [list(p[:2]) for p in points_ll],
        params,
        {
            "waypoints": wps,
            "count": len(wps),
            "segment_start_indices": [0],
            "error": None,
        },
    )


def plan_polygon(
    polygon_ll: List[List[float]],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """二维面状航线规划，后端调用接口。

    参数通过 parse_polygon_params 统一解析。

    Args:
        polygon_ll: 多边形顶点 [[lon, lat], ...]，至少 3 个点。
        params: 可选参数字典，见 PolygonParams / parse_polygon_params。

    Returns:
        成功时 {"waypoints": [...], "count": N, "error": None}；
        失败时 {"waypoints": [], "count": 0, "error": "错误信息"}。
    """
    poly_tuples = [tuple(p[:2]) for p in polygon_ll]
    vertex_count = _polygon_vertex_count(polygon_ll)
    if len(poly_tuples) < 3:
        return _with_input_echo(
            "polygon",
            [list(p[:2]) for p in (polygon_ll or [])],
            params,
            {
                "waypoints": [],
                "count": 0,
                "polygon_vertex_count": vertex_count,
                "error": "多边形至少需要3个顶点",
            },
        )

    # 若外层传入 gsd_cm_per_px(P02)，则把它退化为固定 spacing（use_camera=False），确保参与规划。
    params = dict(params or {})
    if "gsd_cm_per_px" in params and params.get("gsd_cm_per_px") is not None:
        camera_preset = params.get("camera_preset") or "m3e"
        _apply_gsd_cm_per_px_to_spacing(params, camera_preset)

    p = parse_polygon_params(params)
    errs = p.validate()
    if errs:
        return _with_input_echo(
            "polygon",
            [list(p[:2]) for p in polygon_ll],
            params,
            {"waypoints": [], "count": 0, "polygon_vertex_count": vertex_count, "error": "; ".join(errs)},
        )

    try:
        kwargs = p.to_edit_route_kwargs()
        computed_gsd_cm_per_px = None
        computed_gsd_lon_cm_per_px = None
        if p.use_camera:
            cam = p.camera or CAMERA_PRESETS.get(p.camera_preset or "m3e", {})
            if cam:
                computed_gsd_cm_per_px = calculate_gsd_cm_per_px(
                    height=p.height, camera=cam, direction="lateral"
                )
                computed_gsd_lon_cm_per_px = calculate_gsd_cm_per_px(
                    height=p.height, camera=cam, direction="longitudinal"
                )
        waypoints, segment_start_indices = edit_route(polygon_ll=poly_tuples, **kwargs)
        if p.with_timestamps and waypoints and len(waypoints[0]) >= 4:
            wps = [[float(w[0]), float(w[1]), float(w[2]), float(w[3])] for w in waypoints]
        else:
            wps = [[float(x), float(y), float(z)] for x, y, z in waypoints]
        return _with_input_echo(
            "polygon",
            [list(p[:2]) for p in polygon_ll],
            params,
            {
                "waypoints": wps,
                "count": len(wps),
                "polygon_vertex_count": vertex_count,
                "segment_start_indices": segment_start_indices,
                "error": None,
                "computed_gsd_cm_per_px": computed_gsd_cm_per_px,
                "computed_gsd_lon_cm_per_px": computed_gsd_lon_cm_per_px,
            },
        )
    except Exception as e:
        return _with_input_echo(
            "polygon",
            [list(p[:2]) for p in polygon_ll],
            params,
            {"waypoints": [], "count": 0, "polygon_vertex_count": vertex_count, "error": str(e)},
        )


def plan_cylinder(params: Dict[str, Any]) -> Dict[str, Any]:
    """圆柱体航线规划（默认表面扫掠，兼容螺旋），后端调用接口。

    参数通过 parse_cylinder_params 统一解析。

    Args:
        params: 参数字典，须含 center_ll, radius, height, pitch；可选 geometry_mode、home_ll、append_centroid。

    Returns:
        成功时 {"waypoints": [...], "count": N, "error": None}；
        失败时 {"waypoints": [], "count": 0, "error": "错误信息"}。
    """
    try:
        p = parse_cylinder_params(params)
        errs = p.validate()
        if errs:
            return _with_input_echo("cylinder", None, params, {"waypoints": [], "count": 0, "error": "; ".join(errs)})
        waypoints = edit_cylinder_route(
            center_ll=p.center_ll,
            radius=p.radius,
            height=p.height,
            pitch=p.pitch,
            start_z=p.start_z,
            points_per_rev=p.points_per_rev,
            flight_height=p.flight_height,
            geometry_mode=p.geometry_mode,
            home_ll=p.home_ll,
            append_centroid=p.append_centroid,
            with_timestamps=p.with_timestamps,
            flight_speed=p.flight_speed,
            reference_time=p.reference_time,
        )
        if p.with_timestamps and waypoints and len(waypoints[0]) >= 4:
            wps = [[float(w[0]), float(w[1]), float(w[2]), float(w[3])] for w in waypoints]
        else:
            wps = [[float(x), float(y), float(z)] for x, y, z in waypoints]
        return _with_input_echo("cylinder", None, params, {"waypoints": wps, "count": len(wps), "error": None})
    except Exception as e:
        return _with_input_echo("cylinder", None, params, {"waypoints": [], "count": 0, "error": str(e)})


def plan_corridor(
    centerline_ll: List[List[float]],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """带状航线规划，沿中心线扫线。

    Args:
        centerline_ll: 中心线顶点 [[lon, lat], ...]，至少 2 个点。
        params: 可选参数字典，见 CorridorParams / parse_corridor_params。

    Returns:
        成功时 {"waypoints": [...], "count": N, "segment_start_indices": [...], "error": None}；
        失败时 {"waypoints": [], "count": 0, "error": "错误信息"}。
    """
    pts = [tuple(p[:2]) for p in centerline_ll]
    if len(pts) < 2:
        return _with_input_echo(
            "corridor",
            [list(p[:2]) for p in (centerline_ll or [])],
            params,
            {"waypoints": [], "count": 0, "segment_start_indices": [], "error": "中心线至少需要2个顶点"},
        )

    p = parse_corridor_params(params)
    errs = p.validate()
    if errs:
        return _with_input_echo(
            "corridor",
            [list(p[:2]) for p in centerline_ll],
            params,
            {"waypoints": [], "count": 0, "segment_start_indices": [], "error": "; ".join(errs)},
        )

    try:
        kwargs = {
            "centerline_ll": pts,
            "half_width": p.half_width,
            "lateral_spacing": p.lateral_spacing,
            "height": p.height,
            "baseline": p.baseline,
            "longitudinal_spacing": p.longitudinal_spacing,
            "use_camera": p.use_camera,
            "camera": p.camera,
            "camera_preset": p.camera_preset,
            "overlap_lateral": p.overlap_lateral,
            "overlap_longitudinal": p.overlap_longitudinal,
            "with_timestamps": p.with_timestamps,
            "flight_speed": p.flight_speed,
            "reference_time": p.reference_time,
        }
        waypoints, segment_start_indices = edit_corridor_route(**kwargs)
        if p.with_timestamps and waypoints and len(waypoints[0]) >= 4:
            wps = [[float(w[0]), float(w[1]), float(w[2]), float(w[3])] for w in waypoints]
        else:
            wps = [[float(x), float(y), float(z)] for x, y, z in waypoints]
        return _with_input_echo(
            "corridor",
            [list(p[:2]) for p in centerline_ll],
            params,
            {
                "waypoints": wps,
                "count": len(wps),
                "segment_start_indices": segment_start_indices,
                "error": None,
            },
        )
    except Exception as e:
        return _with_input_echo(
            "corridor",
            [list(p[:2]) for p in centerline_ll],
            params,
            {"waypoints": [], "count": 0, "segment_start_indices": [], "error": str(e)},
        )


def plan_close_photography(
    polygon_ll: List[List[float]],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """贴近摄影航线规划（通过 path_generator）。"""
    pts = [p for p in (polygon_ll or []) if isinstance(p, (list, tuple)) and len(p) >= 2]
    req = dict(params or {})
    ll2 = [list(p[:2]) for p in pts]
    if len(pts) < 3:
        return _with_input_echo(
            "close_photography",
            ll2,
            req,
            {"waypoints": [], "count": 0, "segment_start_indices": [], "error": "close_photography 至少需要3个坐标点"},
        )
    sf_dict = req.get("surface_follow")
    if not isinstance(sf_dict, dict):
        return _with_input_echo(
            "close_photography",
            ll2,
            req,
            {
                "waypoints": [],
                "count": 0,
                "segment_start_indices": [],
                "error": "close_photography 需要 options.surface_follow 对象",
            },
        )
    sf = parse_surface_follow_params(sf_dict)
    if not sf.surface_follow_enable:
        return _with_input_echo(
            "close_photography",
            ll2,
            req,
            {
                "waypoints": [],
                "count": 0,
                "segment_start_indices": [],
                "error": "close_photography 要求 surface_follow_enable=true",
            },
        )
    return _plan_generator_route("close_photography", ll2, req)


def plan_facade(
    polygon_ll: List[List[float]],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """斜面航线规划（通过 path_generator）。"""
    pts = [p for p in (polygon_ll or []) if isinstance(p, (list, tuple)) and len(p) >= 2]
    facade_pts = [list(p[:3]) if len(p) >= 3 else list(p[:2]) for p in pts]
    pr = dict(params or {})
    if len(pts) < 2:
        return _with_input_echo(
            "facade",
            facade_pts,
            pr,
            {"waypoints": [], "count": 0, "segment_start_indices": [], "error": "facade 至少需要2个坐标点"},
        )
    return _plan_generator_route("facade", facade_pts, pr)


def check_route_safety_api(
    waypoints_xy: List[List[float]],
    dsm_path: str,
    meta_path: Optional[str] = None,
    safety_buffer: float = 5.0,
) -> Dict[str, Any]:
    """航线安全检测 API：八分角算法检测各航段与地形的安全隐患。

    Args:
        waypoints_xy: 航点 [(x, y, z), ...]，平面坐标与 DSM 同 CRS。
        dsm_path: DSM .npy 路径或目录。
        meta_path: meta.json 路径，None 时自动推断。
        safety_buffer: 安全缓冲 L (m)。

    Returns:
        {"segment_safe": [...], "failed_octants": [...], "min_clearances": [...], "all_safe": bool, "error": str?}
    """
    from pathlib import Path

    from .geometry import load_dsm, check_route_safety

    dsm, meta = load_dsm(Path(dsm_path), Path(meta_path) if meta_path else None)
    if dsm is None or meta is None:
        return {
            "segment_safe": [],
            "failed_octants": [],
            "min_clearances": [],
            "all_safe": False,
            "error": "无法加载 DSM",
        }
    wps = [tuple(w[:3]) for w in waypoints_xy]
    segment_safe, failed_octants, min_clearances = check_route_safety(
        wps, dsm, meta, safety_buffer=safety_buffer
    )
    return {
        "segment_safe": segment_safe,
        "failed_octants": failed_octants,
        "min_clearances": [float(c) if c != float("inf") else None for c in min_clearances],
        "all_safe": all(segment_safe),
        "error": None,
    }


def plan(
    route_type: str,
    polygon_ll: Optional[List[List[float]]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """统一入口：根据航线类型分发到具体算法。

    Args:
        route_type: "polygon"、"waypoint"、"cylinder"、"corridor"、"close_photography"、"facade"。
        polygon_ll: 多边形顶点（polygon/cylinder/close_photography）、航点序列（waypoint）或中心线（corridor/facade）。
        params: 参数字典。

    Returns:
        同 plan_polygon / plan_waypoint / plan_cylinder / plan_corridor 的返回值。
    """
    params = params or {}
    if route_type == "polygon":
        if polygon_ll is None:
            return {
                "waypoints": [],
                "count": 0,
                "error": "polygon 类型需要 polygon_ll 参数",
                "input_geojson": None,
                "input_kml": None,
                "input_kml_json": None,
            }
        return plan_polygon(polygon_ll, params)
    if route_type == "waypoint":
        if polygon_ll is None:
            return {
                "waypoints": [],
                "count": 0,
                "error": "waypoint 类型需要 points_ll 参数",
                "input_geojson": None,
                "input_kml": None,
                "input_kml_json": None,
            }
        return plan_waypoint(polygon_ll, params)
    if route_type == "cylinder":
        return {
            "waypoints": [],
            "count": 0,
            "error": "cylinder 已弃用",
            "input_geojson": None,
            "input_kml": None,
            "input_kml_json": None,
        }
    if route_type == "corridor":
        if polygon_ll is None:
            return {
                "waypoints": [],
                "count": 0,
                "error": "corridor 类型需要 centerline_ll 参数",
                "input_geojson": None,
                "input_kml": None,
                "input_kml_json": None,
            }
        return plan_corridor(polygon_ll, params)
    if route_type == "close_photography":
        if polygon_ll is None:
            return {
                "waypoints": [],
                "count": 0,
                "error": "close_photography 类型需要 polygon_ll 参数",
                "input_geojson": None,
                "input_kml": None,
                "input_kml_json": None,
            }
        return plan_close_photography(polygon_ll, params)
    if route_type == "facade":
        if polygon_ll is None:
            return {
                "waypoints": [],
                "count": 0,
                "error": "facade 类型需要 coordinates 参数",
                "input_geojson": None,
                "input_kml": None,
                "input_kml_json": None,
            }
        return plan_facade(polygon_ll, params)
    return {
        "waypoints": [],
        "count": 0,
        "error": f"不支持的航线类型: {route_type}",
        "input_geojson": None,
        "input_kml": None,
        "input_kml_json": None,
    }


def plan_from_file(
    input_path: str,
    route_type: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """文件输入便捷接口：读取输入文件并直接调用对应规划算法。

    现阶段用于兼容前端 `input_path` 提交方式：
    - 读取 `input_path`（KML/KMZ/GeoJSON/JSON）
    - 从 reader 得到 polygon_ll 与 raw_params
    - raw_params 与 params 按规划参数合并规则合并
    - 若 raw_params 中提供了 `gsd_cm_per_px`（P02），则退化为固定 spacing
    - 调用 plan(route_type, polygon_ll, merged_params)
    """
    tpl_kml, tpl_wpml, polygon_ll, raw_params = read_input(input_path)
    merged_params = merge_planning_params(kmz_params=raw_params, cli_params=params or {})

    # 若前端在 GeoJSON 的 properties 里传了 P02(GSD)，则把它退化为固定 spacing
    # （算法层当前仅支持 spacing，用 use_camera=False 控制走固定 spacing 分支）
    if "gsd_cm_per_px" in raw_params:
        camera_preset = merged_params.get("camera_preset") or "m3e"
        merged_params["gsd_cm_per_px"] = raw_params.get("gsd_cm_per_px")
        _apply_gsd_cm_per_px_to_spacing(merged_params, camera_preset)

    if route_type == "polygon":
        return plan_polygon([list(p[:2]) for p in polygon_ll], merged_params)
    if route_type == "waypoint":
        return plan_waypoint([list(p[:2]) for p in polygon_ll], merged_params)
    if route_type == "corridor":
        return plan_corridor([list(p[:2]) for p in polygon_ll], merged_params)
    if route_type == "close_photography":
        return plan_close_photography([list(p[:2]) for p in polygon_ll], merged_params)
    if route_type == "facade":
        return plan_facade([list(p[:2]) for p in polygon_ll], merged_params)
    if route_type == "cylinder":
        return {
            "waypoints": [],
            "count": 0,
            "error": "cylinder 已弃用",
            "input_geojson": None,
            "input_kml": None,
            "input_kml_json": None,
        }

    return {
        "waypoints": [],
        "count": 0,
        "error": f"不支持的航线类型: {route_type}",
        "input_geojson": None,
        "input_kml": None,
        "input_kml_json": None,
    }
