# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: WPML/KMZ 相关枚举类型定义
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""
KMZ枚举类型定义模块
统一管理所有与KMZ文件处理相关的枚举类型
"""

from enum import Enum
from typing import Any, Optional, Union


class ActionActuatorFuncEnums(Enum):
    """
    wpml:actionActuatorFunc	 动作类型
    """

    TAKE_PHOTO = ("takePhoto", "单拍")
    START_RECORD = ("startRecord", "开始录像")
    STOP_RECORD = ("stopRecord", "结束录像")
    FOCUS = ("focus", "对焦")
    ZOOM = ("zoom", "变焦")
    CUSTOM_DIRNAME = ("customDirName", "创建新文件夹")
    GIMBAL_ROTATE = ("gimbalRotate", "旋转云台")
    ROTATE_YAW = ("rotateYaw", "飞行器偏航")
    HOVER = ("hover", "悬停等待")
    GIMBAL_EVENLY_ROTATE = ("gimbalEvenlyRotate", "航段间均匀转动云台pitch角")
    ORIENTED_SHOOT = ("orientedShoot", "精准复拍动作")
    PANO_SHOT = ("panoShot", "全景拍照动作")
    RECORD_POINT_CLOUD = ("recordPointCloud", "点云录制操作")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ActionGroupModeEnums(Enum):
    """
    wpml:actionGroupMode	 动作执行模式
    """

    MANUAL = ("manual", "手动控制")
    SEQUENCE = ("sequence", "串行执行。即动作组内的动作依次按顺序执行")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ActionTriggerTypeEnums(Enum):
    """
    wpml:actionTriggerType	 动作触发器类型
    """

    REACH_POINT = ("reachPoint", "到达航点时执行")
    BETWEEN_ADJACENT_POINTS = ("betweenAdjacentPoints", "航段触发，均匀转云台")
    MULTIPLE_TIMING = ("multipleTiming", "等时触发")
    MULTIPLE_DISTANCE = ("multipleDistance", "等距触发")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class AircraftPathModeEnums(Enum):
    """
    wpml:aircraftPathMode	 飞行器偏航角转动模式
    """

    CLOCKWISE = ("clockwise", "顺时针旋转")
    COUNTER_CLOCKWISE = ("counterClockwise", "逆时针旋转")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class CollectionMethodEnums(Enum):
    """
    wpml:overlap	 采集类型
    """

    ORTHO = ("ortho", "正射采集")
    INCLINED = ("inclined", "倾斜采集")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class DroneEnumValueEnums(Enum):
    """
    wpml:droneEnumValue	 飞行器机型主类型
    """

    M350_RTK = (89, "M350 RTK")
    M300_RTK = (60, "M300 RTK")
    M30_M30T = (67, "M30/M30T")
    M3E_M3T_M3M = (77, "M3E/M3T/M3M")
    M3D_M3TD = (91, "M3D/M3TD")

    def __init__(self, value: int, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> int:
        return self.value

    def get_description(self) -> str:
        return self.description


class ExecuteHeightModeEnums(Enum):
    """
    wpml:executeHeightMode 执行高度模式
    """

    WGS84 = ("WGS84", "椭球高模式")
    RELATIVE_TO_START_POINT = ("relativeToStartPoint", "相对起飞点高度模式")
    REALTIME_FOLLOW_SURFACE = (
        "realTimeFollowSurface",
        "使用实时仿地模式，仅支持M3E/M3T/M3M",
    )

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ExecuteRCLostActionEnums(Enum):
    """
    wpml:executeRCLostAction 失控动作类型
    当 wpml:exitOnRCLost为 executeLostAction 时为必需元素
    """

    GO_BACK = ("goBack", "返航")
    LANDING = ("landing", "降落")
    HOVER = ("hover", "悬停")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ExitOnRCLostEnums(Enum):
    """
    wpml:exitOnRCLost 失控是否继续执行航线
    """

    GO_CONTINUE = ("goContinue", "继续执行航线")
    EXECUTE_LOST_ACTION = ("executeLostAction", "退出航线，执行失控动作")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class FinishActionEnums(Enum):
    """
    wpml:finishAction 航线结束动作
    注：动作执行过程，若飞行器退出了航线模式且进入失控状态，则会优先执行失控动作。
    """

    GO_HOME = ("goHome", "飞行器完成航线任务后，退出航线模式并返航")
    NO_ACTION = ("noAction", "飞行器完成航线任务后，退出航线模式")
    AUTO_LAND = ("autoLand", "飞行器完成航线任务后，退出航线模式并原地降落")
    GOTO_FIRST_WAYPOINT = (
        "gotoFirstWaypoint",
        "飞行器完成航线任务后，立即飞向航线起始点，到达后退出航线模式",
    )

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class FlyToWaylineModeEnums(Enum):
    """
    wpml:flyToWaylineMode 飞向首航点模式
    """

    SAFELY = ("safely", "安全模式")
    POINT_TO_POINT = ("pointToPoint", "倾斜飞行模式")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class FocusModeEnums(Enum):
    """
    wpml:focusMode 负载对焦模式
    """

    FIRST_POINT = ("firstPoint", "首个航点自动对焦")
    CUSTOM = ("custom", "标定对焦值对焦")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class GimbalPitchModeEnums(Enum):
    """
    wpml:gimbalPitchMode 云台俯仰角控制模式
    """

    MANUAL = ("manual", "手动控制")
    USE_POINT_SETTING = ("usePointSetting", "依照每个航点设置")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class GlobalWaypointTurnModeEnums(Enum):
    """
    wpml:globalWaypointTurnMode 全局航点类型（全局航点转弯模式）
    """

    COORDINATE_TURN = ("coordinateTurn", "协调转弯，不过点，提前转弯")
    TO_POINT_AND_STOP_WITH_DISCONTINUITY_CURVATURE = (
        "toPointAndStopWithDiscontinuityCurvature",
        "直线飞行，飞行器到点停",
    )
    TO_POINT_AND_STOP_WITH_CONTINUITY_CURVATURE = (
        "toPointAndStopWithContinuityCurvature",
        "曲线飞行，飞行器到点停",
    )
    TO_POINT_AND_PASS_WITH_CONTINUITY_CURVATURE = (
        "toPointAndPassWithContinuityCurvature",
        "曲线飞行，飞行器过点不停",
    )

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class HeightModeEnums(Enum):
    """
    wpml:heightMode 航点高程参考平面
    """

    EGM96 = ("EGM96", "使用海拔高编辑")
    RELATIVE_TO_START_POINT = ("relativeToStartPoint", "使用相对点的高度进行编辑")
    ABOVE_GROUND_LEVEL = (
        "aboveGroundLevel",
        "使用地形数据，AGL下编辑(仅支持司空2平台)",
    )
    REALTIME_FOLLOW_SURFACE = (
        "realTimeFollowSurface",
        "使用实时仿地模式（仅用于建图航拍模版），仅支持M3E/M3T/M3M机型",
    )

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ImageFormatEnums(Enum):
    """
    wpml:imageFormat 图片格式列表
    """

    WIDE = ("wide", "存储广角镜头照片")
    ZOOM = ("zoom", "存储变焦镜头照片")
    IR = ("ir", "存储红外镜头照片")
    NARROW_BAND = ("narrow_band", "存储窄带镜头拍摄照片")
    VISABLE = ("visable", "可见光照片")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class LensTypeEnums(Enum):
    """
    wpml:overlap	 采集类型
    """

    LIDAR = ("lidar", "激光")
    CAMERA = ("camera", "可见光")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class MeteringModeEnums(Enum):
    """
    wpml:meteringMode 负载测光模式
    """

    AVERAGE = ("average", "全局测光")
    SPOT = ("spot", "点测光")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class PayloadPositionIndexEnums(Enum):
    """
    wpml:payloadPositionIndex 负载挂载位置
    """

    ZERO = (
        0,
        "飞行器1号挂载位置。M300 RTK,M350 RTK机型,对应机身左前方。其它机型,对应主云台",
    )
    ONE = (1, "飞行器2号挂载位置。M300 RTK,M350 RTK机型,对应机身右前方")
    TWO = (2, "飞行器3号挂载位置。M300 RTK,M350 RTK机型,对应机身上方")

    def __init__(self, value: int, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> int:
        return self.value

    def get_description(self) -> str:
        return self.description


class PayloadTypeEnums(Enum):
    """
    wpml:payloadEnumValue 负载机型主类型
    """

    H20 = (42, "H20")
    H20T = (43, "H20T")
    M30 = (52, "M30双光相机")
    M30T = (53, "M30T三光相机")
    H20N = (61, "H20N")
    MAVIC_3E = (66, "Mavic 3E 相机")
    MAVIC_3T = (67, "Mavic 3T 相机")
    MAVIC_3M = (68, "Mavic 3M 相机")
    MATRICE_3D = (80, "Matrice 3D 相机")
    MATRICE_3TD = (81, "Matrice 3TD 相机")
    PSDK = (65534, "PSDK 负载")
    H30 = (82, "H30")
    H30T = (83, "H30T")

    def __init__(self, value: int, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> int:
        return self.value

    def get_description(self) -> str:
        return self.description


class PositioningTypeEnums(Enum):
    """
    wpml:positioningType 经纬度与高度数据源
    """

    GPS = ("GPS", "位置数据采集来源为GPS/BDS/GLONASS/GALILEO等")
    RTK_BASE_STATION = ("RTKBaseStation", "采集位置数据时，使用RTK基站进行差分定位")
    QIAN_XUN = ("QianXun", "采集位置数据时，使用千寻网络RTK进行差分定位")
    CUSTOM = ("Custom", "采集位置数据时，使用自定义网络RTK进行差分定位")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ReturnModeEnums(Enum):
    """
    wpml:returnMode 激光雷达回波模式
    """

    SINGLE_RETURN_STRONGEST = ("singleReturnStrongest", "单回波")
    DUAL_RETURN = ("dualReturn", "双回波")
    TRIPLE_RETURN = ("tripleReturn", "三回波")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ScanningModeEnums(Enum):
    """
    wpml:scanningMode 负载扫描模式
    """

    REPETITIVE = ("repetitive", "重复扫描")
    NON_REPETITIVE = ("nonRepetitive", "非重复扫描")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class ShootTypeEnums(Enum):
    """
    wpml:shootType 拍照模式（定时或定距）
    """

    TIME = ("time", "等时间拍照")
    DISTANCE = ("distance", "等间隔拍照")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class TemplateTypeEnums(Enum):
    """
    wpml:templateType 预定义模板类型
    """

    WAYPOINT = ("waypoint", "航点飞行")
    MAPPING2D = ("mapping2d", "建图航拍")
    MAPPING3D = ("mapping3d", "倾斜摄影")
    MAPPING_STRIP = ("mappingStrip", "航带飞行")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class WaypointHeadingModeEnums(Enum):
    """
    wpml:waypointHeadingMode 飞行器偏航角模式
    """

    FOLLOW_WAYLINE = ("followWayline", "沿航线方向。飞行器机头沿着航线方向飞至下一航点")
    MANUALLY = (
        "manually",
        "手动控制。飞行器在飞至下一航点的过程中，用户可以手动控制飞行器机头朝向",
    )
    FIXED = (
        "fixed",
        "锁定当前偏航角。飞行器机头保持执行完航点动作后的飞行器偏航角飞至下一航点",
    )
    SMOOTH_TRANSITION = (
        "smoothTransition",
        '自定义。通过"wpml:waypointHeadingAngle"给定某航点的目标偏航角，并在航段飞行过程中均匀过渡至下一航点的目标偏航角。',
    )
    TOWARD_POI = ("towardPOI", "朝向兴趣点")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


class WaypointHeadingPathModeEnums(Enum):
    """
    wpml:waypointHeadingPathMode 飞行器偏航角转动方向
    """

    CLOCKWISE = ("clockwise", "顺时针旋转飞行器偏航角")
    COUNTER_CLOCKWISE = ("counterClockwise", "逆时针旋转飞行器偏航角")
    FOLLOW_BAD_ARC = ("followBadArc", "沿最短路径旋转飞行器偏航角")

    def __init__(self, value: str, description: str):
        self.value = value
        self.description = description

    def get_value(self) -> str:
        return self.value

    def get_description(self) -> str:
        return self.description


# 通用工具函数
def validate_enum_value(enum_class: Enum, value: Any) -> bool:
    """
    验证枚举值是否有效

    Args:
        enum_class: 枚举类
        value: 要验证的值

    Returns:
        bool: 值是否有效
    """
    try:
        if isinstance(value, enum_class):
            return True
        enum_class(value)
        return True
    except (ValueError, KeyError):
        return False


def get_enum_values(enum_class: Enum) -> list:
    """
    获取枚举类的所有值

    Args:
        enum_class: 枚举类

    Returns:
        list: 包含所有枚举值的列表
    """
    return [item.value for item in enum_class]


def get_enum_by_value(enum_class: Enum, value: Union[str, int]) -> Optional[Enum]:
    """
    根据值获取枚举项

    Args:
        enum_class: 枚举类
        value: 枚举值

    Returns:
        Optional[Enum]: 对应的枚举项，如果未找到则返回None
    """
    for item in enum_class:
        if item.value[0] == value or item.value == value:
            return item
    return None


# 为每个枚举类添加便捷方法
enum_classes = [
    ActionActuatorFuncEnums,
    ActionGroupModeEnums,
    ActionTriggerTypeEnums,
    AircraftPathModeEnums,
    CollectionMethodEnums,
    DroneEnumValueEnums,
    ExecuteHeightModeEnums,
    ExecuteRCLostActionEnums,
    ExitOnRCLostEnums,
    FinishActionEnums,
    FlyToWaylineModeEnums,
    FocusModeEnums,
    GimbalPitchModeEnums,
    GlobalWaypointTurnModeEnums,
    HeightModeEnums,
    ImageFormatEnums,
    LensTypeEnums,
    MeteringModeEnums,
    PayloadPositionIndexEnums,
    PayloadTypeEnums,
    PositioningTypeEnums,
    ReturnModeEnums,
    ScanningModeEnums,
    ShootTypeEnums,
    TemplateTypeEnums,
    WaypointHeadingModeEnums,
    WaypointHeadingPathModeEnums,
]

for enum_class in enum_classes:
    # 添加 has_value 类方法
    setattr(
        enum_class,
        "has_value",
        classmethod(lambda cls, value: validate_enum_value(cls, value)),
    )

    # 添加 from_value 类方法
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        for item in cls:
            if item.value == value or (
                isinstance(item.value, tuple) and item.value[0] == value
            ):
                return item
        return None

    setattr(enum_class, "from_value", classmethod(from_value))

    # 添加 get_all_values 类方法
    setattr(
        enum_class,
        "get_all_values",
        classmethod(lambda cls: [item.value for item in cls]),
    )
