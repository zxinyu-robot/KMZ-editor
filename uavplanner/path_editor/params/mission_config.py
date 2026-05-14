# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 任务配置 - F-006 ~ F-014 飞向模式、完成动作、失控动作等
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-09
# ------------------------------------------------------------ #

"""任务配置：missionConfig 对应 WPML 字段，对应需求 F-006 ~ F-014。"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# F-006 飞向首航点模式
FLY_TO_MODES = ("safely", "pointToPoint")
# F-007 完成动作
FINISH_ACTIONS = ("goHome", "autoLand", "hover", "noAction", "gotoFirstWaypoint")
# F-008 失控动作（exitOnRCLost=executeLostAction 时生效）
EXECUTE_RC_LOST_ACTIONS = ("goBack", "hover", "landing")
# F-009 航线失联行为
EXIT_ON_RC_LOST = ("goContinue", "executeLostAction")


@dataclass
class MissionConfig:
    """任务配置：对应 wpml:missionConfig 子元素，兼容司空解析。"""

    fly_to_wayline_mode: str = "safely"  # F-006: safely | pointToPoint
    finish_action: str = "goHome"  # F-007: goHome | autoLand | hover | noAction | gotoFirstWaypoint
    exit_on_rc_lost: str = "goContinue"  # F-009: goContinue | executeLostAction
    execute_rc_lost_action: str = "goBack"  # F-008: goBack | hover | landing（失联时执行）
    take_off_security_height: float = 120.0  # F-013: 安全起飞高度 (m)
    global_transitional_speed: float = 15.0  # 过渡速度 (m/s)
    global_rth_height: float = 100.0  # 返航高度 (m)
    # 司空解析必需字段
    take_off_ref_point: Optional[str] = None  # "lat,lon,height" 格式
    take_off_ref_point_agl_height: float = 0.0
    drone_enum_value: int = 99
    drone_sub_enum_value: int = 1
    payload_enum_value: int = 89
    payload_sub_enum_value: int = 0
    payload_position_index: int = 0
    wayline_avoid_limit_area_mode: int = 0
    auto_reroute_info: Optional[str] = None

    def to_wpml_dict(
        self,
        *,
        include_take_off_ref_fields: bool = True,
        include_auto_reroute_info: bool = False,
    ) -> Dict[str, Any]:
        """转为 WPML 写入用的字典，键为 wpml 标签名。支持标量与嵌套结构。"""
        d: Dict[str, Any] = {
            "flyToWaylineMode": self.fly_to_wayline_mode,
            "finishAction": self.finish_action,
            "exitOnRCLost": self.exit_on_rc_lost,
            "executeRCLostAction": self.execute_rc_lost_action,
            "takeOffSecurityHeight": f"{self.take_off_security_height:.0f}",
            "globalTransitionalSpeed": f"{self.global_transitional_speed:.1f}",
            "globalRTHHeight": f"{self.global_rth_height:.1f}",
            "waylineAvoidLimitAreaMode": str(self.wayline_avoid_limit_area_mode),
            "droneInfo": {
                "droneEnumValue": str(self.drone_enum_value),
                "droneSubEnumValue": str(self.drone_sub_enum_value),
            },
            "payloadInfo": {
                "payloadEnumValue": str(self.payload_enum_value),
                "payloadSubEnumValue": str(self.payload_sub_enum_value),
                "payloadPositionIndex": str(self.payload_position_index),
            },
        }
        if include_take_off_ref_fields:
            d["takeOffRefPointAGLHeight"] = f"{self.take_off_ref_point_agl_height:.0f}"
            if self.take_off_ref_point is not None:
                d["takeOffRefPoint"] = self.take_off_ref_point
        if include_auto_reroute_info and self.auto_reroute_info is not None:
            d["autoRerouteInfo"] = self.auto_reroute_info
        return d

    def with_take_off_ref_point(self, lat: float, lon: float, height: float) -> "MissionConfig":
        """返回带起飞点的新配置（不修改原对象）。"""
        from copy import copy

        c = copy(self)
        c.take_off_ref_point = f"{lat:.6f},{lon:.6f},{height:.3f}"
        return c

    def to_dict(self) -> Dict[str, Any]:
        """转为 API/CLI 参数字典。"""
        return {
            "fly_to_wayline_mode": self.fly_to_wayline_mode,
            "finish_action": self.finish_action,
            "exit_on_rc_lost": self.exit_on_rc_lost,
            "execute_rc_lost_action": self.execute_rc_lost_action,
            "take_off_security_height": self.take_off_security_height,
            "global_transitional_speed": self.global_transitional_speed,
            "global_rth_height": self.global_rth_height,
            "wayline_avoid_limit_area_mode": self.wayline_avoid_limit_area_mode,
        }


def parse_mission_config(params: Optional[Dict[str, Any]] = None) -> MissionConfig:
    """从字典解析任务配置，未提供则用默认值。"""
    cfg = MissionConfig()
    if not params:
        return cfg
    mapping = {
        "fly_to_wayline_mode": "fly_to_wayline_mode",
        "flyToWaylineMode": "fly_to_wayline_mode",
        "finish_action": "finish_action",
        "finishAction": "finish_action",
        "exit_on_rc_lost": "exit_on_rc_lost",
        "exitOnRCLost": "exit_on_rc_lost",
        "execute_rc_lost_action": "execute_rc_lost_action",
        "executeRCLostAction": "execute_rc_lost_action",
        "take_off_security_height": "take_off_security_height",
        "takeOffSecurityHeight": "take_off_security_height",
        "global_transitional_speed": "global_transitional_speed",
        "globalTransitionalSpeed": "global_transitional_speed",
        "global_rth_height": "global_rth_height",
        "globalRTHHeight": "global_rth_height",
        "take_off_ref_point": "take_off_ref_point",
        "takeOffRefPoint": "take_off_ref_point",
        "take_off_ref_point_agl_height": "take_off_ref_point_agl_height",
        "takeOffRefPointAGLHeight": "take_off_ref_point_agl_height",
        "drone_enum_value": "drone_enum_value",
        "drone_sub_enum_value": "drone_sub_enum_value",
        "payload_enum_value": "payload_enum_value",
        "payload_sub_enum_value": "payload_sub_enum_value",
        "payload_position_index": "payload_position_index",
        "wayline_avoid_limit_area_mode": "wayline_avoid_limit_area_mode",
        "waylineAvoidLimitAreaMode": "wayline_avoid_limit_area_mode",
        "auto_reroute_info": "auto_reroute_info",
        "autoRerouteInfo": "auto_reroute_info",
    }
    for k, attr in mapping.items():
        v = params.get(k)
        if v is None:
            continue
        if attr in ("take_off_security_height", "global_transitional_speed", "global_rth_height", "take_off_ref_point_agl_height"):
            try:
                setattr(cfg, attr, float(v))
            except (TypeError, ValueError):
                pass
        elif attr in (
            "drone_enum_value",
            "drone_sub_enum_value",
            "payload_enum_value",
            "payload_sub_enum_value",
            "payload_position_index",
            "wayline_avoid_limit_area_mode",
        ):
            try:
                setattr(cfg, attr, int(v))
            except (TypeError, ValueError):
                pass
        else:
            if isinstance(v, str):
                setattr(cfg, attr, v.strip())
    return cfg
