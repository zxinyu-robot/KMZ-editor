#!/bin/bash
# 生成所有航线类型的 KMZ 示例文件
# 用法: bash backend/app/utils/path_editor/tools/generate_all_kmz.sh
# 输入统一为 jiling1，输出至 work_dir/kmz_exports/

set -e
cd "$(dirname "$0")/../../../../.."
OUT=work_dir/kmz_exports
mkdir -p "$OUT"

# 清理并覆盖：删除将生成的同名 KMZ，确保每次生成为全新写入
rm -f "$OUT/surveyArea.kmz" "$OUT/waypoints.kmz" "$OUT/cylinderSpiral.kmz" "$OUT/corridorRoute.kmz"

echo "=== 1. 面状航线 (polygon) ==="
python3 -m backend.app.utils.path_editor.cli polygon examples/data/waypoints.geojson \
  -o "$OUT/surveyArea.kmz" --spacing 15 --margin 2 --camera-preset m3e
echo "[OK] $OUT/surveyArea.kmz"

echo ""
echo "=== 2. 航点航线 (waypoint) ==="
python3 -m backend.app.utils.path_editor.cli waypoint examples/data/waypoints.geojson \
  -o "$OUT/waypoints.kmz"
echo "[OK] $OUT/waypoints.kmz"

echo ""
echo "=== 3. 圆柱螺旋线 (cylinder) ==="
python3 -m backend.app.utils.path_editor.cli cylinder --center 113.9371,22.5796 --radius 50 \
  -o "$OUT/cylinderSpiral.kmz"
echo "[OK] $OUT/cylinderSpiral.kmz"

echo ""
echo "=== 4. 带状航线 (corridor) ==="
python3 -m backend.app.utils.path_editor.cli corridor examples/data/centerline_straight.geojson \
  -o "$OUT/corridorRoute.kmz" --half-width 20
echo "[OK] $OUT/corridorRoute.kmz"

echo ""
echo "=== 全部完成 ==="
ls -la "$OUT"/*.kmz
