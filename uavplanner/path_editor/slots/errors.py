# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: path_editor Slot 层错误码定义
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""可解释错误码：API / CLI 可原样返回给调用方（前缀避免与其它子系统冲突）。"""

from enum import Enum


class PathEditorErrorCode(str, Enum):
    """path_editor 关键错误码（字符串值稳定，可写入日志与 JSON）。"""

    # 输入 / slot
    M2D_UNKNOWN_SLOT = "PE_M2D_UNKNOWN_SLOT"
    M2D_VALIDATION_FAILED = "PE_M2D_VALIDATION_FAILED"
    CYL_VALIDATION_FAILED = "PE_CYL_VALIDATION_FAILED"
    # 几何
    GEOM_INVALID_POLYGON = "PE_GEOM_INVALID_POLYGON"
    GEOM_TOO_FEW_VERTICES = "PE_GEOM_TOO_FEW_VERTICES"
    # 规划 / I/O
    PLAN_FAILED = "PE_PLAN_FAILED"
    IO_READ_FAILED = "PE_IO_READ_FAILED"
    EXPORT_FAILED = "PE_EXPORT_FAILED"
