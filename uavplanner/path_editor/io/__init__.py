# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 文件 I/O 层 - KML/KMZ/GeoJSON/JSON 读取
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""文件 I/O 层：KML/KMZ/GeoJSON/JSON 读取。"""

from .reader import (
    read_input,
    read_kmz,
    read_kml,
    read_geojson,
    read_json_polygon,
    extract_waypoints_from_wpml,
    parse_polygon_from_kmz,
    parse_waypoints_from_kmz,
)

__all__ = [
    "read_input",
    "read_kmz",
    "read_kml",
    "read_geojson",
    "read_json_polygon",
    "extract_waypoints_from_wpml",
    "parse_polygon_from_kmz",
    "parse_waypoints_from_kmz",
]
