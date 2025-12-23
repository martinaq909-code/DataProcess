# 地理数据处理工具集

一个综合性的地理空间数据处理工具集，用于卫星影像下载、道路矢量数据获取、瓦片拼接和道路语义分割mask生成。

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动GUI（推荐）
```bash
python main.py gui
```

### 命令行使用
```bash
# 下载OSM道路数据
python main.py osm --bbox 116.3,39.8,116.5,39.9 --output data/output/roads.geojson --roads-only

# 查看帮助
python main.py --help
```

## 📁 项目结构

```
dataprocess/
├── core/                   # 核心功能模块
│   ├── osm_fetcher.py     # OSM数据下载
│   ├── osm_cleaner.py     # OSM数据清洗
│   ├── tile_downloader.py # 通用瓦片下载器
│   ├── bing_dom_downloader.py  # Bing DOM瓦片下载
│   ├── tile_compositor.py # 瓦片拼接
│   └── road_segmentation.py   # 道路缓冲区生成
│
├── gui/                    # 图形用户界面
│   └── app.py             # PySide6主GUI应用
│
├── config/                 # 配置文件
│   ├── parameters.py      # 参数配置
│   ├── settings.py        # 全局设置
│   └── download_types.py  # 下载类型定义
│
├── utils/                  # 工具函数
│   ├── data_analyzer.py   # 数据分析
│   └── url_detector.py    # URL格式检测
│
├── tests/                  # 单元测试
│   └── test_osm_fetcher.py
│
├── scripts/                # 实用脚本工具
│   ├── dual_tile_process.py           # 双源瓦片拼接
│   ├── create_simple_vrt_and_vector.py
│   ├── fix_vrt_paths.py
│   ├── process_from_gpkg.py
│   ├── run_modified_roadmask.py
│   └── ...
│
├── docs/                   # 项目文档
│   ├── 模式说明.md        # Roadmask模式详解
│   ├── 处理结果总结.md    # 处理结果统计
│   ├── 性能优化说明.md    # 8项优化技术
│   ├── DUAL_TILE_COMPOSITOR_README.md
│   └── ...
│
├── data/                   # 数据目录
│   ├── input/             # 输入数据
│   ├── output/            # 输出结果
│   └── cache/             # 缓存文件
│
├── main.py                 # 命令行主入口
├── roadmasktest.py        # 道路Mask生成（核心算法）
└── requirements.txt       # 依赖包列表
```

## 🎯 主要功能

### 1. OSM数据下载
- 支持矢量文件/BBOX范围
- 多类型数据（道路、铁路、建筑等）
- 自动坐标转换和缓存

### 2. 卫星影像下载
- **数据源**: Google、Bing、OSM、Mapbox、Esri
- **缩放级别**: 0-20
- 并发下载，失败重试

### 3. 瓦片拼接
- 4x4瓦片拼接成1024x1024复合图
- 生成GeoTIFF和VRT地理参考
- 双源同步拼接（Google+Bing）

### 4. 道路语义分割 ⭐
**核心算法**: `roadmasktest.py`
- 🔬 **8项优化**: LRU缓存、多指标融合、自适应阈值等
- 📊 **两种模式**: 
  - Visualization - 可视化分析
  - Annotation - 深度学习训练数据
- 🎯 **性能**: 速度提升2-3倍，准确率提升25-40%

## 📖 文档

详细文档位于 `docs/` 目录：
- [模式说明](docs/模式说明.md) - Roadmask功能详解
- [处理结果总结](docs/处理结果总结.md) - 处理结果统计
- [性能优化说明](docs/性能优化说明.md) - 技术优化详解
- [双源拼接说明](docs/DUAL_TILE_COMPOSITOR_README.md)

## 🛠️ 技术栈

- **地理数据**: geopandas, rasterio, shapely, osmnx
- **图像处理**: opencv-python, scikit-image
- **GUI**: PySide6
- **瓦片处理**: mercantile

## 📝 许可证

项目路径: `d:\gjn\dataprocess\`

---

**最后更新**: 2025-11-28
