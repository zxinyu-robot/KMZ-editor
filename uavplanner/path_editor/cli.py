#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: path_editor CLI 入口（多题型规划与导出）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""
path_editor CLI 入口（迁移版本）

支持面状、航点、圆柱、带状四种航线类型。
输入路径支持：绝对路径、相对当前目录、或相对项目根目录。

推荐用法（在项目根目录执行）:
    python3 -m backend.app.utils.path_editor.cli polygon examples/data/waypoints.geojson --spacing 15
"""

import sys
import json
from pathlib import Path

from .io import read_input
from .output import export_kmz
from .params import resolve_spacing, resolve_longitudinal_spacing, merge_planning_params
from .output.kmz import build_minimal_corridor_template, build_minimal_waypoint_template
from .api import plan_polygon, plan_waypoint, plan_cylinder, plan_corridor, edit_waypoints
from .params import parse_mission_config, parse_surface_follow_params
from .geometry import load_dsm, apply_dsm_to_waypoints, ll_to_xy_func


def _parse_center(s: str) -> tuple:
    parts = s.strip().split(",")
    if len(parts) != 2:
        raise ValueError("--center 格式须为 LON,LAT，如 120.15,30.28")
    return (float(parts[0].strip()), float(parts[1].strip()))


def _resolve_input_path(path: str) -> str:
    """解析输入路径：若不存在则尝试相对于项目根目录。"""
    p = Path(path)
    if p.exists():
        return str(p.resolve())
    repo_root = Path(__file__).resolve().parents[5]  # backend/app/utils/path_editor/cli.py → 项目根
    alt = repo_root / path
    if alt.exists():
        return str(alt.resolve())
    raise FileNotFoundError(path)


def _print_spacing_info(params: dict, result: dict, polygon_vertex_count: int | None = None) -> None:
    """打印实际使用的条带间距与航向采样间距（便于排查 GSD 问题）。"""
    from .params.config import CAMERA_PRESETS

    use_fixed = not params.get("use_camera", True)
    lat = resolve_spacing(
        params["spacing"],
        params["height"],
        camera=None,
        camera_preset=params.get("camera_preset"),
        overlap_lateral=params.get("overlap_lateral", 0.7),
        use_fixed_spacing=use_fixed,
    )
    lon = resolve_longitudinal_spacing(
        params["spacing"],
        params["height"],
        camera=None,
        camera_preset=params.get("camera_preset"),
        overlap_longitudinal=params.get("overlap_longitudinal", 0.8),
        use_fixed_spacing=use_fixed,
    )
    preset = params.get("camera_preset") or "m3e"
    cam = CAMERA_PRESETS.get(preset, {})
    gsd_lat = (
        (params["height"] * cam.get("sensor_width", 17.3))
        / (cam.get("focal_length", 24) * cam.get("image_width", 5280))
        if cam
        else 0
    )
    info_prefix = ""
    if polygon_vertex_count is not None:
        info_prefix = f"多边形顶点数: {polygon_vertex_count} | "
    print(
        f"[INFO] {info_prefix}条带间距(旁向): {lat:.2f} m | 航向采样间距: {lon:.2f} m | 规划航点数: {result.get('count', 0)}"
        f"{f' | GSD≈{gsd_lat*100:.2f} cm/px' if not use_fixed and cam else ''}"
    )


def _add_common_args(ap):
    ap.add_argument("-o", "--output", default="work_dir/kmz_exports/pathEdited.kmz", help="输出 KMZ（驼峰命名，兼容司空）")
    ap.add_argument("--action-template", default=None, help="动作模板 id，如 photo_45、photo_only")
    ap.add_argument("--fly-to-mode", choices=("safely", "pointToPoint"), help="F-006 飞向首航点模式")
    ap.add_argument("--finish-action", choices=("goHome", "autoLand", "hover", "noAction", "gotoFirstWaypoint"), help="F-007 完成动作")
    ap.add_argument("--exit-on-rc-lost", choices=("goContinue", "executeLostAction"), help="F-009 航线失联行为")
    ap.add_argument("--execute-rc-lost-action", choices=("goBack", "hover", "landing"), help="F-008 失控动作")
    ap.add_argument("--take-off-security-height", type=float, help="F-013 安全起飞高度 (m)")
    ap.add_argument("--global-rth-height", type=float, help="返航高度 (m)")


def _run_corridor(args):
    tpl_kml, tpl_wpml, coords_ll, raw_params = read_input(_resolve_input_path(args.input))
    centerline_ll = [list(p[:2]) for p in coords_ll]
    if len(centerline_ll) < 2:
        print("[ERROR] 中心线至少需要2个顶点")
        sys.exit(1)
    params = {
        "half_width": args.half_width,
        "lateral_spacing": args.lateral_spacing,
        "baseline": args.baseline,
        "height": raw_params.get("height", args.height),
        "use_camera": args.use_camera,
        "camera_preset": args.camera_preset,
    }
    result = plan_corridor(centerline_ll, params)
    if result["error"]:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
    waypoints = [tuple(w[:3]) for w in result["waypoints"]]
    if args.dsm:
        dsm_path = Path(args.dsm)
        meta_path = Path(args.dsm_meta) if args.dsm_meta else None
        dsm, meta = load_dsm(dsm_path, meta_path)
        if dsm is not None and meta is not None:
            ref_lon, ref_lat = waypoints[0][0], waypoints[0][1]
            ll2xy = ll_to_xy_func(ref_lon, ref_lat)
            surf_height = args.surface_relative_height
            if raw_params.get("surface_follow", {}).get("surface_relative_height") is not None:
                surf_height = raw_params["surface_follow"]["surface_relative_height"]
            waypoints = apply_dsm_to_waypoints(waypoints, dsm, meta, ll2xy, surf_height)
        else:
            print("[WARN] DSM 加载失败，使用固定高度")
    tpl_kml = build_minimal_corridor_template(
        centerline_ll,
        half_width=args.half_width,
        height=params.get("height", 100.0),
    )
    surface_params = dict(raw_params.get("surface_follow") or {})
    if args.surface_follow or args.dsm:
        surface_params["surface_follow_enable"] = True
    if args.surface_relative_height is not None:
        surface_params["surface_relative_height"] = args.surface_relative_height
    surface_follow = parse_surface_follow_params(surface_params) if surface_params else None
    mission_config = parse_mission_config(dict(raw_params.get("mission_config") or {})) or None
    export_kmz(
        out_path=args.output,
        template_kml=tpl_kml,
        template_wpml=tpl_wpml,
        waypoints=waypoints,
        height=params.get("height", 100.0),
        auto_speed=raw_params.get("auto_speed", 10.0),
        action_library=raw_params.get("action_library"),
        segment_start_indices=result.get("segment_start_indices"),
        action_template_id=args.action_template or "photo_45",
        mission_config=mission_config,
        surface_follow=surface_follow,
    )
    print(f"[OK] 已导出: {args.output}")


def _run_cylinder(args):
    try:
        center = _parse_center(args.center)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    home_ll = None
    if getattr(args, "home", None):
        try:
            home_ll = _parse_center(args.home)
        except ValueError as e:
            print(f"[ERROR] --home {e}")
            sys.exit(1)
    params = {
        "center_ll": center,
        "radius": args.radius,
        "height": args.height,
        "pitch": args.pitch,
        "start_z": args.start_z,
        "points_per_rev": args.points_per_rev,
        "flight_height": args.flight_height,
        "geometry_mode": args.geometry_mode,
        "home_ll": home_ll,
        "append_centroid": bool(getattr(args, "append_centroid", False)),
    }
    result = plan_cylinder(params)
    if result["error"]:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
    waypoints = [tuple(w[:3]) for w in result["waypoints"]]
    tpl_kml = build_minimal_waypoint_template(
        waypoints,
        height=args.height or 100.0,
    )
    mission_config = (
        parse_mission_config(
            {
                "take_off_security_height": args.take_off_security_height,
                "global_rth_height": args.global_rth_height,
            }
        )
        if (args.take_off_security_height or args.global_rth_height)
        else None
    )
    export_kmz(
        out_path=args.output,
        template_kml=tpl_kml,
        template_wpml=None,
        waypoints=waypoints,
        height=args.height or 100.0,
        auto_speed=10.0,
        action_library=None,
        segment_start_indices=[0],
        action_template_id=args.action_template or "photo_45",
        mission_config=mission_config,
    )
    print(f"[OK] 已导出: {args.output}")


def _run_polygon_or_waypoint(args, mode: str):
    input_path = _resolve_input_path(args.input)
    tpl_kml, tpl_wpml, coords_ll, raw_params = read_input(input_path)
    # 约束：当输入来自 KMZ 时，不允许改写原始 wpmz/template.kml
    patch_template_kml = Path(input_path).suffix.lower() != ".kmz"
    input_type = raw_params.get("input_type", "polygon")
    if mode == "waypoint" and input_type != "waypoint":
        print("[WARN] 输入非航点格式，将按多边形处理。指定 waypoint 子命令时建议使用 MultiPoint/点数组。")
    if mode == "polygon" and input_type == "waypoint":
        print("[WARN] 输入为航点格式，将按航点处理。")

    if input_type == "waypoint":
        waypoints_3d = raw_params.get("waypoints_3d")
        if waypoints_3d:
            result = {
                "waypoints": [[w[0], w[1], w[2]] for w in waypoints_3d],
                "segment_start_indices": [0],
                "error": None,
            }
        else:
            params = {"height": raw_params.get("height", 100.0)}
            result = plan_waypoint([list(p[:2]) for p in coords_ll], params)
        if getattr(args, "edit", None) and not result["error"]:
            edit_path = Path(args.edit)
            if edit_path.exists():
                edit_data = json.loads(edit_path.read_text(encoding="utf-8"))
                ops = edit_data.get("operations") if isinstance(edit_data, dict) else edit_data
                if isinstance(ops, list) and ops:
                    result = edit_waypoints(result["waypoints"], ops, raw_params.get("height", 100.0))
                    result["segment_start_indices"] = [0]
        action_template = args.action_template or "photo_only"
    else:
        use_camera = not getattr(args, "fixed_spacing", False)
        cli_overrides = {
            "use_camera": use_camera,
            "camera_preset": args.camera_preset,
            "spacing": args.spacing,
            "optimize_path": args.optimize_path,
        }
        if args.direction is not None:
            cli_overrides["direction"] = args.direction
        if args.height is not None:
            cli_overrides["height"] = args.height
        if getattr(args, "margin", None) is not None:
            cli_overrides["margin"] = args.margin
        if getattr(args, "overlap_lateral", None) is not None:
            cli_overrides["overlap_lateral"] = args.overlap_lateral
        if getattr(args, "overlap_longitudinal", None) is not None:
            cli_overrides["overlap_longitudinal"] = args.overlap_longitudinal
        params = merge_planning_params(kmz_params=raw_params, cli_params=cli_overrides)
        if not use_camera:
            print("[INFO] 使用固定条带间距 --spacing（--fixed-spacing 模式）")
        result = plan_polygon([list(p[:2]) for p in coords_ll], params)
        if getattr(args, "verbose", False) and result.get("waypoints"):
            polygon_vertex_count = len(coords_ll)
            if polygon_vertex_count >= 2 and coords_ll[0] == coords_ll[-1]:
                polygon_vertex_count -= 1
            _print_spacing_info(params, result, polygon_vertex_count=polygon_vertex_count)
        action_template = args.action_template or "photo_45"

    if result["error"]:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)

    waypoints = [tuple(w[:3]) for w in result["waypoints"]]

    if args.dsm:
        dsm_path = Path(args.dsm)
        meta_path = Path(args.dsm_meta) if args.dsm_meta else None
        dsm, meta = load_dsm(dsm_path, meta_path)
        if dsm is not None and meta is not None:
            ref_lon, ref_lat = waypoints[0][0], waypoints[0][1]
            ll2xy = ll_to_xy_func(ref_lon, ref_lat)
            surf_height = args.surface_relative_height
            if raw_params.get("surface_follow", {}).get("surface_relative_height") is not None:
                surf_height = raw_params["surface_follow"]["surface_relative_height"]
            waypoints = apply_dsm_to_waypoints(waypoints, dsm, meta, ll2xy, surf_height)
        else:
            print("[WARN] DSM 加载失败，使用固定高度")

    surface_params = dict(raw_params.get("surface_follow") or {})
    if args.surface_follow or args.dsm:
        surface_params["surface_follow_enable"] = True
    if args.surface_relative_height is not None:
        surface_params["surface_relative_height"] = args.surface_relative_height
    surface_follow = parse_surface_follow_params(surface_params) if surface_params else None

    mission_params = dict(raw_params.get("mission_config") or {})
    if args.fly_to_mode is not None:
        mission_params["fly_to_wayline_mode"] = args.fly_to_mode
    if args.finish_action is not None:
        mission_params["finish_action"] = args.finish_action
    if args.exit_on_rc_lost is not None:
        mission_params["exit_on_rc_lost"] = args.exit_on_rc_lost
    if args.execute_rc_lost_action is not None:
        mission_params["execute_rc_lost_action"] = args.execute_rc_lost_action
    if args.take_off_security_height is not None:
        mission_params["take_off_security_height"] = args.take_off_security_height
    if args.global_rth_height is not None:
        mission_params["global_rth_height"] = args.global_rth_height
    mission_config = parse_mission_config(mission_params) if mission_params else None

    export_height = (
        params.get("height", raw_params.get("height", 100.0)) if input_type == "polygon" else raw_params.get("height", 100.0)
    )
    export_kmz(
        out_path=args.output,
        template_kml=tpl_kml,
        template_wpml=tpl_wpml,
        waypoints=waypoints,
        height=export_height,
        auto_speed=raw_params.get("auto_speed", 10.0),
        action_library=raw_params.get("action_library"),
        segment_start_indices=result.get("segment_start_indices"),
        action_template_id=action_template,
        mission_config=mission_config,
        surface_follow=surface_follow,
        overlap_lateral=params.get("overlap_lateral") if input_type == "polygon" else None,
        overlap_longitudinal=params.get("overlap_longitudinal") if input_type == "polygon" else None,
        margin=params.get("margin") if input_type == "polygon" else None,
        direction=params.get("direction") if input_type == "polygon" else None,
        height_mode=params.get("height_mode") if input_type == "polygon" else raw_params.get("height_mode"),
        execute_height_mode=(
            (params.get("execute_height_mode") if input_type == "polygon" else None)
            or raw_params.get("execute_height_mode")
        ),
        capture_mode=raw_params.get("capture_mode"),
        gimbal_pitch=raw_params.get("camera_pitch"),
        heading_mode=raw_params.get("heading_mode"),
        heading_angle=raw_params.get("heading_angle"),
        patch_template_kml=patch_template_kml,
    )
    print(f"[OK] 已导出: {args.output}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(description="面状/航点/圆柱航线路径编辑器")
    sub = ap.add_subparsers(dest="cmd", help="子命令")

    # polygon 子命令
    p_poly = sub.add_parser("polygon", help="面状航线（多边形扫线）")
    p_poly.add_argument("input", help="输入：KMZ/KML/GeoJSON/JSON 多边形")
    p_poly.add_argument(
        "--spacing",
        type=float,
        default=15.0,
        help="条带间距（米）；--fixed-spacing 时使用，否则由 GSD+重叠率计算",
    )
    p_poly.add_argument("--height", type=float, default=None, help="飞行高度（米），覆盖输入中的高度")
    p_poly.add_argument(
        "--overlap-lateral",
        type=float,
        default=None,
        help="旁向重叠率 0~1，不指定则用 KMZ 或默认 0.7",
    )
    p_poly.add_argument(
        "--overlap-longitudinal",
        type=float,
        default=None,
        help="航向重叠率 0~1，不指定则用 KMZ 或默认 0.8",
    )
    p_poly.add_argument("--direction", type=float, default=None, help="航线方向（度）")
    p_poly.add_argument("--margin", type=float, default=None, help="边界内缩（米），不指定则用 KMZ 或默认 0")
    p_poly.add_argument("--fixed-spacing", action="store_true", help="使用固定 --spacing，不按 GSD 计算")
    p_poly.add_argument(
        "--camera-preset",
        default="m3e",
        choices=("m3e", "m3t", "m30t", "m300"),
        help="相机预设（m3e=广角），用于 GSD 计算",
    )
    p_poly.add_argument("--optimize-path", action="store_true", help="剔除共线冗余点")
    p_poly.add_argument("--verbose", "-v", action="store_true", help="打印条带间距、GSD 等（便于排查）")
    p_poly.add_argument("--surface-follow", action="store_true", help="启用仿地")
    p_poly.add_argument("--surface-relative-height", type=float, default=100.0, help="仿地相对地表高度 (m)")
    p_poly.add_argument("--dsm", metavar="PATH", help="DSM 路径")
    p_poly.add_argument("--dsm-meta", metavar="PATH", help="DSM meta.json 路径")
    _add_common_args(p_poly)
    p_poly.set_defaults(func=lambda a: _run_polygon_or_waypoint(a, "polygon"))

    # waypoint 子命令
    p_wp = sub.add_parser("waypoint", help="航点航线（点序列）")
    p_wp.add_argument("input", help="输入：KMZ/KML/GeoJSON/JSON（MultiPoint 或点数组）")
    p_wp.add_argument("--edit", metavar="JSON", help="航点逐点编辑：JSON 文件，含 operations 数组")
    p_wp.add_argument("--spacing", type=float, default=15.0, help="（多边形时）条带间距")
    p_wp.add_argument("--height", type=float, default=None)
    p_wp.add_argument("--overlap-lateral", type=float, default=None)
    p_wp.add_argument("--overlap-longitudinal", type=float, default=None)
    p_wp.add_argument("--direction", type=float, default=None)
    p_wp.add_argument("--margin", type=float, default=None)
    p_wp.add_argument("--fixed-spacing", action="store_true")
    p_wp.add_argument(
        "--camera-preset",
        default="m3e",
        choices=("m3e", "m3t", "m30t", "m300"),
    )
    p_wp.add_argument("--optimize-path", action="store_true")
    p_wp.add_argument("--verbose", "-v", action="store_true")
    p_wp.add_argument("--surface-follow", action="store_true")
    p_wp.add_argument("--surface-relative-height", type=float, default=100.0)
    p_wp.add_argument("--dsm", metavar="PATH")
    p_wp.add_argument("--dsm-meta", metavar="PATH")
    _add_common_args(p_wp)
    p_wp.set_defaults(func=lambda a: _run_polygon_or_waypoint(a, "waypoint"))

    # corridor 子命令
    p_cor = sub.add_parser("corridor", help="带状航线（沿中心线扫线）")
    p_cor.add_argument("input", help="输入：中心线 KMZ/KML/GeoJSON/JSON（LineString 或点序列）")
    p_cor.add_argument("--half-width", type=float, default=25.0, help="半宽 (m)，中心线向每侧扩展")
    p_cor.add_argument("--lateral-spacing", type=float, default=15.0, help="旁向间距 (m)")
    p_cor.add_argument("--baseline", type=float, default=None, help="摄影基线 (m)，沿航线插值")
    p_cor.add_argument("--height", type=float, default=100.0, help="飞行高度 (m)")
    p_cor.add_argument("--use-camera", action="store_true", help="按相机预设自动算间距")
    p_cor.add_argument(
        "--camera-preset",
        default="m3e",
        choices=("m3e", "m3t", "m30t", "m300"),
    )
    p_cor.add_argument("--surface-follow", action="store_true")
    p_cor.add_argument("--surface-relative-height", type=float, default=100.0)
    p_cor.add_argument("--dsm", metavar="PATH")
    p_cor.add_argument("--dsm-meta", metavar="PATH")
    _add_common_args(p_cor)
    p_cor.set_defaults(func=_run_corridor)

    # cylinder 子命令
    p_cyl = sub.add_parser("cylinder", help="圆柱几何体航线（默认表面扫掠，兼容螺旋）")
    p_cyl.add_argument("--center", required=True, metavar="LON,LAT", help="圆心经纬度，如 120.15,30.28")
    p_cyl.add_argument("--radius", type=float, required=True, help="飞行半径 (m)")
    p_cyl.add_argument("--height", type=float, default=100.0, help="圆柱高度 (m)")
    p_cyl.add_argument(
        "--pitch",
        type=float,
        default=10.0,
        help="surface_sweep: 竖直层间距 (m)；spiral: 每圈螺距 (m/圈)",
    )
    p_cyl.add_argument(
        "--start-z",
        type=float,
        default=25.0,
        help="起始高度 (m)，默认 25 以满足司空近地 20m 安全阈值",
    )
    p_cyl.add_argument("--points-per-rev", type=int, default=36, help="每圈采样点数")
    p_cyl.add_argument("--flight-height", type=float, default=0.0, help="叠加基准高度 (m)")
    p_cyl.add_argument(
        "--geometry-mode",
        default="surface_sweep",
        choices=("surface_sweep", "spiral"),
        help="几何体路径模式：surface_sweep=分层扫掠（默认），spiral=螺旋兼容模式",
    )
    p_cyl.add_argument(
        "--home",
        metavar="LON,LAT",
        default=None,
        help="可选：起飞参考点，插入为首航点（高度与首条规划航点一致）",
    )
    p_cyl.add_argument(
        "--append-centroid",
        action="store_true",
        help="在航线末尾追加圆心 (--center) 航点（高度与末条规划航点一致）",
    )
    _add_common_args(p_cyl)
    p_cyl.set_defaults(func=_run_cylinder)

    if argv and argv[0] not in ("polygon", "waypoint", "cylinder", "corridor"):
        argv = ["polygon"] + list(argv)
    args = ap.parse_args(argv)
    if args.cmd is None:
        ap.print_help()
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

