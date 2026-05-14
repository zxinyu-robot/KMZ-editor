# -*- coding: utf-8 -*-
# 自 drone_3d_path backend/app/views/waylines.py 抽取：KMZ → wayline_info 字典。
from __future__ import annotations

import os
from typing import Any, Dict

from uavplanner.kmz.kmz_parser import KMZParser


def safe_decode_bytes(v: Any) -> Any:
    if isinstance(v, (bytes, bytearray)):
        try:
            return bytes(v).decode("utf-8")
        except Exception:
            return bytes(v).decode("utf-8", errors="replace")
    return v


def build_wayline_info_from_kmz(local_file_path: str) -> Dict[str, Any]:
    """解析 KMZ，返回与 waylines ``wayline_info`` 对齐的结构（kml/wpml 及 JSON 特征）。"""
    kmz_parser = KMZParser(local_file_path)
    is_valid, message, _ = kmz_parser.validate_kmz_file()
    if not is_valid:
        raise ValueError(f"KMZ校验失败: {message}")

    kml_data = kmz_parser.parse_kmz_kml_content()
    payload_info, drone_model_key, template_type_str = kmz_parser._extract_template_info(kml_data)
    _ = drone_model_key, template_type_str
    file_size = os.path.getsize(local_file_path)

    return {
        "payload_info": payload_info,
        "kml": safe_decode_bytes(kml_data.get("template_kml_org", b"")),
        "kml_json": kml_data.get("template_kml_features", []),
        "wpml": safe_decode_bytes(kml_data.get("waylines_wpml_org", b"")),
        "wpml_json": kml_data.get("waylines_wpml_features", []),
        "file_size": file_size,
    }
