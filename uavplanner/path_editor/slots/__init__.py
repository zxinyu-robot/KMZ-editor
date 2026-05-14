# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: Slot 聚合导出（mapping2d / cylinder / errors）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""Slot 层：题型模板下的编号、语义、分类、类型、枚举、默认值、版本。

与 `docs/工程要范_参数驱动与模板填空设计规范.md` §七、`docs/面状航线前端对接接口文档.md` 对齐。
"""

from . import mapping2d, cylinder
from .errors import PathEditorErrorCode

__all__ = ["mapping2d", "cylinder", "PathEditorErrorCode"]
