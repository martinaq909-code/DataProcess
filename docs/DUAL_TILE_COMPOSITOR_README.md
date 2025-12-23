# 双源瓦片同步拼接功能

## 功能概述

双源瓦片同步拼接功能允许您同时处理Google和Bing DOM瓦片，生成具有相同地理范围的复合图像，便于后续的同范围对比分析。

## 核心组件

### 1. DualTileCompositor 类 (`core/dual_tile_compositor.py`)
- **功能**: 同时处理Google和Bing瓦片，确保相同地理范围
- **特点**:
  - 支持Google瓦片(PNG格式)和Bing DOM瓦片(JPEG格式)
  - 自动识别两个数据源的共同覆盖区域
  - 使用相同的地理坐标范围进行拼接
  - 保持现有的地理坐标命名格式（西_南_东_北）
  - 支持矢量数据的同时裁剪

### 2. 命令行工具 (`dual_tile_process.py`)
- **功能**: 提供命令行接口进行批量处理
- **使用方法**:
```bash
python dual_tile_process.py \
    --google_tiles_dir data/output/googletiles_l17 \
    --bing_tiles_dir data/output/bing_dom_tiles \
    --vector_file data/output/cleaned_osm.geojson \
    --output_dir data/output/dual_composited \
    --zoom 19
```

### 3. GUI界面 (`gui/dual_compositor_tab.py`)
- **功能**: 提供图形界面进行交互式操作
- **位置**: 主应用中的"双源拼接"标签页
- **特点**:
  - 分别选择Google和Bing瓦片目录
  - 可选的矢量文件输入
  - 实时日志显示
  - 一键同步处理

## 输出结构

处理后会在输出目录中创建以下结构：

```
output_dir/
├── google/
│   ├── images/     # Google复合图(PNG)
│   ├── vrts/       # Google VRT文件
│   └── vectors/    # Google矢量裁剪结果
└── bing/
    ├── images/     # Bing复合图(PNG)
    ├── vrts/       # Bing VRT文件
    └── vectors/    # Bing矢量裁剪结果
```

## 主要特性

1. **同步处理**: 同时处理Google和Bing瓦片，确保处理范围完全一致
2. **相同地理范围**: 生成的复合图具有相同的地理边界，便于对比分析
3. **统一命名**: 使用地理坐标格式命名（西_南_东_北），与现有Google瓦片命名保持一致
4. **矢量裁剪**: 可选的矢量数据裁剪功能，为两个数据源生成对应的矢量子集
5. **详细日志**: 提供详细的处理日志和统计信息
6. **错误处理**: 完善的错误处理和恢复机制

## 使用场景

- **数据对比分析**: 生成相同范围的高分辨率影像，用于Google和Bing数据的对比研究
- **变化检测**: 基于相同地理范围的多时相影像进行变化检测
- **模型训练**: 为机器学习模型提供配准的多源训练数据
- **质量评估**: 对比不同数据源在相同区域的表现质量

## 技术细节

- **瓦片格式**: Google瓦片(PNG)、Bing DOM瓦片(JPEG)
- **输出格式**: PNG图像 + VRT地理参考文件
- **坐标系统**: WGS84地理坐标系
- **复合图尺寸**: 1024x1024像素（4x4瓦片）
- **缩放级别**: 支持0-20级，默认19级

## 注意事项

1. 确保Google和Bing瓦片目录结构正确
2. 瓦片文件命名应该包含quadkey信息
3. 矢量文件应该是清洗后的OSM数据
4. 处理大量瓦片时可能需要较多内存
5. 输出目录应该有足够的磁盘空间