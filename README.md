# 地理数据处理工具集 (Geospatial Data Processing Toolkit)

这是一个综合性的地理空间数据处理工具集，专为地理信息系统 (GIS) 和遥感数据处理设计。主要功能涵盖卫星影像下载、OSM道路矢量数据获取与清洗、瓦片拼接、以及深度学习标注数据（LabelMe JSON <-> Binary Mask）的高效转换。

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
conda install --channel conda-forge geopandas osmnx
```

#### 第三步：安装剩余依赖
安装项目中列出的其他 Python 库：

```bash
pip install -r requirements.txt
```

*如果遇到依赖冲突，请确保您的 `pip` 是最新的：`python -m pip install --upgrade pip`*

## 🚀 启动方式

环境配置完成后，在项目根目录下运行以下命令启动图形用户界面 (GUI)：

```bash
python main.py
```

## 📖 功能使用手册

### 1. 数据预处理 (Data Preprocessing)

此标签页集成了从数据获取到预处理的完整流程。

*   **1. 数据下载**:
    *   **下载类型**: 选择数据源（如 Google Satellite, Bing Maps, OSM Vector 等）。
    *   **BBox 设置**: 输入感兴趣区域的经纬度范围 (Left, Bottom, Right, Top)。
    *   **输出目录**: 设置下载文件的保存位置。
    *   点击 **"开始下载"** 即可启动多线程下载任务。

*   **2. 数据清洗**:
    *   主要用于处理 OSM 矢量数据。
    *   **输入文件**: 选择下载的 OSM GeoJSON 文件。
    *   **提取主干道**: 点击按钮可自动过滤出主要道路网络。
    *   **保存结果**: 将清洗后的数据保存为新的 GeoJSON 文件。

*   **3. 瓦片拼接**:
    *   将下载的瓦片碎片拼接成完整的大图（GeoTIFF/PNG）。
    *   **瓦片目录**: 指向包含瓦片图片的文件夹。
    *   **矢量文件**: (可选) 用于裁剪或参考的矢量范围。
    *   **缩放级别**: 设置拼接的目标 Zoom Level。

### 2. 标注转换 (Annotation Conversion)

此功能用于连接标注工具 (LabelMe) 和深度学习训练数据 (Mask) 之间的桥梁。

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
│   ├── tile_downloader.py  # 瓦片下载器
│   ├── tile_compositor.py  # 瓦片拼接逻辑
│   ├── labelme2mask.py     # JSON转Mask算法
│   └── mask2labelme.py     # Mask转JSON算法
├── gui/                    # GUI 界面代码
│   ├── datapreprocessing_tab.py  # 预处理界面
│   ├── mask_conversion_tab.py    # 转换界面
│   └── custom_labelme_tab.py     # 内嵌LabelMe界面
├── utils/                  # 通用工具
├── main.py                 # 程序启动入口
└── requirements.txt        # 依赖列表
```

## ⚠️ 常见问题

1.  **GeoPandas 导入错误**:
    *   如果启动时提示找不到 DLL 或模块，通常是 GDAL 环境问题。请尝试卸载 `geopandas` 和 `fiona`，然后使用 `conda install -c conda-forge geopandas` 重新安装。

2.  **地图瓦片无法下载**:
    *   请检查网络连接。部分地图服务（如 Google）可能需要代理才能访问。

3.  **LabelMe 模块未找到**:
    *   确保已运行 `pip install labelme`。GUI 依赖于系统环境中安装的 `labelme` 库来加载画布组件。
