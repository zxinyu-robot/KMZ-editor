# KMZ 运行模板

按大疆 WPML 规范制作的标准 KMZ 模板，供 path_editor 读取并用于司空验证。

| 模板 | templateType | 用途 |
|------|--------------|------|
| mapping2d_standard | mapping2d | 面状航线（正射） |
| waypoint_standard | waypoint | 航点航线 |
| oblique_standard | mapping3d | 倾斜摄影 |
| root_wpmz | mapping2d | 原根目录 wpmz 迁入，含 res/dsm/ |

## mapping2d_standard

**mapping2d 面状航线**标准模板，符合司空面状航线格式。

### 结构

- `mapping2d_standard.kmz`：打包后的 KMZ（可直接作为 path_editor 输入）
- `mapping2d_standard/wpmz/`：解压后的 wpmz 目录
  - `template.kml`：区域模板（Polygon、missionConfig、waylineCoordinateSysParam）
  - `waylines.wpml`：航点序列（含 actionGroup，对齐司空格式）

### 动作组说明（司空格式）

actionGroup 仅在**首航点**定义，`actionGroupStartIndex`/`actionGroupEndIndex` 指定作用范围（0-3）：
- 触发方式：`multipleTiming`，间隔 2 秒
- 动作：云台 -45° + 拍照
- 需含完整 gimbal 参数：gimbalRollRotateEnable、gimbalRotateTimeEnable 等

### 动作库 Folder（folder-Action 模板拓展）

在 waylines.wpml 的 Document 下可增加「动作库」Folder，用于预定义可复用的动作模板，供 scripts 按航段绑定、解析分配。

| 字段 | 说明 |
|------|------|
| Folder name | 可为「动作库」「ActionLibrary」「动作模板库」 |
| Data name | `actionTemplate` 或 `action_template` |
| value | JSON 格式：`{"id":"photo_45","name":"俯拍45度","trigger":{"type":"multipleTiming","param":"2.0"},"actions":[...]}` |

**JSON 结构**：
- `id`：模板唯一标识
- `name`：显示名称
- `trigger.type`：触发类型（`multipleTiming` 间隔触发、`reachPoint` 到达航点触发等）
- `trigger.param`：触发参数（如间隔秒数）
- `actions`：动作列表，每项含 `func`（如 gimbalRotate、takePhoto）和 `params`

**内置模板**：`photo_45`（云台 -45° + 拍照，2 秒间隔）、`photo_only`（仅拍照，到达触发）。`read_kmz` 会将解析结果写入 `params["action_library"]`，供导出或任务分配使用。

### AI 识别 Folder（司空兼容说明）

AI识别 Folder 使用 ExtendedData 定义航段与识别类型。**为兼容司空导入，当前模板已移除 AI Folder**；若需保留，可单独维护一份含 AI 配置的模板供 scripts 解析使用。

| 字段 | 说明 |
|------|------|
| aiSegment | 单段配置，格式：`waylineId=0;startIndex=0;endIndex=3;types=smoke,person,illegal_building,truck` |
| waylineId | 航线 Folder 的 waylineId |
| startIndex/endIndex | 航点索引范围 |
| types | 识别类型，逗号分隔（smoke=烟雾, person=人, illegal_building=违章建筑, truck=大卡车 等） |

多段配置时添加多个 `<Data name="aiSegment">`。

### 关键字段

| 字段 | 值 | 说明 |
|------|-----|------|
| templateType | mapping2d | 司空面状航线 |
| coordinateMode | WGS84 | 坐标模式 |
| heightMode | EGM96 | 高度模式 |
| executeHeightMode | relativeToStartPoint | waylines 高度模式（与司空示例一致） |
| droneEnumValue | 67 | M30 系列 |
| payloadEnumValue | 52 | M30 双光相机 |
| overlap | 80/70 | 正交/倾斜重叠率 |

### 用法

```bash
# 用 path_editor 读取 KMZ 模板并生成航线（输入须为 .kmz 文件）
PYTHONPATH=scripts python3 scripts/path_editor.py work_dir/templates/mapping2d_standard.kmz -o work_dir/mapping2dOutput.kmz --spacing 15
```

> 司空平台禁止文件名中的字符：`< > : " / \ | ? * . _`，建议输出使用驼峰命名（如 mapping2dOutput.kmz）。

### 司空验证

将导出的 `work_dir/mapping2dOutput.kmz` 上传至司空，验证：

1. 能否正确解析
2. 面状航线是否显示为扫线航点（而非仅 4 个角点）
3. 各航点动作组是否正确执行

---

## waypoint_standard

**waypoint 航点航线**标准模板，符合司空航点航线格式。输入为点序列（GeoJSON MultiPoint 或 JSON 点数组），无 Polygon 区域。

### 结构

- `waypoint_standard.kmz`：打包后的 KMZ
- `waypoint_standard/wpmz/`
  - `template.kml`：航点模板（多个 Point Placemark、missionConfig、waylineCoordinateSysParam）
  - `waylines.wpml`：航点序列（含 actionGroup、动作库）

### 关键字段

| 字段 | 值 | 说明 |
|------|-----|------|
| templateType | waypoint | 司空航点航线 |
| gimbalPitchMode | manual | 云台手动模式 |
| executeHeightMode | relativeToStartPoint | waylines 高度模式 |

### 用法

```bash
# 直接导出
PYTHONPATH=scripts python3 scripts/path_editor.py work_dir/templates/waypoint_standard.kmz -o work_dir/waypointOutput.kmz

# 逐点编辑后导出（--edit 指定操作 JSON）
PYTHONPATH=scripts python3 scripts/path_editor.py work_dir/templates/waypoint_standard.kmz -o work_dir/waypointEdited.kmz --edit work_dir/edits_example.json
```

**编辑操作**：`--edit` 接收 JSON 文件，含 `operations` 数组，支持 `add`、`delete`、`move`、`reorder`。

---

## oblique_standard

**oblique（mapping3d）倾斜摄影**标准模板，符合司空倾斜摄影格式。输入为 Polygon 区域，与 mapping2d 类似，但含倾斜云台俯仰角、倾斜重叠率等参数。

### 结构

- `oblique_standard.kmz`：打包后的 KMZ
- `oblique_standard/wpmz/`
  - `template.kml`：区域模板（Polygon、inclinedGimbalPitch=-45、overlap 等）
  - `waylines.wpml`：航点序列（扫线航点，云台 -45°）

### 关键字段

| 字段 | 值 | 说明 |
|------|-----|------|
| templateType | mapping3d | 司空倾斜摄影 |
| inclinedGimbalPitch | -45 | 倾斜云台俯仰角 |
| overlap | ortho/inclined | 正交与倾斜重叠率 |

### 用法

```bash
PYTHONPATH=scripts python3 scripts/path_editor.py work_dir/templates/oblique_standard.kmz -o work_dir/obliqueOutput.kmz --spacing 15
```

---

*模板区域：杭州附近约 1km² 矩形（120.15–120.16°E, 30.28–30.29°N），可替换为实际测区坐标。*
