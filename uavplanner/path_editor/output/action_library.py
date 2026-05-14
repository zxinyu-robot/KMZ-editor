# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: KMZ 动作库 Folder-Action 模板解析
# Author:      zxinyu
# Version:     1.0
# Time:        2026-03-05
# ------------------------------------------------------------ #

"""KMZ 动作库 folder-Action 模板拓展：解析动作库 Folder，供航线编辑与任务分配使用。"""

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

NS_KML = "http://www.opengis.net/kml/2.2"
NS_WPML = "http://www.dji.com/wpmz/1.0.6"
K = "{%s}" % NS_KML
W = "{%s}" % NS_WPML


def _add_wpml_param(parent: ET.Element, key: str, value: Any) -> None:
    """将单个参数添加为 wpml 子元素。"""
    child = ET.SubElement(parent, f"{W}{key}")
    child.text = str(value)


def _tag_local(elem: ET.Element) -> str:
    return (elem.tag or "").split("}")[-1]


def _text(elem: Optional[ET.Element], default: str = "") -> str:
    return (elem.text or "").strip() if elem is not None else default


@dataclass
class ActionTemplate:
    """动作模板：可复用的动作组定义。"""
    id: str = ""
    name: str = ""
    trigger_type: str = "multipleTiming"
    trigger_param: str = "2.0"
    actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_action_group_dict(self) -> Dict[str, Any]:
        """转为与 wpml:actionGroup 兼容的结构。"""
        return {
            "trigger_type": self.trigger_type,
            "trigger_param": self.trigger_param,
            "actions": self.actions,
        }

    def build_wpml_action_group(
        self,
        start_index: int,
        end_index: int,
        group_id: int = 0,
    ) -> ET.Element:
        """构建 wpml:actionGroup 元素，用于插入 Placemark。

        Args:
            start_index: actionGroupStartIndex。
            end_index: actionGroupEndIndex。
            group_id: actionGroupId。

        Returns:
            wpml:actionGroup 根元素。
        """
        ag = ET.Element(f"{W}actionGroup")
        ET.SubElement(ag, f"{W}actionGroupId").text = str(group_id)
        ET.SubElement(ag, f"{W}actionGroupStartIndex").text = str(start_index)
        ET.SubElement(ag, f"{W}actionGroupEndIndex").text = str(end_index)
        ET.SubElement(ag, f"{W}actionGroupMode").text = "sequence"
        trig = ET.SubElement(ag, f"{W}actionTrigger")
        ET.SubElement(trig, f"{W}actionTriggerType").text = self.trigger_type
        ET.SubElement(trig, f"{W}actionTriggerParam").text = self.trigger_param
        for aid, act in enumerate(self.actions):
            func = act.get("func") or act.get("actionActuatorFunc", "takePhoto")
            params = act.get("params") or act.get("actionActuatorFuncParam") or {}
            if isinstance(params, dict):
                pass
            else:
                params = {}
            action_elem = ET.SubElement(ag, f"{W}action")
            ET.SubElement(action_elem, f"{W}actionId").text = str(aid)
            ET.SubElement(action_elem, f"{W}actionActuatorFunc").text = str(func)
            param_elem = ET.SubElement(action_elem, f"{W}actionActuatorFuncParam")
            for k, v in params.items():
                _add_wpml_param(param_elem, k, v)
        return ag


def _parse_action_template_value(value: str) -> Optional[ActionTemplate]:
    """解析 actionTemplate 的 value 字符串。格式：JSON 或 id=...;name=...;triggerType=..."""
    value = value.strip()
    if not value:
        return None
    try:
        data = json.loads(value)
        return ActionTemplate(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            trigger_type=str(data.get("trigger", {}).get("type", "multipleTiming") if isinstance(data.get("trigger"), dict) else "multipleTiming"),
            trigger_param=str(data.get("trigger", {}).get("param", "2.0") if isinstance(data.get("trigger"), dict) else "2.0"),
            actions=list(data.get("actions", [])),
        )
    except json.JSONDecodeError:
        pass
    out = ActionTemplate()
    for part in value.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k == "id":
                out.id = v
            elif k == "name":
                out.name = v
            elif k == "triggerType":
                out.trigger_type = v
            elif k == "triggerParam":
                out.trigger_param = v
            elif k == "actions":
                for act in v.split("|"):
                    act = act.strip()
                    if ":" in act:
                        func, params = act.split(":", 1)
                        out.actions.append({"func": func.strip(), "params": params.strip()})
    return out if out.id or out.actions else None


def parse_action_library_from_document(doc: ET.Element) -> Dict[str, ActionTemplate]:
    """
    从 Document 下解析所有「动作库」Folder，返回 id -> ActionTemplate 映射。

    Args:
        doc: KML Document 元素（或根元素）。

    Returns:
        {template_id: ActionTemplate, ...}
    """
    library: Dict[str, ActionTemplate] = {}
    for folder in doc.findall(f".//{K}Folder"):
        name_elem = folder.find(f"{K}name")
        name = _text(name_elem)
        if name not in ("动作库", "ActionLibrary", "动作模板库"):
            continue
        ext = folder.find(f"{K}ExtendedData")
        if ext is None:
            continue
        for data in ext.findall(f"{K}Data"):
            if (data.get("name") or "").lower() not in ("actiontemplate", "action_template"):
                continue
            val_elem = data.find(f"{K}value")
            val = _text(val_elem)
            tpl = _parse_action_template_value(val)
            if tpl and tpl.id:
                library[tpl.id] = tpl
    return library


def parse_action_library_from_wpml(wpml_bytes: bytes) -> Dict[str, ActionTemplate]:
    """
    从 waylines.wpml 原始内容解析动作库。

    Args:
        wpml_bytes: waylines.wpml 文件内容。

    Returns:
        {template_id: ActionTemplate, ...}
    """
    try:
        root = ET.fromstring(wpml_bytes)
    except ET.ParseError:
        return {}
    doc = root.find(f".//{K}Document") or root
    return parse_action_library_from_document(doc)


def get_photo_only_template() -> ActionTemplate:
    """返回仅拍照模板（到达首航点触发）。"""
    return ActionTemplate(
        id="photo_only",
        name="仅拍照",
        trigger_type="reachPoint",
        trigger_param="0",
        actions=[
            {
                "func": "takePhoto",
                "params": {
                    "payloadPositionIndex": "0",
                    "useGlobalPayloadLensIndex": "0",
                    "payloadLensIndex": "wide",
                },
            },
        ],
    )


def get_default_photo_template() -> ActionTemplate:
    """返回默认俯拍模板（云台 -45° + 拍照，间隔 2 秒）。"""
    return ActionTemplate(
        id="photo_45",
        name="俯拍45度",
        trigger_type="multipleTiming",
        trigger_param="2.0",
        actions=[
            {
                "func": "gimbalRotate",
                "params": {
                    "gimbalHeadingYawBase": "aircraft",
                    "gimbalRotateMode": "absoluteAngle",
                    "gimbalPitchRotateEnable": "1",
                    "gimbalPitchRotateAngle": "-45",
                    "gimbalRollRotateEnable": "0",
                    "gimbalRollRotateAngle": "0",
                    "gimbalYawRotateEnable": "1",
                    "gimbalYawRotateAngle": "0",
                    "gimbalRotateTimeEnable": "0",
                    "gimbalRotateTime": "10",
                    "payloadPositionIndex": "0",
                },
            },
            {
                "func": "takePhoto",
                "params": {
                    "payloadPositionIndex": "0",
                    "useGlobalPayloadLensIndex": "0",
                    "payloadLensIndex": "wide",
                },
            },
        ],
    )
