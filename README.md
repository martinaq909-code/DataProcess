# 地理数据处理工具集 (Geospatial Data Processing Toolkit) V0.0

## 🆕 本次版本更新（2026-01-12）

### 下载器（稳定性/可控性/可追溯）
*   **瓦片完整性校验**：遇到 `200` 但返回非图片内容（如 HTML/验证码页）会自动判定为无效并重试；已存在但过小/损坏的瓦片会自动删除并重下。
*   **下载任务 Manifest**：每次下载会在瓦片输出目录生成 `download_manifest.json`，记录 `run_id`、输入范围（bbox/矢量）、参数、统计信息、失败原因分布，以及自适应限速统计（如启用）。
*   **暂停/继续/取消**：下载过程支持暂停与继续（线程会阻塞等待恢复），取消会触发停止逻辑并尽快退出。
*   **自适应并发**：启用自适应限速时，每个批次会依据限速器建议动态调整实际 worker 数（不超过配置的 `max_workers`）。

### 命令行全流程（可审计级别的运行记录）
*   输出目录根部新增 `pipeline_manifest.json`：记录 `run_id`、参数、bbox、每一步（读取边界/下载瓦片/OSM/拼接/筛选）的 **开始/结束时间、耗时、状态、错误信息、关键指标**，以及主要产物文件大小与更新时间。
*   Pipeline manifest 会关联瓦片目录下的 `download_manifest.json` 路径，方便串联排查。

### GUI（体验增强）
*   “数据下载”模块新增 **暂停/继续/取消** 按钮与状态栏。
*   状态栏实时显示进度、下载速率与 ETA（基于日志估算）。

### 测试与依赖
*   新增离线测试覆盖下载器关键行为（非图片 200 响应重试、坏文件自动重下、manifest 产出）。
*   `requirements.txt` 新增 `pytest` 以运行测试。

### 升级注意事项
*   默认开启“已存在文件校验”，如果输出目录里存在 **空文件/过小文件/非图片**，会被自动删除并重下。
*   若你有特殊需求（例如完全跳过已有文件检查），可在创建下载器时设置 `verify_existing=False`。

### 如何快速验证
```bash
python -m pytest -q tests/test_tile_downloader_integrity.py
```

这是一个综合性的地理空间数据处理工具集，专为地理信息系统 (GIS) 和遥感数据处理设计。主要功能涵盖卫星影像下载、OSM道路矢量数据获取与清洗、瓦片拼接与清洗、以及深度学习标注数据（LabelMe JSON <-> Binary Mask）的高效转换。

## ✨ 核心特性

*   **多源数据获取**: 支持 **Google Satellite**、**Amap (高德)**、**USGS**、**OpenStreetMap** 等多种数据源。
*   **高稳健性下载引擎**:
    *   **智能故障转移**: 自动检测可用节点，主节点失效时自动切换至备用镜像。
    *   **反爬虫机制**: 内置 User-Agent 轮询与智能退避策略，有效降低被封禁风险。
    *   **断点续传**: 支持任务中断后从断点继续下载。
    *   **完整性校验**: 自动识别 200 返回的非图片内容（如验证码/HTML），并重试；对已存在但损坏/过小的瓦片会自动重下。
    *   **下载清单 (Manifest)**: 下载目录会生成 `download_manifest.json`，记录 bbox/zoom、参数、统计与自适应限速信息，便于复现实验与排查。
    *   **实时进度**: 所有耗时操作均包含详细的实时进度日志和状态反馈。
*   **高精度瓦片处理**:
    *   **精准拼接**: 生成地理坐标精确的 VRT 和 GeoTIFF/PNG 影像（EPSG:3857）。
    *   **瓦片清洗**: 基于黑边比例自动过滤无效瓦片，支持非破坏性筛选。
*   **全流程日志系统**: 详细的 `error.log` 记录，自动捕获界面与后台的所有异常，方便排查。
*   **可追溯运行记录**:
    *   下载目录：`download_manifest.json`
    *   命令行全流程：输出目录根部生成 `pipeline_manifest.json`（包含每一步 start/end、耗时、关键指标、产物文件大小等）

## 🛠️ 环境搭建指南

为了确保所有依赖库（特别是 GDAL 和 GeoPandas）能正确安装，强烈建议使用 **Anaconda** 或 **Miniconda** 进行环境管理。

### 1. 创建虚拟环境

打开 Anaconda Prompt 或终端，执行以下命令创建一个新的 Python 3.9 环境（推荐 3.9 版本以获得最佳兼容性）：

```bash
conda create -n dataprocess python=3.9
conda activate dataprocess
```

### 2. 安装核心依赖

由于 `labelme` 是本项目的关键组件，且 `geopandas` 在 Windows 下直接通过 pip 安装容易出错，建议按以下顺序安装：

#### 第一步：安装 LabelMe
```bash
pip install labelme
```

#### 第二步：安装 GeoPandas 和其他科学计算库
推荐使用 conda 安装 `geopandas` 和 `osmnx`，因为 conda 会自动处理底层的 C++ 依赖（如 GDAL, GEOS）：

```bash
conda install --channel conda-forge geopandas osmnx rasterio mercantile
```

#### 第三步：安装剩余依赖
安装项目中列出的其他 Python 库：

```bash
pip install -r requirements.txt
```

## 🚀 启动方式

环境配置完成后，在项目根目录下运行以下命令启动图形用户界面 (GUI)：

```bash
python main.py
```

## 📖 功能使用手册

### 1. 数据预处理 (Data Preprocessing)

此标签页采用 **四宫格布局**，集成了从数据获取到预处理的完整流程，每个模块都支持后台运行和实时日志输出。

*   **1. 数据下载 (左上)**:
    *   **下载类型**: 选择数据源（如 Google Satellite, Amap, USGS 等）。
    *   **BBox 设置**: 支持通过 Grid 布局快速输入经纬度范围 (Left/Right, Bottom/Top)，或从矢量文件读取。
    *   **输出目录**: 设置下载文件的保存位置。
    *   **功能**: 支持多线程并发下载，具备断点续传和自动重试功能。
    *   **控制**: 支持 **暂停/继续/取消**，并在状态栏显示实时进度与 ETA（基于日志估算）。

*   **2. 数据清洗 (右上)**:
    *   主要用于处理 OSM 矢量数据。
    *   **输入文件**: 选择下载的 OSM GeoJSON 文件。
    *   **提取主干道**: 自动过滤非主干道、地下道路及负层道路。
    *   **保存结果**: 将清洗后的数据保存为新的 GeoJSON 文件。

*   **3. 瓦片拼接 (左下)**:
    *   将下载的瓦片碎片拼接成完整的大图。
    *   **瓦片目录**: 指向包含瓦片图片的文件夹。
    *   **缩放级别**: 设置拼接的目标 Zoom Level。
    *   **输出结果**: 自动扫描目录下的所有瓦片，按坐标拼接成 1024x1024 像素的影像块。
    *   *注：拼接过程完全基于文件名中的 Quadkey 坐标，不依赖任何外部矢量文件。*

*   **4. 瓦片清洗 (右下)**:
    *   **输入目录**: 待清洗的瓦片/影像目录。
    *   **输出目录**: 清洗后有效图片的保存目录。
    *   **黑边阈值**: 设置允许的最大黑像素比例（默认 1/16）。
    *   **功能**: 自动计算每张图片的黑边比例，将符合要求的图片**复制**到输出目录（非破坏性操作）。

### 2. 标注转换 (Annotation Conversion)

此功能用于连接标注工具 (LabelMe) 和深度学习训练数据 (Mask) 之间的桥梁，支持批量处理和进度显示。

*   **Mask 转 LabelMe JSON**:
    *   适用于：已有二值 Mask 图像，需要导入 LabelMe 进行人工精修。
    *   **输入**: Mask 目录（二值图）+ 影像目录（原图）。
    *   **输出**: 生成对应的 JSON 文件，可在 LabelMe 中直接打开编辑。

*   **LabelMe JSON 转 Mask**:
    *   适用于：人工标注完成后，生成用于模型训练的二值 Mask。
    *   **输入**: 包含 JSON 文件的目录。
    *   **输出**: 生成对应的二值 Mask 图像。

### 3. 自定义 LabelMe (Custom LabelMe)

本项目集成了一个轻量级的 LabelMe 编辑器，无需单独启动外部程序即可快速查看和修改标注。

*   **加载数据**: 点击 **"Load Directories"**，分别设置：
    *   `Image Dir`: 原图目录
    *   `JSON Dir`: 标注文件目录
    *   `Save Dir`: 保存目录
*   **常用操作**:
    *   **Create Polygon**: 开始绘制新的多边形标注。
    *   **Edit Mode**: 编辑现有的标注点。
    *   **Save**: 保存修改。
*   **快捷键**:
    *   `Q`: 上一张图片
    *   `D`: 删除选中的标注
    *   `Ctrl+S`: 保存

## 📁 项目结构说明

```
dataprocess/
├── config/                 # 配置文件 (下载源URL、参数配置)
├── core/                   # 核心算法模块
│   ├── osm_fetcher.py      # OSM数据获取
│   ├── tile_downloader.py  # 瓦片下载器 (支持故障转移与并发)
│   ├── tile_compositor.py  # 瓦片拼接逻辑 (支持VRT生成)
│   ├── tile_filter.py      # 瓦片清洗逻辑 (黑边检测)
│   ├── labelme2mask.py     # JSON转Mask算法
│   ├── mask2labelme.py     # Mask转JSON算法
│   └── logger.py           # 全局日志模块
├── gui/                    # GUI 界面代码
│   ├── datapreprocessing_tab.py  # 预处理界面 (四宫格布局)
│   ├── mask_conversion_tab.py    # 转换界面
│   └── custom_labelme_tab.py     # 内嵌LabelMe界面
├── logs/                   # 运行日志 (自动轮转)
├── utils/                  # 通用工具
│   └── url_detector.py     # 服务器连通性检测
├── main.py                 # 程序启动入口
└── requirements.txt        # 依赖列表
```

## ⚠️ 常见问题

1.  **GeoPandas 导入错误**:
    *   如果启动时提示找不到 DLL 或模块，通常是 GDAL 环境问题。请尝试卸载 `geopandas` 和 `fiona`，然后使用 `conda install -c conda-forge geopandas` 重新安装。

2.  **地图瓦片无法下载**:
    *   **USGS**: 国内访问可能不稳定或超时，程序会自动重试，但若长时间 404/Timeout 属正常网络现象。
    *   **Google/Amap**: 程序内置了多节点切换，通常能保持稳定下载。

3.  **LabelMe 模块未找到**:
    *   确保已运行 `pip install labelme`。GUI 依赖于系统环境中安装的 `labelme` 库来加载画布组件。
