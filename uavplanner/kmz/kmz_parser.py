# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: KMZ 解压校验与 KML/WPML 解析入口
# Author:      SubChange
# Version:     1.0
# Time:        2025-08-31
# Copyright:   (c) 2025 SubChange. All rights reserved.
# ------------------------------------------------------------ #

import os
import zipfile
from typing import Any, Dict, Tuple, List, Optional
from lxml import etree
import re
import json

from uavplanner.kmz.kml_modes import KmlDocument

# 要求的 wpmz 子目录必须包含的文件
REQUIRED_WPMZ_FILES = {"template.kml", "waylines.wpml"}
WPMZ_FOLDER_NAME = "wpmz"
class KMZValidationError(Exception):
    """自定义异常：KMZ 校验失败"""
    pass


class KMZParser:
    """
    KMZ文件解析器类
    负责解析KMZ文件中的KML和WPML内容
    """

    def __init__(self, file_path: str):
        """
        初始化KMZ解析器

        :param file_path: KMZ文件路径
        """
        self.file_path = file_path
        self.zip_ref = None

    def validate_kmz_file(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        验证 KMZ 文件格式和内容结构

        :return: (success: bool, message: str, info: dict)
        """
        try:
            # 0. 检查文件是否存在和大小
            if not os.path.exists(self.file_path):
                return False, "文件不存在", {}
            
            file_size = os.path.getsize(self.file_path)
            if file_size == 0:
                return False, "文件为空，无法解析", {}
            
            with zipfile.ZipFile(self.file_path, "r") as zip_ref:
                # 1. 检查是否损坏
                bad_file = zip_ref.testzip()
                if bad_file:
                    raise KMZValidationError(f"压缩包已损坏，错误文件: {bad_file}")

                file_list = zip_ref.namelist()
                
                # 2. 检查压缩包是否为空
                if not file_list:
                    return False, "KMZ 文件中没有任何内容", {}

                # 3. 查找 wpmz 目录下的文件
                wpmz_files = []
                for f in file_list:
                    # 支持 / 和 \ 路径分隔符
                    if f.lower().startswith(f"{WPMZ_FOLDER_NAME}/") or f.lower().startswith(
                        f"{WPMZ_FOLDER_NAME}\\"
                    ):
                        filename = f.split("/")[-1].split("\\")[-1]
                        wpmz_files.append(filename)

                if not wpmz_files:
                    available_dirs = set(f.split("/")[0] for f in file_list)
                    raise KMZValidationError(
                        f"缺少 '{WPMZ_FOLDER_NAME}' 文件夹。当前顶层目录: {list(available_dirs)}"
                    )

                # 4. 检查必需文件
                wpmz_set = set(wpmz_files)
                missing = REQUIRED_WPMZ_FILES - wpmz_set
                if missing:
                    raise KMZValidationError(
                        f"wpmz 文件夹中缺少文件: {list(missing)}。已找到: {wpmz_files}"
                    )

                # 成功
                return (
                    True,
                    "KMZ 文件校验通过",
                    {
                        "folder": WPMZ_FOLDER_NAME,
                        "files": sorted(wpmz_files),
                        "required_files_present": True,
                        "total_files_in_kmz": len(file_list),
                        "original_filename": os.path.basename(self.file_path)
                        # if "os" in globals()
                        # else "unknown",
                    },
                )

        except zipfile.BadZipFile:
            return False, "文件不是有效的 ZIP/KMZ 格式", {}
        except KMZValidationError as e:
            return False, f"{str(e)}", {}
        except Exception as e:
            return False, f"未知错误: {str(e)}", {}

    def get_kmz_info(self) -> dict:
        """
        提取 KMZ 文件信息（仅在校验通过后调用）

        :return: 包含文件结构信息的字典
        """
        success, msg, info = self.validate_kmz_file()
        if not success:
            raise ValueError(msg)
        return info
    
    def parse_kmz_files(self) -> dict:
        """解析 KMZ 文件中的 KML 内容

        Raises:
            KMZValidationError: _description_
            KMZValidationError: _description_

        Returns:
            dict: 解析后的 KML 信息字典
        """
        try:
            with zipfile.ZipFile(self.file_path, "r") as zip_ref:
                # 查找并读取 KML 文件
                kml_files = []
                wpml_files = []

                for file_name in zip_ref.namelist():
                    if file_name.endswith(".kml") and "template.kml" in file_name.lower():
                        kml_files.append(file_name)
                    elif (
                        file_name.endswith(".wpml") and "waylines.wpml" in file_name.lower()
                    ):
                        wpml_files.append(file_name)

                # 读取 template.kml 文件
                template_kml_name = None
                template_kml_content = None
                if kml_files:
                    template_kml_name = kml_files[0]
                    template_kml_content = zip_ref.read(template_kml_name)

                # 读取 waylines.wpml 文件
                waylines_wpml_name = None
                waylines_wpml_content = None
                if wpml_files:
                    waylines_wpml_name = wpml_files[0]
                    waylines_wpml_content = zip_ref.read(waylines_wpml_name)

                if not template_kml_content and not waylines_wpml_content:
                    raise KMZValidationError(
                        "KMZ 文件中未找到 template.kml 或 waylines.wpml 文件"
                    )

                result = {
                    "parsed_files": {
                        "template_kml": template_kml_name,
                        "waylines_wpml": waylines_wpml_name,
                    }
                }
            return result
        except KMZValidationError:
            raise
        except Exception as e:
            raise KMZValidationError(f"解析 KML 内容时出错: {str(e)}")

    def parse_kmz_kml_content(self) -> dict:
        """
        解析 KMZ 文件中的 KML 内容

        :return: 解析后的 KML 信息字典
        """
        try:
            with zipfile.ZipFile(self.file_path, "r") as zip_ref:
                # 查找并读取 KML 文件
                kml_files = []
                wpml_files = []

                for file_name in zip_ref.namelist():
                    if file_name.endswith(".kml") and "template.kml" in file_name.lower():
                        kml_files.append(file_name)
                    elif (
                        file_name.endswith(".wpml") and "waylines.wpml" in file_name.lower()
                    ):
                        wpml_files.append(file_name)

                # 读取 template.kml 文件
                template_kml_content = None
                template_kml_name = None
                if kml_files:
                    template_kml_name = kml_files[0]
                    template_kml_content = zip_ref.read(template_kml_name)

                # 读取 waylines.wpml 文件
                waylines_wpml_content = None
                waylines_wpml_name = None
                if wpml_files:
                    waylines_wpml_name = wpml_files[0]
                    waylines_wpml_content = zip_ref.read(waylines_wpml_name)

                if not template_kml_content and not waylines_wpml_content:
                    raise KMZValidationError(
                        "KMZ 文件中未找到 template.kml 或 waylines.wpml 文件"
                    )

                result = {
                    "parsed_files": {
                        "template_kml": template_kml_name,
                        "waylines_wpml": waylines_wpml_name,
                    },
                    "template_kml_org": template_kml_content, # bytes
                    "waylines_wpml_org": waylines_wpml_content, # bytes
                    "template_kml_features": [],
                    "waylines_wpml_features": [],
                }

                # 解析 template.kml
                if template_kml_content:
                    features = self._parse_kml_content(template_kml_content) # FIXME 这里的`templpate`和下main的`waylines`是暂时不区分吗？我看似乎2者的内容不太一样的
                    document = None  # 初始化为 None
                    for feature in features:
                        if feature['type'] == 'Document':
                            document = KmlDocument.from_dict(feature)
                            break  # 找到后提前退出循环

                    if document is None:
                        raise KMZValidationError("未在 template.kml 中找到有效的 Document 节点")

                    result["template_kml_features"] = features
                
                # 解析 waylines.wpml
                if waylines_wpml_content:
                    features = self._parse_kml_content(waylines_wpml_content)
                    document = None  # 初始化为 None
                    for feature in features:
                        if feature['type'] == 'Document':
                            document = KmlDocument.from_dict(feature)
                            break  # 找到后提前退出循环

                    if document is None:
                        raise KMZValidationError("未在 waylines.kml 中找到有效的 Document 节点")

                    result["waylines_wpml_features"] = features
                return result

        except KMZValidationError:
            raise
        except Exception as e:
            raise KMZValidationError(f"解析 KML 内容时出错: {str(e)}")

    def _clean_kml_content_bytes(self, kml_content: bytes) -> bytes:
        """
        清理 KML 字节内容，移除可能导致解析错误的字符

        :param kml_content: 原始 KML 字节内容
        :return: 清理后的 KML 字节内容
        """
        # 如果是字节数据，先解码为字符串进行清理，然后再编码回字节
        if isinstance(kml_content, bytes):
            try:
                # 尝试 UTF-8 解码
                kml_str = kml_content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    # 尝试 GBK 解码
                    kml_str = kml_content.decode("gbk")
                except UnicodeDecodeError:
                    # 如果都失败，忽略错误
                    kml_str = kml_content.decode("utf-8", errors="ignore")

            # 移除可能导致问题的控制字符（保留换行符、制表符等）
            cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", kml_str)

            # 移除 XML 声明中的 encoding 属性，避免 fastkml 报错
            cleaned = re.sub(
                r'(<\?xml[^>]*)encoding\s*=\s*["\'][^"\']*["\']([^>]*\?>)', r"\1\2", cleaned
            )

            # 确保 XML 声明格式正确
            if cleaned.startswith("<?xml"):
                if "version" not in cleaned.split("?>")[0]:
                    cleaned = (
                        '<?xml version="1.0"?>' + cleaned.split("?>", 1)[1]
                        if "?>" in cleaned
                        else '<?xml version="1.0"?>' + cleaned
                    )

            return cleaned.encode("utf-8")

        return kml_content

    def _parse_kml_content(self, kml_content: bytes) -> list:
        try:
            # 清理并解析 KML 内容
            cleaned_content = self._clean_kml_content_bytes(kml_content)
            
            # 解析 XML
            root = etree.fromstring(cleaned_content)
            
            # 定义命名空间
            namespaces = {
                'kml': 'http://www.opengis.net/kml/2.2',
                'wpml': 'http://www.dji.com/wpmz/1.0.6'
            }
            
            # 提取信息
            features = []
            
            # 查找 Document 节点
            documents = root.xpath('//kml:Document', namespaces=namespaces)
            for doc in documents:
                doc_info = {
                    'type': 'Document',
                    'author': self._get_text_or_none(doc.xpath('./wpml:author/text()', namespaces=namespaces)),
                    'createTime': self._get_text_or_none(doc.xpath('./wpml:createTime/text()', namespaces=namespaces)),
                    'updateTime': self._get_text_or_none(doc.xpath('./wpml:updateTime/text()', namespaces=namespaces)),
                    'Folder': []
                }
                doc_extended_data = self._parse_extended_data(doc, namespaces)
                if doc_extended_data:
                    doc_info['ExtendedData'] = doc_extended_data
                
                # 解析 missionConfig
                mission_configs = doc.xpath('./wpml:missionConfig', namespaces=namespaces)
                for mission_config in mission_configs:
                    config_info = self._parse_mission_config(mission_config, namespaces)
                    doc_info['missionConfig'] = config_info
                
                # 查找 Folder 节点
                folders = doc.xpath('./kml:Folder', namespaces=namespaces)
                for folder in folders:
                    folder_info = self._parse_folder(folder, namespaces)
                    if doc_extended_data:
                        for key, value in doc_extended_data.items():
                            if key not in folder_info:
                                folder_info[key] = value
                    doc_info['Folder'].append(folder_info)
                
                features.append(doc_info)
            
            return features
            
        except Exception as e:
            print(f"解析 KML 内容时出错: {str(e)}")
            return []

    def _get_text_or_none(self, xpath_result):
        """获取 xpath 结果中的文本，如果没有则返回 None"""
        return xpath_result[0] if xpath_result else None

    def _parse_extended_data(self, element, namespaces):
        """解析 KML ExtendedData/Data(name=value)。

        目前用于回读由导出链路写入 template.kml 的规划参数（如 gsd_cm_per_px）。
        """
        out = {}
        data_nodes = element.xpath('./kml:ExtendedData/kml:Data', namespaces=namespaces)
        for data_node in data_nodes:
            name = (data_node.attrib.get('name') or '').strip()
            if not name:
                continue
            value_text = self._get_text_or_none(data_node.xpath('./kml:value/text()', namespaces=namespaces))
            if value_text is None:
                continue
            value_text = value_text.strip()
            if value_text == '':
                continue
            if name == 'gsd_cm_per_px':
                try:
                    out[name] = float(value_text)
                    continue
                except (TypeError, ValueError):
                    pass
            out[name] = value_text
        return out

    def _parse_mission_config(self, mission_config_element, namespaces):
        """解析 missionConfig 元素并映射到 KmlMissionConfig 模型"""
        config_info = {
            'type': 'missionConfig',
            'flyToWayLineMode': self._get_text_or_none(mission_config_element.xpath('./wpml:flyToWaylineMode/text()', namespaces=namespaces)),
            'finishAction': self._get_text_or_none(mission_config_element.xpath('./wpml:finishAction/text()', namespaces=namespaces)),
            'exitOnRCLost': self._get_text_or_none(mission_config_element.xpath('./wpml:exitOnRCLost/text()', namespaces=namespaces)),
            'executeRCLostAction': self._get_text_or_none(mission_config_element.xpath('./wpml:executeRCLostAction/text()', namespaces=namespaces)),
            'takeOffSecurityHeight': self._get_text_or_none(mission_config_element.xpath('./wpml:takeOffSecurityHeight/text()', namespaces=namespaces)),
            'globalTransitionalSpeed': self._get_text_or_none(mission_config_element.xpath('./wpml:globalTransitionalSpeed/text()', namespaces=namespaces)),
            'globalRTHHeight': self._get_text_or_none(mission_config_element.xpath('./wpml:globalRTHHeight/text()', namespaces=namespaces)),
            'takeOffRefPoint': self._get_text_or_none(mission_config_element.xpath('./wpml:takeOffRefPoint/text()', namespaces=namespaces)),
            'takeOffRefPointAGLHeight': self._get_text_or_none(mission_config_element.xpath('./wpml:takeOffRefPointAGLHeight/text()', namespaces=namespaces)),
        }
        
        # 解析 droneInfo
        drone_infos = mission_config_element.xpath('./wpml:droneInfo', namespaces=namespaces)
        for drone_info in drone_infos:
            config_info['droneInfo'] = {
                'droneEnumValue': self._get_text_or_none(drone_info.xpath('./wpml:droneEnumValue/text()', namespaces=namespaces)),
                'droneSubEnumValue': self._get_text_or_none(drone_info.xpath('./wpml:droneSubEnumValue/text()', namespaces=namespaces)),
            }
        
        # 解析 payloadInfo
        payload_infos = mission_config_element.xpath('./wpml:payloadInfo', namespaces=namespaces)
        for payload_info in payload_infos:
            config_info['payloadInfo'] = {
                'payloadEnumValue': self._get_text_or_none(payload_info.xpath('./wpml:payloadEnumValue/text()', namespaces=namespaces)),
                'payloadSubEnumValue': self._get_text_or_none(payload_info.xpath('./wpml:payloadSubEnumValue/text()', namespaces=namespaces)),
                'payloadPositionIndex': self._get_text_or_none(payload_info.xpath('./wpml:payloadPositionIndex/text()', namespaces=namespaces)),
            }
        
        return config_info

    def _parse_folder(self, folder_element, namespaces):
        """解析 Folder 元素并映射到 KmlFolder 模型"""
        folder_info = {
            'type': 'Folder',
            'templateId': self._get_text_or_none(folder_element.xpath('./wpml:templateId/text()', namespaces=namespaces)),
            'templateType': self._get_text_or_none(folder_element.xpath('./wpml:templateType/text()', namespaces=namespaces)),
            'autoFlightSpeed': self._get_text_or_none(folder_element.xpath('./wpml:autoFlightSpeed/text()', namespaces=namespaces)),
            'executeHeightMode': self._get_text_or_none(folder_element.xpath('./wpml:executeHeightMode/text()', namespaces=namespaces)),
            'waylineId': self._get_text_or_none(folder_element.xpath('./wpml:waylineId/text()', namespaces=namespaces)),
            'distance': self._get_text_or_none(folder_element.xpath('./wpml:distance/text()', namespaces=namespaces)),
            'duration': self._get_text_or_none(folder_element.xpath('./wpml:duration/text()', namespaces=namespaces)),
            'globalWaypointTurnMode': self._get_text_or_none(folder_element.xpath('./wpml:globalWaypointTurnMode/text()', namespaces=namespaces)),
            'globalUseStraightLine': self._get_text_or_none(folder_element.xpath('./wpml:globalUseStraightLine/text()', namespaces=namespaces)),
            'gimbalPitchMode': self._get_text_or_none(folder_element.xpath('./wpml:gimbalPitchMode/text()', namespaces=namespaces)),
            'globalHeight': self._get_text_or_none(folder_element.xpath('./wpml:globalHeight/text()', namespaces=namespaces)),
            'Placemark': []
        }
        extended_data = self._parse_extended_data(folder_element, namespaces)
        if extended_data:
            folder_info.update(extended_data)
        
        # 解析 waylineCoordinateSysParam
        coord_sys_params = folder_element.xpath('./wpml:waylineCoordinateSysParam', namespaces=namespaces)
        for coord_sys_param in coord_sys_params:
            folder_info['waylineCoordinateSysParam'] = {
                'coordinateMode': self._get_text_or_none(coord_sys_param.xpath('./wpml:coordinateMode/text()', namespaces=namespaces)),
                'heightMode': self._get_text_or_none(coord_sys_param.xpath('./wpml:heightMode/text()', namespaces=namespaces)),
                'positioningType': self._get_text_or_none(coord_sys_param.xpath('./wpml:positioningType/text()', namespaces=namespaces)),
                'globalShootHeight': self._get_text_or_none(coord_sys_param.xpath('./wpml:globalShootHeight/text()', namespaces=namespaces)),
                'surfaceFollowModeEnable': self._get_text_or_none(coord_sys_param.xpath('./wpml:surfaceFollowModeEnable/text()', namespaces=namespaces)),
                'isRealtimeSurfaceFollow': self._get_text_or_none(coord_sys_param.xpath('./wpml:isRealtimeSurfaceFollow/text()', namespaces=namespaces)),
                'surfaceRelativeHeight': self._get_text_or_none(coord_sys_param.xpath('./wpml:surfaceRelativeHeight/text()', namespaces=namespaces)),
            }
        
        # 解析 payloadParam
        payload_params = folder_element.xpath('./wpml:payloadParam', namespaces=namespaces)
        for payload_param in payload_params:
            folder_info['payloadParam'] = {
                'payloadPositionIndex': self._get_text_or_none(payload_param.xpath('./wpml:payloadPositionIndex/text()', namespaces=namespaces)),
                'focusMode': self._get_text_or_none(payload_param.xpath('./wpml:focusMode/text()', namespaces=namespaces)),
                'meteringMode': self._get_text_or_none(payload_param.xpath('./wpml:meteringMode/text()', namespaces=namespaces)),
                'dewarpingEnable': self._get_text_or_none(payload_param.xpath('./wpml:dewarpingEnable/text()', namespaces=namespaces)),
                'returnMode': self._get_text_or_none(payload_param.xpath('./wpml:returnMode/text()', namespaces=namespaces)),
                'samplingRate': self._get_text_or_none(payload_param.xpath('./wpml:samplingRate/text()', namespaces=namespaces)),
                'scanningMode': self._get_text_or_none(payload_param.xpath('./wpml:scanningMode/text()', namespaces=namespaces)),
                'modelColoringEnable': self._get_text_or_none(payload_param.xpath('./wpml:modelColoringEnable/text()', namespaces=namespaces)),
                'imageFormat': self._get_text_or_none(payload_param.xpath('./wpml:imageFormat/text()', namespaces=namespaces)),
            }
        
        # 解析 globalWaypointHeadingParam
        global_heading_params = folder_element.xpath('./wpml:globalWaypointHeadingParam', namespaces=namespaces)
        for global_heading_param in global_heading_params:
            folder_info['globalWaypointHeadingParam'] = {
                'waypointHeadingMode': self._get_text_or_none(global_heading_param.xpath('./wpml:waypointHeadingMode/text()', namespaces=namespaces)),
                'waypointHeadingAngle': self._get_text_or_none(global_heading_param.xpath('./wpml:waypointHeadingAngle/text()', namespaces=namespaces)),
                'waypointPoiPoint': self._get_text_or_none(global_heading_param.xpath('./wpml:waypointPoiPoint/text()', namespaces=namespaces)),
                'waypointHeadingPathMode': self._get_text_or_none(global_heading_param.xpath('./wpml:waypointHeadingPathMode/text()', namespaces=namespaces)),
            }
        
        # 查找 Placemark 节点
        placemarks = folder_element.xpath('./kml:Placemark', namespaces=namespaces)
        for placemark in placemarks:
            placemark_info = self._parse_placemark(placemark, namespaces)
            folder_info['Placemark'].append(placemark_info)
        
        return folder_info

    def _parse_placemark(self, placemark_element, namespaces):
        """解析 Placemark 元素并映射到 KmlPlacemark 模型"""
        placemark_info = {
            'type': 'Placemark',
            'isRisky': self._get_text_or_none(placemark_element.xpath('./wpml:isRisky/text()', namespaces=namespaces)),
            'index': self._get_text_or_none(placemark_element.xpath('./wpml:index/text()', namespaces=namespaces)),
            'useGlobalHeight': self._get_text_or_none(placemark_element.xpath('./wpml:useGlobalHeight/text()', namespaces=namespaces)),
            'ellipsoidHeight': self._get_text_or_none(placemark_element.xpath('./wpml:ellipsoidHeight/text()', namespaces=namespaces)),
            'height': self._get_text_or_none(placemark_element.xpath('./wpml:height/text()', namespaces=namespaces)),
            'useGlobalSpeed': self._get_text_or_none(placemark_element.xpath('./wpml:useGlobalSpeed/text()', namespaces=namespaces)),
            'waypointSpeed': self._get_text_or_none(placemark_element.xpath('./wpml:waypointSpeed/text()', namespaces=namespaces)),
            'useGlobalHeadingParam': self._get_text_or_none(placemark_element.xpath('./wpml:useGlobalHeadingParam/text()', namespaces=namespaces)),
            'useGlobalTurnParam': self._get_text_or_none(placemark_element.xpath('./wpml:useGlobalTurnParam/text()', namespaces=namespaces)),
            'useStraightLine': self._get_text_or_none(placemark_element.xpath('./wpml:useStraightLine/text()', namespaces=namespaces)),
            'gimbalPitchAngle': self._get_text_or_none(placemark_element.xpath('./wpml:gimbalPitchAngle/text()', namespaces=namespaces)),
            'executeHeight': self._get_text_or_none(placemark_element.xpath('./wpml:executeHeight/text()', namespaces=namespaces)),
            'shootTopFaceEnable': self._get_text_or_none(placemark_element.xpath('./wpml:shootTopFaceEnable/text()', namespaces=namespaces)),
            'trajectoryType': self._get_text_or_none(placemark_element.xpath('./wpml:trajectoryType/text()', namespaces=namespaces)),
            'startPositionType': self._get_text_or_none(placemark_element.xpath('./wpml:startPositionType/text()', namespaces=namespaces)),
            'facadeWaylineEnable': self._get_text_or_none(placemark_element.xpath('./wpml:facadeWaylineEnable/text()', namespaces=namespaces)),
        }
        
        # 解析 Point 坐标
        coordinates = placemark_element.xpath('./kml:Point/kml:coordinates/text()', namespaces=namespaces)
        if coordinates:
            placemark_info['Point'] = {
                'coordinates': coordinates[0].strip()
            }
        
        # 解析 LineString 坐标
        coordinates = placemark_element.xpath('./kml:LineString/kml:coordinates/text()', namespaces=namespaces)
        if coordinates:
            placemark_info['LineString'] = {
                'coordinates': self._parse_coordinates_to_array(coordinates[0])
            }

        # 解析 Polygon 外环坐标
        coordinates = placemark_element.xpath(
            './kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates/text()',
            namespaces=namespaces
        )
        if coordinates:
            placemark_info['Polygon'] = {
                'outerBoundaryIs': {
                    'LinearRing': {
                        'coordinates': self._parse_coordinates_to_array(coordinates[0])
                    }
                }
            }
        
        # 解析 waypointHeadingParam
        heading_params = placemark_element.xpath('./wpml:waypointHeadingParam', namespaces=namespaces)
        for heading_param in heading_params:
            placemark_info['waypointHeadingParam'] = {
                'waypointHeadingMode': self._get_text_or_none(heading_param.xpath('./wpml:waypointHeadingMode/text()', namespaces=namespaces)),
                'waypointHeadingAngle': self._get_text_or_none(heading_param.xpath('./wpml:waypointHeadingAngle/text()', namespaces=namespaces)),
                'waypointPoiPoint': self._get_text_or_none(heading_param.xpath('./wpml:waypointPoiPoint/text()', namespaces=namespaces)),
                'waypointHeadingPathMode': self._get_text_or_none(heading_param.xpath('./wpml:waypointHeadingPathMode/text()', namespaces=namespaces)),
            }
        
        # 解析 waypointTurnParam
        turn_params = placemark_element.xpath('./wpml:waypointTurnParam', namespaces=namespaces)
        for turn_param in turn_params:
            placemark_info['waypointTurnParam'] = {
                'waypointTurnMode': self._get_text_or_none(turn_param.xpath('./wpml:waypointTurnMode/text()', namespaces=namespaces)),
                'waypointTurnDampingDist': self._get_text_or_none(turn_param.xpath('./wpml:waypointTurnDampingDist/text()', namespaces=namespaces)),
            }
        
        # 解析 actionGroup
        action_groups = placemark_element.xpath('./wpml:actionGroup', namespaces=namespaces)
        if action_groups:
            action_group_info = self._parse_action_group(action_groups[0], namespaces)
            placemark_info['actionGroup'] = action_group_info
        
        return placemark_info

    def _parse_action_group(self, action_group_element, namespaces):
        """解析 actionGroup 元素并映射到 KmlActionGroup 模型"""
        action_group_info = {
            'actionGroupId': self._get_text_or_none(action_group_element.xpath('./wpml:actionGroupId/text()', namespaces=namespaces)),
            'actionGroupStartIndex': self._get_text_or_none(action_group_element.xpath('./wpml:actionGroupStartIndex/text()', namespaces=namespaces)),
            'actionGroupEndIndex': self._get_text_or_none(action_group_element.xpath('./wpml:actionGroupEndIndex/text()', namespaces=namespaces)),
            'actionGroupMode': self._get_text_or_none(action_group_element.xpath('./wpml:actionGroupMode/text()', namespaces=namespaces)),
            'action': []
        }
        
        # 解析 actionTrigger
        action_triggers = action_group_element.xpath('./wpml:actionTrigger', namespaces=namespaces)
        for action_trigger in action_triggers:
            action_group_info['actionTrigger'] = {
                'actionTriggerType': self._get_text_or_none(action_trigger.xpath('./wpml:actionTriggerType/text()', namespaces=namespaces)),
                'actionTriggerParam': self._get_text_or_none(action_trigger.xpath('./wpml:actionTriggerParam/text()', namespaces=namespaces)),
            }
        
        # 解析 actions
        actions = action_group_element.xpath('./wpml:action', namespaces=namespaces)
        for action in actions:
            action_info = self._parse_action(action, namespaces)
            action_group_info['action'].append(action_info)
        
        return action_group_info

    def _parse_action(self, action_element, namespaces):
        """解析 action 元素并映射到 KmlAction 模型"""
        action_info = {
            'actionId': self._get_text_or_none(action_element.xpath('./wpml:actionId/text()', namespaces=namespaces)),
            'actionActuatorFunc': self._get_text_or_none(action_element.xpath('./wpml:actionActuatorFunc/text()', namespaces=namespaces)),
        }
        
        # 解析 actionActuatorFuncParam
        func_params = action_element.xpath('./wpml:actionActuatorFuncParam', namespaces=namespaces)
        for func_param in func_params:
            param_info = {}
            
            # 提取所有可能的参数
            param_elements = func_param.xpath('./*', namespaces=namespaces)
            for param_element in param_elements:
                tag_name = param_element.tag.split('}')[-1]  # 去除命名空间
                param_info[tag_name] = param_element.text
            
            action_info['actionActuatorFuncParam'] = param_info
        
        return action_info

    def _parse_coordinates_to_array(self, coordinates_text: str) -> List[str]:
        """将 KML 的坐标块转换为一维数组: ['lon,lat[,alt]', ...]"""
        points: List[str] = []
        if not coordinates_text:
            return points

        for token in coordinates_text.strip().split():
            parts = [p.strip() for p in token.split(",")]
            if len(parts) < 2:
                continue

            if len(parts) >= 3 and parts[2] != "":
                points.append(f"{parts[0]},{parts[1]},{parts[2]}")
            else:
                points.append(f"{parts[0]},{parts[1]}")
        return points

    #参数提取
    def _extract_template_info(self, kml_data):
        """
        从模板KML数据中提取信息
        
        Args:
            kml_data (dict): 解析后的KML数据
            
        Returns:
            tuple: (payload_information, drone_model_key, template_types)
        """
        payload_information = {}
        drone_model_key = ""
        template_type = ""
        
        template_kml_features = kml_data.get('template_kml_features', [])
        
        if template_kml_features and isinstance(template_kml_features, list):
            # 提取任务配置
            mission_config = template_kml_features[0].get('missionConfig', {})
            
            # 提取载荷信息
            payload_information = mission_config.get('payloadInfo', {})
            
            # 提取无人机信息并格式化为 0-{droneEnumValue}-{droneSubEnumValue}
            drone_info = mission_config.get('droneInfo', {})
            drone_enum_value = drone_info.get('droneEnumValue', '')
            drone_sub_enum_value = drone_info.get('droneSubEnumValue', '')
            if drone_enum_value and drone_sub_enum_value:
                drone_model_key = f"0-{drone_enum_value}-{drone_sub_enum_value}"
                
            # 提取模板类型
            folder = template_kml_features[0].get('Folder', [])
            if folder and isinstance(folder, list) and len(folder) > 0:
                raw_template_type = folder[0].get('templateType')
                template_type = raw_template_type or '' # waypoint
                # 如果为空或None，设置为默认值 "waypoint"
                if not template_type:
                    template_type = 'waypoint'
                
        return payload_information, drone_model_key, template_type

    def _extract_wayline_info(self, kml_data):
        """
        从航线KML数据中提取信息
        
        Args:
            kml_data (dict): 解析后的KML数据
            
        Returns:
            tuple: (distance, duration, wayline_point_nums)
        """
        distance = 0.0
        duration = 0.0
        wayline_point_nums = 0
        takeoff_ref_point = [0.0, 0.0, 0.0]
        
        waylines_wpml_features = kml_data.get('waylines_wpml_features', [])
        
        if waylines_wpml_features and isinstance(waylines_wpml_features, list):

            mission_config = waylines_wpml_features[0].get('missionConfig', {})
            if mission_config.get('takeOffRefPoint', None) is not None:
                takeoff_ref_point = list(map(float, mission_config.get('takeOffRefPoint', ['0.0','0.0','0.0']).split(','))) # NOTE 仅仅经纬度坐标

            folder = waylines_wpml_features[0].get('Folder', [])
            if folder and isinstance(folder, list) and len(folder) > 0:
                folder_data = folder[0]
                
                # 提取距离和持续时间
                distance = float(folder_data.get('distance') or 0.0)
                duration = float(folder_data.get('duration') or 0.0)
                
                # 计算航点数量
                placemarks = folder_data.get('Placemark', [])
                if placemarks and isinstance(placemarks, list):
                    wayline_point_nums = len(placemarks)
                    
        return distance, duration, wayline_point_nums, takeoff_ref_point
    
    def extract_waylines(self, kml_data:dict) -> list:
        """提取`wpml`中的航线 并返回列表

        Args:
            kml_data (dict): _description_

        Returns:
            list: _description_
        """
        waylines_wpml_features = kml_data.get('waylines_wpml_features', [])
        
        waylines = []
        if waylines_wpml_features and isinstance(waylines_wpml_features, list):
            folder = waylines_wpml_features[0].get('Folder', [])
            if folder and isinstance(folder, list) and len(folder) > 0:
                for fl in folder:

                    wayline = []
                    wayline_id = int(fl.get("waylineId", "-1"))
                    for pm in fl["Placemark"]:
                        point = pm["Point"]
                        lon, lat = point["coordinates"].split(",")
                        alt = pm["executeHeight"]
                        wayline.append((float(lon), float(lat), float(alt), wayline_id))
                    waylines.append(wayline)
                    
        return waylines
