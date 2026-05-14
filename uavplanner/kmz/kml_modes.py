# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: KML 数据模型与文档结构（KMZ 解析配套）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""
KML数据模型包
统一管理所有与KML文件处理相关的数据模型类
"""

import json
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, List, Optional, Union


def _clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """清理字典，移除值为None的键"""
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class KmlDocument:
    """
    对应template.Document中的KmlDocument 文档类
    """
    author: Optional[str] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None
    kmlMissionConfig: Optional['KmlMissionConfig'] = None
    folder: Optional['KmlFolder'] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "missionConfig" and v is not None:
                    result[k] = v.to_dict()
                elif k == "Folder" and v is not None:
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KmlDocument':
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        if "missionConfig" in filtered_data and filtered_data["missionConfig"]:
            filtered_data["missionConfig"] = KmlMissionConfig.from_dict(
                filtered_data["missionConfig"]
            )
        if "Folder" in filtered_data and filtered_data["Folder"]:
            filtered_data["Folder"] = KmlFolder.from_dict(filtered_data["Folder"])

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'KmlDocument':
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)

@dataclass
class KmlActionActuatorFuncParam:
    """
    对应wpml:actionActuatorFuncParam中的KmlActionActuatorFuncParam 动作执行器功能参数类
    """

    # TAKE_PHOTO相关参数
    payloadPositionIndex: Optional[str] = None
    fileSuffix: Optional[str] = None
    useGlobalPayloadLensIndex: Optional[str] = None
    payloadLensIndex: Optional[str] = None

    # GIMBAL_ROTATE相关参数
    gimbalHeadingYawBase: Optional[str] = None
    gimbalRotateMode: Optional[str] = None
    gimbalPitchRotateEnable: Optional[str] = None
    gimbalPitchRotateAngle: Optional[str] = None
    gimbalRollRotateEnable: Optional[str] = None
    gimbalRollRotateAngle: Optional[str] = None
    gimbalYawRotateEnable: Optional[str] = None
    gimbalYawRotateAngle: Optional[str] = None
    gimbalRotateTimeEnable: Optional[str] = None
    gimbalRotateTime: Optional[str] = None

    # ROTATE_YAW相关参数
    aircraftHeading: Optional[str] = None
    aircraftPathMode: Optional[str] = None

    # HOVER相关参数
    hoverTime: Optional[str] = None

    # ZOOM相关参数
    focalLength: Optional[str] = None

    # focus
    isPointFocus: Optional[str] = None
    focusX: Optional[str] = None
    focusY: Optional[str] = None
    focusRegionWidth: Optional[str] = None
    focusRegionHeight: Optional[str] = None
    isInfiniteFocus: Optional[str] = None

    # customDirName
    directoryName: Optional[str] = None

    # orientedShoot
    accurateFrameValid: Optional[str] = None
    targetAngle: Optional[str] = None
    actionUUID: Optional[str] = None
    imageWidth: Optional[str] = None
    imageHeight: Optional[str] = None
    AFPos: Optional[str] = None
    gimbalPort: Optional[str] = None
    orientedCameraType: Optional[str] = None
    orientedFilePath: Optional[str] = None
    orientedFileMD5: Optional[str] = None
    orientedFileSize: Optional[str] = None
    orientedFileSuffix: Optional[str] = None
    orientedCameraApertue: Optional[str] = None
    orientedCameraLuminance: Optional[str] = None
    orientedCameraShutterTime: Optional[str] = None
    orientedCameraISO: Optional[str] = None
    orientedPhotoMode: Optional[str] = None

    # panoShot
    panoShotSubMode: Optional[str] = None

    # recordPointCloud
    recordPointCloudOperate: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlActionActuatorFuncParam":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlActionActuatorFuncParam":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlActionTrigger:
    """
    对应wpml:actionTrigger中的KmlActionTrigger 动作触发器类
    """

    actionTriggerType: Optional[str] = None
    actionTriggerParam: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlActionTrigger":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlActionTrigger":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlAction:
    """
    对应wpml:action中的KmlAction类，用于表示KML动作
    """

    actionId: Optional[str] = None
    actionActuatorFunc: Optional[str] = None
    actionActuatorFuncParam: Optional["KmlActionActuatorFuncParam"] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "actionActuatorFuncParam" and v is not None:
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlAction":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        if (
            "actionActuatorFuncParam" in filtered_data
            and filtered_data["actionActuatorFuncParam"]
        ):
            filtered_data["actionActuatorFuncParam"] = (
                KmlActionActuatorFuncParam.from_dict(
                    filtered_data["actionActuatorFuncParam"]
                )
            )

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlAction":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlActionGroup:
    """
    对应wpml:actionGroup中的KmlActionGroup 动作组类
    """

    actionGroupId: Optional[str] = None
    actionGroupStartIndex: Optional[str] = None
    actionGroupEndIndex: Optional[str] = None
    actionGroupMode: Optional[str] = None
    actionTrigger: Optional["KmlActionTrigger"] = None
    action: List["KmlAction"] = None

    def __post_init__(self):
        if self.action is None:
            self.action = []

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "actionTrigger" and v is not None:
                    result[k] = v.to_dict()
                elif k == "action" and v is not None:
                    result[k] = [item.to_dict() for item in v]
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlActionGroup":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        if "actionTrigger" in filtered_data and filtered_data["actionTrigger"]:
            filtered_data["actionTrigger"] = KmlActionTrigger.from_dict(
                filtered_data["actionTrigger"]
            )

        if "action" in filtered_data and filtered_data["action"]:
            filtered_data["action"] = [
                KmlAction.from_dict(item) for item in filtered_data["action"]
            ]

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlActionGroup":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlPoint:
    """
    对应kml Point中的KmlPoint类
    """

    coordinates: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlPoint":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlPoint":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlWaypointTurnParam:
    """
    对应wpml:waypointTurnParam中的KmlWaypointTurnParam  航点转弯参数类
    """

    waypointTurnMode: Optional[str] = None
    waypointTurnDampingDist: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlWaypointTurnParam":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlWaypointTurnParam":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlWaypointHeadingParam:
    """
    对应wpml:globalWaypointHeadingParam中的KmlWaypointHeadingParam 航点航向参数类
    """

    waypointHeadingMode: Optional[str] = None
    waypointHeadingAngle: Optional[str] = None
    waypointPoiPoint: Optional[str] = None
    waypointHeadingPathMode: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlWaypointHeadingParam":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlWaypointHeadingParam":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlOverlap:
    """
    KML重叠类
    """

    orthoLidarOverlapH: Optional[str] = None
    orthoLidarOverlapW: Optional[str] = None
    orthoCameraOverlapH: Optional[str] = None
    orthoCameraOverlapW: Optional[str] = None
    inclinedLidarOverlapH: Optional[str] = None
    inclinedLidarOverlapW: Optional[str] = None
    inclinedCameraOverlapH: Optional[str] = None
    inclinedCameraOverlapW: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlOverlap":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlOverlap":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlLineString:
    """
    KML线串类
    """

    coordinates: Optional[Union[str, List[str]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlLineString":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlLineString":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlLinearRing:
    """
    KML线性环类
    """

    coordinates: Optional[Union[str, List[str]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlLinearRing":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlLinearRing":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlOuterBoundaryIs:
    """
    KML外边界类
    """

    linearRing: Optional["KmlLinearRing"] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "linearRing" and v is not None:
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlOuterBoundaryIs":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        if "linearRing" in filtered_data and filtered_data["linearRing"]:
            filtered_data["linearRing"] = KmlLinearRing.from_dict(
                filtered_data["linearRing"]
            )

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlOuterBoundaryIs":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlPolygon:
    """
    KML多边形类
    表示一个多边形区域
    """

    outerBoundaryIs: Optional["KmlOuterBoundaryIs"] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "outerBoundaryIs" and v is not None:
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlPolygon":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        if "outerBoundaryIs" in filtered_data and filtered_data["outerBoundaryIs"]:
            filtered_data["outerBoundaryIs"] = KmlOuterBoundaryIs.from_dict(
                filtered_data["outerBoundaryIs"]
            )

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlPolygon":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlPlacemark:
    """
    对应kml Placemark中的KmlPlacemark地标类
    """

    isRisky: Optional[str] = None
    kmlPoint: Optional["KmlPoint"] = None
    index: Optional[str] = None
    useGlobalHeight: Optional[str] = None
    ellipsoidHeight: Optional[str] = None
    height: Optional[str] = None
    useGlobalSpeed: Optional[str] = None
    waypointSpeed: Optional[str] = None
    useGlobalHeadingParam: Optional[str] = None
    waypointHeadingParam: Optional["KmlWaypointHeadingParam"] = None
    useGlobalTurnParam: Optional[str] = None
    waypointTurnParam: Optional["KmlWaypointTurnParam"] = None
    useStraightLine: Optional[str] = None
    gimbalPitchAngle: Optional[str] = None
    actionGroup: Optional["KmlActionGroup"] = None

    # 下面 wpml 文件使用
    executeHeight: Optional[str] = None

    # 建图航拍模板元素
    caliFlightEnable: Optional[str] = None
    elevationOptimizeEnable: Optional[str] = None
    smartObliqueEnable: Optional[str] = None
    smartObliqueGimbalPitch: Optional[str] = None
    shootTopFaceEnable: Optional[str] = None
    shootType: Optional[str] = None
    trajectoryType: Optional[str] = None
    startPositionType: Optional[str] = None
    direction: Optional[str] = None
    margin: Optional[str] = None
    overlap: Optional["KmlOverlap"] = None
    facadeWaylineEnable: Optional[str] = None
    polygon: Optional["KmlPolygon"] = None
    mappingHeadingParam: Optional["KmlActionGroup"] = None
    gimbalPitchMode: Optional[str] = None

    # 倾斜摄影模板元素
    inclinedGimbalPitch: Optional[str] = None
    inclinedFlightSpeed: Optional[str] = None

    # 航带飞行模板元素
    singleLineEnable: Optional[str] = None
    cuttingDistance: Optional[str] = None
    boundaryOptimEnable: Optional[str] = None
    leftExtend: Optional[str] = None
    rightExtend: Optional[str] = None
    includeCenterEnable: Optional[str] = None
    stripUseTemplateAltitude: Optional[str] = None
    lineString: Optional["KmlLineString"] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "kmlPoint" and v is not None:
                    result[k] = v.to_dict()
                elif k == "waypointHeadingParam" and v is not None:
                    result[k] = v.to_dict()
                elif k == "waypointTurnParam" and v is not None:
                    result[k] = v.to_dict()
                elif k == "actionGroup" and v is not None:
                    result[k] = v.to_dict()
                elif k == "overlap" and v is not None:
                    result[k] = v.to_dict()
                elif k == "polygon" and v is not None:
                    result[k] = v.to_dict()
                elif k == "mappingHeadingParam" and v is not None:
                    result[k] = v.to_dict()
                elif k == "lineString" and v is not None:
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlPlacemark":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        nested_mappings = {
            "kmlPoint": KmlPoint,
            "waypointHeadingParam": KmlWaypointHeadingParam,
            "waypointTurnParam": KmlWaypointTurnParam,
            "actionGroup": KmlActionGroup,
            "overlap": KmlOverlap,
            "polygon": KmlPolygon,
            "mappingHeadingParam": KmlActionGroup,
            "lineString": KmlLineString,
        }

        for key, cls_type in nested_mappings.items():
            if key in filtered_data and filtered_data[key]:
                filtered_data[key] = cls_type.from_dict(filtered_data[key])

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlPlacemark":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlGlobalWaypointHeadingParam:
    """
    对应wpml:globalWaypointHeadingParam中的KmlGlobalWaypointHeadingParam 全局航点航向参数类
    """

    waypointHeadingMode: Optional[str] = None
    waypointHeadingAngle: Optional[str] = None
    waypointPoiPoint: Optional[str] = None
    waypointHeadingPathMode: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlGlobalWaypointHeadingParam":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlGlobalWaypointHeadingParam":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlWayLineCoordinateSysParam:
    """
    对应wpml:waylineCoordinateSysParam中的KmlWayLineCoordinateSysParam 航线坐标系参数类
    """

    coordinateMode: Optional[str] = None
    heightMode: Optional[str] = None
    positioningType: Optional[str] = None
    globalShootHeight: Optional[str] = None
    surfaceFollowModeEnable: Optional[str] = None
    isRealtimeSurfaceFollow: Optional[str] = None
    surfaceRelativeHeight: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlWayLineCoordinateSysParam":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlWayLineCoordinateSysParam":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlPayloadParam:
    """
    对应wpml:payloadParam中的KmlPayloadParam 负载参数类
    负载设置
    """

    payloadPositionIndex: Optional[str] = None
    focusMode: Optional[str] = None
    meteringMode: Optional[str] = None
    dewarpingEnable: Optional[str] = None
    returnMode: Optional[str] = None
    samplingRate: Optional[str] = None
    scanningMode: Optional[str] = None
    modelColoringEnable: Optional[str] = None
    imageFormat: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlPayloadParam":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlPayloadParam":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlPayloadInfo:
    """
    对应wpml:payloadInfo中的KmlPayloadInfo类
    """

    payloadEnumValue: Optional[str] = None
    payloadPositionIndex: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlPayloadInfo":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlPayloadInfo":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlDroneInfo:
    """
    对应wpml:droneInfo中的KmlDroneInfo 无人机信息类
    """

    droneEnumValue: Optional[str] = None
    droneSubEnumValue: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlDroneInfo":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlDroneInfo":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlMissionConfig:
    """
    对应wpml:missionConfig中的KmlMissionConfig 任务配置类
    """

    flyToWayLineMode: Optional[str] = None
    finishAction: Optional[str] = None
    exitOnRCLost: Optional[str] = None
    executeRCLostAction: Optional[str] = None
    takeOffSecurityHeight: Optional[str] = None
    globalTransitionalSpeed: Optional[str] = None
    globalRTHHeight: Optional[str] = None
    droneInfo: Optional["KmlDroneInfo"] = None
    payloadInfo: Optional["KmlPayloadInfo"] = None
    takeOffRefPoint: Optional[str] = None
    takeOffRefPointAGLHeight: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "droneInfo" and v is not None:
                    result[k] = v.to_dict()
                elif k == "payloadInfo" and v is not None:
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlMissionConfig":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        if "droneInfo" in filtered_data and filtered_data["droneInfo"]:
            filtered_data["droneInfo"] = KmlDroneInfo.from_dict(
                filtered_data["droneInfo"]
            )
        if "payloadInfo" in filtered_data and filtered_data["payloadInfo"]:
            filtered_data["payloadInfo"] = KmlPayloadInfo.from_dict(
                filtered_data["payloadInfo"]
            )

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlMissionConfig":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlFolder:
    """
    对应kml Folder中的KmlFolder 文件夹类
    """

    templateId: Optional[str] = None
    autoFlightSpeed: Optional[str] = None
    templateType: Optional[str] = None
    waylineCoordinateSysParam: Optional["KmlWayLineCoordinateSysParam"] = None
    payloadParam: Optional["KmlPayloadParam"] = None

    # 以下为 wpml 文件使用
    executeHeightMode: Optional[str] = None
    waylineId: Optional[str] = None
    actionGroup: Optional["KmlActionGroup"] = None

    # 以下为航点飞行模板元素
    globalWaypointTurnMode: Optional[str] = None
    globalUseStraightLine: Optional[str] = None
    gimbalPitchMode: Optional[str] = None
    globalHeight: Optional[str] = None
    globalWaypointHeadingParam: Optional["KmlGlobalWaypointHeadingParam"] = None
    placemarkList: List["KmlPlacemark"] = None

    def __post_init__(self):
        if self.placemarkList is None:
            self.placemarkList = []

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "waylineCoordinateSysParam" and v is not None:
                    result[k] = v.to_dict()
                elif k == "payloadParam" and v is not None:
                    result[k] = v.to_dict()
                elif k == "actionGroup" and v is not None:
                    result[k] = v.to_dict()
                elif k == "globalWaypointHeadingParam" and v is not None:
                    result[k] = v.to_dict()
                elif k == "placemarkList" and v is not None:
                    result[k] = [item.to_dict() for item in v]
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlFolder":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        nested_mappings = {
            "waylineCoordinateSysParam": KmlWayLineCoordinateSysParam,
            "payloadParam": KmlPayloadParam,
            "actionGroup": KmlActionGroup,
            "globalWaypointHeadingParam": KmlGlobalWaypointHeadingParam,
        }

        for key, cls_type in nested_mappings.items():
            if key in filtered_data and filtered_data[key]:
                filtered_data[key] = cls_type.from_dict(filtered_data[key])

        # 特殊处理列表
        if "placemarkList" in filtered_data and filtered_data["placemarkList"]:
            filtered_data["placemarkList"] = [
                KmlPlacemark.from_dict(item) for item in filtered_data["placemarkList"]
            ]

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlFolder":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)

@dataclass
class KmlInfo:
    """
    对应kml 中的KmlInfo 信息类
    """

    xmlns: str = "http://www.opengis.net/kml/2.2"
    wpml: str = "http://www.dji.com/wpmz/1.0.4"
    document: Optional["KmlDocument"] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if k == "document" and v is not None:
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlInfo":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}

        # 特殊处理嵌套对象
        if "document" in filtered_data and filtered_data["document"]:
            filtered_data["document"] = KmlDocument.from_dict(filtered_data["document"])

        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlInfo":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class KmlParams:
    """
    KML参数类
    航线文件
    """

    # 航线类型
    templateType: Optional[str] = None

    # 无人机类型
    droneType: Optional[int] = None

    # 无人机子类型
    subDroneType: Optional[int] = None

    # 负载类型
    payloadType: Optional[int] = None

    # 负载挂载位置
    payloadPosition: Optional[int] = None

    # 航线结束动作
    finishAction: Optional[str] = None

    # 失控动作
    exitOnRcLostAction: Optional[str] = None

    # 参考起飞点
    takeOffRefPoint: Optional[str] = None

    # 全局航点转弯模式
    waypointTurnReq: Optional[object] = None

    # 全局航线高度
    globalHeight: Optional[float] = None

    # 全局偏航角模式
    waypointHeadingReq: Optional[object] = None

    # 云台俯仰角控制模式
    gimbalPitchMode: Optional[str] = None

    # 全局航线飞行速度
    autoFlightSpeed: Optional[float] = None

    # 负载图片存储类型
    imageFormat: Optional[str] = None

    # 航点列表
    routePointList: List[object] = None

    # 建图航拍、倾斜摄影、航带飞行模板参数
    mappingTypeReq: Optional[object] = None

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典"""
        return _clean_dict(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KmlParams":
        """从字典创建对象"""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """将对象序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "KmlParams":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)
