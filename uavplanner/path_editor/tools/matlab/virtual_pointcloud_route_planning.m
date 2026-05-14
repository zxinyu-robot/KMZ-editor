%% 手动绘制巡检区域 + 障碍识别 + 路径规划
% 1. 加载 JPG 航拍图
% 2. 手动绘制巡检区域（多边形）
% 3. 仅在区域内进行障碍识别和路径规划

clear; clc; close all;
set(0, 'DefaultFigureVisible', 'on');

%% 1. 测试数据集路径
script_dir = fileparts(mfilename('fullpath'));
dataset_dir = fullfile(script_dir, '..', 'matlab测试数据集');
% 若自动路径不可用，可手动指定，例如: dataset_dir = 'C:\path\to\matlab测试数据集';
img_files = [];
if ~exist(dataset_dir, 'dir')
    warning('未找到测试数据集目录: %s', dataset_dir);
    dataset_dir = [];
else
    fprintf('测试数据集路径: %s\n', dataset_dir);
    img_files = dir(fullfile(dataset_dir, '*.JPG'));
    if isempty(img_files), img_files = dir(fullfile(dataset_dir, '*.jpg')); end
end

%% 2. 加载 JPG 图像
if isempty(dataset_dir)
    error('未找到测试数据集目录，请确保 matlab测试数据集 文件夹存在');
end
if isempty(img_files)
    error('测试数据集中无 JPG 图像，请将 JPG 文件放入 matlab测试数据集 文件夹');
end

img_path = fullfile(img_files(1).folder, img_files(1).name);
img = [];
try
    img = imread(img_path);
catch
    old_cd = pwd;
    try
        cd(img_files(1).folder);
        img = imread(img_files(1).name);
        cd(old_cd);
    catch
        try cd(old_cd); catch, end
        img = [];
    end
end
if isempty(img)
    fprintf('自动加载失败，请手动选择 JPG 图像文件...\n');
    [fname, fpath] = uigetfile({'*.jpg;*.JPG;*.jpeg;*.JPEG', 'JPEG 图像'; '*.*', '所有文件'}, ...
        '选择 matlab测试数据集 中的 JPG 图像', dataset_dir);
    if fname ~= 0
        img = imread(fullfile(fpath, fname));
        fprintf('手动选择加载成功: %s\n', fname);
    else
        error('未选择图像文件，程序终止');
    end
end

if size(img, 3) >= 3
    img_gray = rgb2gray(img);
else
    img_gray = img;
end
[H_img, W_img] = size(img_gray);

%% 2.1 手动绘制巡检区域（ROI）
fig_roi = figure('Name', '请绘制巡检区域', 'Color', 'w', 'Visible', 'on');
fig_roi.Position = [80, 80, 900, 650];
fprintf('请在图像上点击绘制巡检区域多边形，完成后双击或按回车键确认\n');
BW_roi = roipoly(img);
close(fig_roi);
if isempty(BW_roi) || ~any(BW_roi(:))
    error('未有效绘制巡检区域，请重新运行并在图像上点击绘制多边形');
end
fprintf('巡检区域已确定，区域内像素数: %d\n', nnz(BW_roi));

%% 2.2 在 ROI 内进行障碍识别
GRID_CELL_PX = max(1, round(min(H_img, W_img) / 80));
ny = ceil(H_img / GRID_CELL_PX);
nx = ceil(W_img / GRID_CELL_PX);
map = imresize(double(img_gray), [ny, nx], 'bilinear');
map = map / max(map(:));
OBSTACLE_THRESH = 0.35;
map = (map < OBSTACLE_THRESH);
se_small = strel('disk', 1);
map = imopen(map, se_small);
se = strel('disk', 1);
map = imdilate(map, se);
map = double(map);
% 应用 ROI 掩膜：区域外视为障碍
BW_roi_small = imresize(double(BW_roi), [ny, nx], 'nearest');
map(BW_roi_small < 0.5) = 1;
fprintf('障碍统计（仅 ROI 内）: 障碍格 %d / 总格 %d (%.1f%%)\n', nnz(map==1), numel(map), 100*nnz(map==1)/numel(map));
xmin = 0; xmax = nx; ymin = 0; ymax = ny;
d_grid = 1;
xg = (1:nx)'; yg = (1:ny)';
[Xg, Yg] = meshgrid(xg, yg);
Zg = zeros(size(Xg));
P_grid = [Xg(:), Yg(:), Zg(:)];
img_ref = img;
fprintf('已从 JPG 构建地图: %s, 栅格 %d x %d\n', img_files(1).name, ny, nx);

%% 3. 航线参考：Z 字形扫线覆盖（起点在 ROI 左下附近）
start_candidates = [];
for i = ny:-1:max(1, ny-15)
    for j = 1:min(20, nx)
        if map(i, j) == 0
            start_candidates = [start_candidates; i, j];
        end
    end
    if ~isempty(start_candidates), break; end
end
if isempty(start_candidates)
    [ii, jj] = find(map == 0);
    if ~isempty(ii)
        start_ij = [ii(1), jj(1)];
    else
        error('巡检区域内无可通行格！请调整 OBSTACLE_THRESH 或重新绘制更大区域');
    end
else
    start_ij = start_candidates(1, :);
end
start_xy = [xmin + (start_ij(2)-0.5)*d_grid, ymin + (start_ij(1)-0.5)*d_grid];

% 仅保留与起点连通的区域（避免 D* 因不连通而失败）
reachable = reachable_from(map, start_ij(1), start_ij(2), ny, nx);
n_reachable = sum(reachable(:));
fprintf('起点位置: (%d, %d), 连通区域大小: %d 格\n', start_ij(1), start_ij(2), n_reachable);

% 生成 Z 字形扫线航点序列：按行扫，奇数列从左到右、偶数列从右到左（仅取可通行且可达格）
raster_ij = [];
for i = 1:ny
    if mod(i, 2) == 1
        j_list = 1:nx;
    else
        j_list = nx:-1:1;
    end
    for j = j_list
        if map(i, j) == 0 && reachable(i, j)
            raster_ij = [raster_ij; i, j];
        end
    end
end
% 转成世界坐标 (x,y)
raster_xy = [xmin + (raster_ij(:,2)-1)*d_grid, ymin + (raster_ij(:,1)-1)*d_grid];
n_raster = size(raster_xy, 1);
fprintf('扫线点数量: %d\n', n_raster);
if n_raster == 0
    error('起点所在连通区域内无可扫线点，请减少障碍数量或调整阈值 OBSTACLE_THRESH');
end

%% 4. 用 D* 按扫线顺序连接：起点 -> 第1扫点 -> ... -> 第N扫点（不回到起点）
route_full = [start_xy(1), start_xy(2)];
current_ij = start_ij;
all_found = true;

% 起点 -> 第一个扫线点
failed_segments = [];
if n_raster >= 1
    goal_ij = raster_ij(1,:);
    [~, seg_xy, found] = dstar_grid(map, xg, yg, current_ij, goal_ij, xmin, ymin, d_grid);
    if found
        route_full = [route_full; seg_xy(2:end,:)];
    else
        route_full = [route_full; raster_xy(1,:)];
        all_found = false;
        failed_segments = [failed_segments; 0, 1];
        fprintf('警告: 起点 -> 第1扫点 D* 失败 (起点=%d,%d -> 目标=%d,%d)\n', current_ij(1), current_ij(2), goal_ij(1), goal_ij(2));
    end
    current_ij = raster_ij(1,:);
end

% 相邻扫线点之间用 D* 连接（沿扫线走向，遇障绕行），不回到起点
for k = 2:n_raster
    goal_ij = raster_ij(k,:);
    [~, seg_xy, found] = dstar_grid(map, xg, yg, current_ij, goal_ij, xmin, ymin, d_grid);
    if found
        route_full = [route_full; seg_xy(2:end,:)];
    else
        route_full = [route_full; raster_xy(k,:)];
        all_found = false;
        failed_segments = [failed_segments; k-1, k];
        if size(failed_segments, 1) <= 5  % 只打印前5个失败段
            fprintf('警告: 第%d -> 第%d扫点 D* 失败 (起点=%d,%d -> 目标=%d,%d)\n', k-1, k, current_ij(1), current_ij(2), goal_ij(1), goal_ij(2));
        end
    end
    current_ij = goal_ij;
end
if ~isempty(failed_segments)
    fprintf('共 %d 个 D* 段失败\n', size(failed_segments, 1));
end
path_xy = route_full(2:end,:);

%% 5. 画图：栅格等间距点 + 区域 + 障碍 + Z 字形扫线航线（参考图2）
fig1 = figure('Name', '平面栅格 + Z 字形扫线航线 (参考图2)', 'Color', 'w', 'Visible', 'on');
fig1.Position = [50, 50, 800, 600];

if ~isempty(img_ref)
    H_img = size(img_ref, 1); W_img = size(img_ref, 2);
    imshow(img_ref);
    set(gca, 'YDir', 'normal');
    hold on;
    % 绘制巡检区域边界
    if exist('BW_roi', 'var') && ~isempty(BW_roi)
        B = bwboundaries(BW_roi);
        for kb = 1:length(B)
            boundary = B{kb};
            plot(boundary(:,2), boundary(:,1), 'c-', 'LineWidth', 2);
        end
    end
    % 世界坐标 -> 图像像素坐标
    path_px = (route_full(:,1) - xmin) / max(1e-6, xmax - xmin) * (W_img - 1) + 1;
    path_py = (route_full(:,2) - ymin) / max(1e-6, ymax - ymin) * (H_img - 1) + 1;
    start_px = (start_xy(1) - xmin) / max(1e-6, xmax - xmin) * (W_img - 1) + 1;
    start_py = (start_xy(2) - ymin) / max(1e-6, ymax - ymin) * (H_img - 1) + 1;
    [ii, jj] = find(map == 1);
    if ~isempty(ii)
        obs_px = (jj - 0.5) / max(1, nx) * (W_img - 1) + 1;
        obs_py = (ii - 0.5) / max(1, ny) * (H_img - 1) + 1;
        scatter(obs_px, obs_py, 8, [0.8 0.2 0.2], 'filled', 'MarkerFaceAlpha', 0.6);
    end
    plot(start_px, start_py, 'ko', 'MarkerSize', 14, 'MarkerFaceColor', 'r');
    text(start_px + 5, start_py, 'S', 'FontSize', 10, 'FontWeight', 'bold');
    if size(route_full, 1) > 1
        plot(path_px, path_py, 'o', 'MarkerSize', 4, 'MarkerFaceColor', [0 0.8 0.3], 'MarkerEdgeColor', 'none');
        plot(path_px, path_py, 'g-', 'LineWidth', 1.8);
    end
    title('巡检区域 + 障碍识别 + 规划路径');
end
shg;
drawnow;

%% 6. 输出
if all_found && size(route_full,1) >= 2
    segs = sqrt(sum(diff(route_full(:,1:2)).^2, 2));
    fprintf('Z 字形扫线（不回到起点）| 扫线点数: %d | 路径节点数: %d | 总长: %.2f\n', n_raster, size(route_full,1), sum(segs));
else
    fprintf('存在未找到的 D* 段。\n');
end

%% ========== A* 栅格搜索（8 邻接，欧式代价） ==========
% 从 start 向 goal 搜索，更稳定可靠
function [path_ij, path_xy, found] = dstar_grid(map, ~, ~, start_ij, goal_ij, xmin, ymin, d_grid)
[ny, nx] = size(map);
path_ij = [];
path_xy = [];
found = false;
if map(start_ij(1), start_ij(2)) == 1 || map(goal_ij(1), goal_ij(2)) == 1
    return;
end
% 特殊处理：起点和目标点相同或相邻（8邻接）
if start_ij(1) == goal_ij(1) && start_ij(2) == goal_ij(2)
    path_ij = [start_ij(1), start_ij(2)];
    path_xy = [xmin + (start_ij(2)-1)*d_grid, ymin + (start_ij(1)-1)*d_grid];
    found = true;
    return;
end
di = abs(start_ij(1) - goal_ij(1));
dj = abs(start_ij(2) - goal_ij(2));
if di <= 1 && dj <= 1 && (di + dj > 0)
    path_ij = [start_ij(1), start_ij(2); goal_ij(1), goal_ij(2)];
    path_xy = [xmin + (start_ij(2)-1)*d_grid, ymin + (start_ij(1)-1)*d_grid; ...
               xmin + (goal_ij(2)-1)*d_grid, ymin + (goal_ij(1)-1)*d_grid];
    found = true;
    return;
end

% A* 算法：从 start 到 goal
dy = [-1 -1 -1  0  0  1  1  1];
dx = [-1  0  1 -1  1 -1  0  1];
cost_scale = [sqrt(2) 1 sqrt(2) 1 1 sqrt(2) 1 sqrt(2)];

g_score = inf(ny, nx);
g_score(start_ij(1), start_ij(2)) = 0;
h0 = heuristic(start_ij, goal_ij, d_grid);
open_list = [start_ij(1), start_ij(2), 0 + h0, 0];  % [i, j, f, g]
came_from = zeros(ny, nx, 2);  % 记录前驱 (i,j)
closed = false(ny, nx);

max_iter = ny * nx * 10;
iter = 0;
while ~isempty(open_list) && iter < max_iter
    iter = iter + 1;
    [~, idx] = min(open_list(:,3));
    u = open_list(idx, 1:2);
    open_list(idx,:) = [];
    i = u(1); j = u(2);
    if closed(i, j), continue; end
    closed(i, j) = true;
    if i == goal_ij(1) && j == goal_ij(2)
        found = true; break;
    end
    g_curr = g_score(i, j);
    for n = 1:8
        ni = i + dy(n); nj = j + dx(n);
        if ni < 1 || ni > ny || nj < 1 || nj > nx || map(ni, nj) == 1, continue; end
        move_cost = cost_scale(n) * d_grid;
        tentative_g = g_curr + move_cost;
        if tentative_g < g_score(ni, nj)
            g_score(ni, nj) = tentative_g;
            came_from(ni, nj, 1) = i;
            came_from(ni, nj, 2) = j;
            f_val = tentative_g + heuristic([ni, nj], goal_ij, d_grid);
            open_list = [open_list; ni, nj, f_val, tentative_g];
        end
    end
end
if ~found, return; end

% 回溯路径（从 goal 到 start）
path_ij = [];
i = goal_ij(1); j = goal_ij(2);
while true
    path_ij = [i, j; path_ij];
    if i == start_ij(1) && j == start_ij(2)
        break;
    end
    pi = came_from(i, j, 1); pj = came_from(i, j, 2);
    if pi < 1 || pj < 1
        found = false; return;
    end
    i = pi; j = pj;
end
path_xy = [xmin + (path_ij(:,2)-1)*d_grid, ymin + (path_ij(:,1)-1)*d_grid];
end

function h = heuristic(a_ij, b_ij, d_grid)
h = d_grid * sqrt((a_ij(1)-b_ij(1))^2 + (a_ij(2)-b_ij(2))^2);
end

function ij = xy_to_ij(xy, xmin, ymin, d_grid, ny, nx)
j = round((xy(1) - xmin) / d_grid) + 1;
i = round((xy(2) - ymin) / d_grid) + 1;
ij = [max(1, min(ny, i)), max(1, min(nx, j))];
end

function reachable = reachable_from(map, i0, j0, ny, nx)
% BFS 标记从 (i0,j0) 可达的所有可通行格
reachable = false(ny, nx);
if map(i0, j0) == 1, return; end
reachable(i0, j0) = true;
queue = [i0, j0];
dy = [-1 -1 -1  0  0  1  1  1];
dx = [-1  0  1 -1  1 -1  0  1];
while ~isempty(queue)
    u = queue(1,:); queue(1,:) = [];
    for n = 1:8
        ni = u(1) + dy(n); nj = u(2) + dx(n);
        if ni >= 1 && ni <= ny && nj >= 1 && nj <= nx && map(ni,nj) == 0 && ~reachable(ni,nj)
            reachable(ni, nj) = true;
            queue = [queue; ni, nj];
        end
    end
end
end

function [ij_free, found] = nearest_free_ij(map, i0, j0)
[ny, nx] = size(map);
if map(i0, j0) == 0
    ij_free = [i0, j0]; found = true; return;
end
for r = 1:max(ny, nx)
    for di = -r:r
        for dj = -r:r
            if abs(di) ~= r && abs(dj) ~= r, continue; end
            i = i0 + di; j = j0 + dj;
            if i >= 1 && i <= ny && j >= 1 && j <= nx && map(i, j) == 0
                ij_free = [i, j]; found = true; return;
            end
        end
    end
end
ij_free = [i0, j0]; found = false;
end
