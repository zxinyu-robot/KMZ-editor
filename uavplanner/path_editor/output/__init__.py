# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 输出层 - 航点序列格式化、KMZ 导出
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""输出层：航点序列格式化、KMZ 导出。"""

from .kmz import export_kmz, build_minimal_template_kml, build_minimal_waypoint_template, resolve_height_export_modes
from .action_library import (
    ActionTemplate,
    parse_action_library_from_wpml,
    parse_action_library_from_document,
    get_default_photo_template,
)
from .formatter import (
    to_waypoints,
    to_waypoints_3d,
    add_waypoint_timestamps,
    waypoints_with_time_to_list,
)

__all__ = [
    "export_kmz",
    "build_minimal_template_kml",
    "build_minimal_waypoint_template",
    "resolve_height_export_modes",
    "ActionTemplate",
    "parse_action_library_from_wpml",
    "parse_action_library_from_document",
    "get_default_photo_template",
    "to_waypoints",
    "to_waypoints_3d",
    "add_waypoint_timestamps",
    "waypoints_with_time_to_list",
]
