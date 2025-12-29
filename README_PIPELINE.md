# 数据清洗流程脚本使用说明

## 功能概述

`process_pipeline.py` 是一个完整的命令行数据处理工具，可以从矢量边界文件自动完成以下流程：

1. 📍 读取矢量边界范围
2. 🛰️ 下载Google卫星瓦片
3. 🗺️ 下载OSM道路数据
4. 🧹 清洗OSM数据（提取主干道）
5. 🎨 拼接瓦片成1024x1024图像
6. ⚫ 黑边检测过滤
7. 🛣️ 道路筛选过滤

## 快速开始

### 基本用法

```bash
# 激活conda环境
conda activate labelme

# 最简单的调用（使用默认参数）
python process_pipeline.py -b "C:\path\to\boundary.shp" -o "D:\output"
```

### 完整参数示例

```bash
python process_pipeline.py \
    --boundary "C:\Users\user\Documents\boundary.shp" \
    --output "D:\data\processed" \
    --road-threshold 0.5 \
    --black-threshold 0.0625 \
    --zoom 17 \
    --verbose
```

## 参数说明

### 必需参数

| 参数 | 简写 | 说明 | 示例 |
|------|------|------|------|
| `--boundary` | `-b` | 矢量边界文件路径 | `boundary.shp` |
| `--output` | `-o` | 输出目录路径 | `D:\output` |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--road-threshold` | 0.5 | 道路筛选阈值（道路长度/对角线长度） |
| `--black-threshold` | 0.0625 | 黑边筛选阈值（黑像素比例，1/16） |
| `--zoom` | 17 | 瓦片缩放级别（10-19） |
| `--no-road-filter` | - | 禁用道路筛选，只使用黑边检测 |
| `--verbose` `-v` | - | 显示详细日志 |

## 输出目录结构

```
output/
├── tiles_z17/              # 下载的原始瓦片
│   ├── xxxxxxx.png
│   └── ...
├── osm_data/              # OSM道路数据
│   ├── osm_roads.geojson
│   └── osm_trunk_roads.geojson
├── composited/            # 拼接后的图像
│   └── images/
│       ├── 116.xxx_39.xxx_116.xxx_39.xxx.png
│       └── ...
├── filtered_images/       # 最终筛选后的图像（推荐用于训练）
│   ├── 116.xxx_39.xxx_116.xxx_39.xxx.png
│   └── ...
└── logs/                  # 处理日志
    └── pipeline_20251229_153000.log
```

## 使用场景示例

### 场景1：城市道路提取（推荐设置）

```bash
python process_pipeline.py \
    -b "city_boundary.shp" \
    -o "D:\city_data" \
    --road-threshold 0.5 \
    --zoom 18
```

### 场景2：高速公路区域（宽松阈值）

```bash
python process_pipeline.py \
    -b "highway_area.shp" \
    -o "D:\highway_data" \
    --road-threshold 0.2 \
    --zoom 17
```

### 场景3：只做黑边过滤（不筛选道路）

```bash
python process_pipeline.py \
    -b "area.shp" \
    -o "D:\output" \
    --no-road-filter
```

### 场景4：详细调试模式

```bash
python process_pipeline.py \
    -b "test_area.shp" \
    -o "D:\test" \
    --verbose
```

## 常见问题

### Q: 如何查看处理进度？

A: 查看控制台输出或日志文件 `output/logs/pipeline_*.log`

### Q: 下载失败或中断怎么办？

A: 脚本支持断点续传，直接重新运行相同命令即可继续下载

### Q: 支持哪些矢量文件格式？

A: 支持 Shapefile (.shp), GeoJSON (.geojson), GeoPackage (.gpkg), KML (.kml) 等所有GeoPandas支持的格式

### Q: 如何调整道路筛选严格程度？

A: 调整 `--road-threshold` 参数：
- `0.1-0.2`: 宽松（主要去除完全无路区域）
- `0.3-0.5`: 适中（保留有一定道路密度的区域）
- `0.5-1.0`: 严格（只保留道路非常密集的区域）

### Q: 如何选择合适的缩放级别？

A: 
- `zoom=17`: 适中分辨率，推荐用于城市道路
- `zoom=18`: 高分辨率，细节更多但下载量大
- `zoom=16`: 低分辨率，快速测试用

## 性能优化建议

1. **网络优化**：使用稳定的网络连接，脚本会自动重试失败的下载
2. **并行下载**：默认使用4个线程，已优化性能
3. **存储空间**：确保有足够磁盘空间（每个瓦片约10-50KB）
4. **测试先行**：先用小范围测试参数，确认效果后再处理大范围

## 技术支持

如有问题，请查看：
1. 日志文件：`output/logs/pipeline_*.log`
2. 测试报告：参考 `test/test_report.md` 和 `test_zn/test_report.md`
3. 实现文档：查看 `walkthrough.md`

---

**版本**: 1.0.0  
**更新日期**: 2025-12-29  
**维护团队**: DataProcess Team
