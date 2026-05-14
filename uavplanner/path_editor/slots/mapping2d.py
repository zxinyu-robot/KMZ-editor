# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 面状题型 slot 定义与白名单（mapping2d）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""面状航线（mapping2d）slot 定义与白名单。

分类与 `docs/面状航线前端对接接口文档.md` 中「硬约束 / 软约束 / 策略开关 / 必需」口径对应：
- HARD / SOFT / STRATEGY / REQUIRED_TEMPLATE
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, FrozenSet, List, Mapping, Tuple

TEMPLATE_KIND = "mapping2d"
SLOT_VERSION = "v1"


class SlotCategory(str, Enum):
    """与工程要范「硬/软/策略」一致；模板分支单独标记。"""

    HARD = "hard"
    SOFT = "soft"
    STRATEGY = "strategy"
    REQUIRED_TEMPLATE = "required_template"


# P01–P27 允许出现在 GeoJSON properties / 协议中的槽位编号
ALLOWED_SLOTS: FrozenSet[str] = frozenset(f"P{i:02d}" for i in range(1, 28))

# 规划最小可运行集（其余有默认值）：仅作文档化提示，不强制 API 报错
RECOMMENDED_FOR_PLANNING: FrozenSet[str] = frozenset({"P19"})

SLOT_CATEGORY: Dict[str, SlotCategory] = {
    "P01": SlotCategory.REQUIRED_TEMPLATE,
    "P02": SlotCategory.HARD,
    "P03": SlotCategory.STRATEGY,
    "P04": SlotCategory.HARD,
    "P05": SlotCategory.HARD,
    "P06": SlotCategory.HARD,
    "P07": SlotCategory.STRATEGY,
    "P08": SlotCategory.HARD,
    "P09": SlotCategory.STRATEGY,
    "P10": SlotCategory.STRATEGY,
    "P11": SlotCategory.HARD,
    "P12": SlotCategory.HARD,
    "P13": SlotCategory.HARD,
    "P14": SlotCategory.STRATEGY,
    "P15": SlotCategory.STRATEGY,
    "P16": SlotCategory.STRATEGY,
    "P17": SlotCategory.STRATEGY,
    "P18": SlotCategory.STRATEGY,
    "P19": SlotCategory.STRATEGY,
    "P20": SlotCategory.SOFT,
    "P21": SlotCategory.REQUIRED_TEMPLATE,
    "P22": SlotCategory.STRATEGY,
    "P23": SlotCategory.REQUIRED_TEMPLATE,
    "P24": SlotCategory.SOFT,
    "P25": SlotCategory.HARD,
    "P26": SlotCategory.STRATEGY,
    "P27": SlotCategory.STRATEGY,
}

_P_SLOT = re.compile(r"^P(\d{2})$")


def validate_p_slot_keys(props: Mapping[str, object]) -> Tuple[bool, List[str]]:
    """若 properties 含 `Pxx` 键，则必须在白名单内。"""
    bad: List[str] = []
    for k in props:
        if _P_SLOT.match(k):
            if k not in ALLOWED_SLOTS:
                bad.append(k)
    return len(bad) == 0, bad
