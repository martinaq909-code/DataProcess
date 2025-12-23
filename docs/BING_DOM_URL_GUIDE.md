# Bing Maps DOM URL 解析与下载指南

## URL格式解析

### 基础URL格式
```
https://t.ssl.ak.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?n=z&g=9649
```

### URL组成部分

1. **基础域名**: `https://t.ssl.ak.tiles.virtualearth.net/tiles/`
   - Bing Maps瓦片服务器地址

2. **瓦片类型标识**:
   - `a{quadkey}` - **Aerial** (航拍/卫星影像) - **DOM数据**
   - `r{quadkey}` - Road (道路地图)
   - `h{quadkey}` - Hybrid (混合模式)

3. **Quadkey (四叉树键值)**:
   - 用于唯一标识瓦片位置的字符串
   - 由0、1、2、3四个数字组成
   - 长度等于缩放级别（zoom level）

4. **文件格式**: `.jpeg`

5. **URL参数**:
   - `n=z` - 可能是某种标识参数
   - `g=9649` - 可能是版本号或密钥

## Quadkey计算

### 从经纬度到Quadkey

```python
from core.bing_dom_downloader import deg2num, tile_to_quadkey

# 1. 经纬度转瓦片坐标
lat, lon = 39.9042, 116.4074  # 北京天安门
zoom = 19
tile_x, tile_y = deg2num(lat, lon, zoom)

# 2. 瓦片坐标转Quadkey
quadkey = tile_to_quadkey(tile_x, tile_y, zoom)
# 结果: "1321001211000113030"

# 3. 构建完整URL
url = f"https://t.ssl.ak.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?n=z&g=9649"
```

### Quadkey示例

| 位置 | 经纬度 | Zoom | Tile坐标 | Quadkey |
|------|--------|------|----------|---------|
| 北京天安门 | 39.9042, 116.4074 | 19 | (431674, 198666) | 1321001211000113030 |
| 上海外滩 | 31.2304, 121.4737 | 19 | (442123, 211234) | ... |

## 下载方法

### 方法1：使用BingDOMDownloader类

```python
from core.bing_dom_downloader import BingDOMDownloader

# 创建下载器
downloader = BingDOMDownloader(
    base_url="https://t.ssl.ak.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?n=z&g=9649",
    output_dir="data/output/bing_dom_tiles"
)

# 下载单个瓦片
img = downloader.download_tile(
    tile_x=431674,
    tile_y=198666,
    zoom=19,
    save=True
)

# 下载边界框内的所有瓦片
downloader.download_bbox(
    west=116.6,    # 西边界（经度）
    south=39.9,    # 南边界（纬度）
    east=116.7,    # 东边界（经度）
    north=40.0,    # 北边界（纬度）
    zoom=19        # 缩放级别
)
```

### 方法2：直接下载URL

```python
import requests
from PIL import Image
import io

quadkey = "1321001211000113030"
url = f"https://t.ssl.ak.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?n=z&g=9649"

response = requests.get(url)
img = Image.open(io.BytesIO(response.content))
img.save("tile.jpeg")
```

## 缩放级别说明

| Zoom级别 | 地面分辨率（米/像素） | 说明 |
|----------|---------------------|------|
| 18 | ~0.6 | 城市级别 |
| 19 | ~0.3 | **推荐用于道路提取** |
| 20 | ~0.15 | 高精度 |
| 21 | ~0.075 | 超高精度 |

## 数据特点

### DOM (Digital Orthophoto Map) 优势

1. **正射校正**: 消除了地形起伏和透视变形
2. **几何精度高**: 适合精确测量和提取
3. **方向准确**: 道路方向不受透视影响
4. **适合道路提取**: 比普通卫星影像更适合LSOH算法

### 与普通卫星影像对比

| 特性 | DOM | 普通卫星影像 |
|------|-----|------------|
| 透视变形 | 无 | 有 |
| 地形校正 | 已校正 | 未校正 |
| 方向精度 | 高 | 受透视影响 |
| 道路提取 | 适合 | 需要更宽松参数 |

## 批量下载示例

```python
from core.bing_dom_downloader import BingDOMDownloader

# 下载test_composited_10数据对应的DOM影像
downloader = BingDOMDownloader(
    output_dir="data/output/bing_dom_tiles"
)

# 从test_composited_10的边界框下载
# 例如：116.636353_39.947121_116.639099_39.949227
west, south = 116.636353, 39.947121
east, north = 116.639099, 39.949227
zoom = 19

downloader.download_bbox(west, south, east, north, zoom)
```

## 注意事项

1. **请求频率**: 建议添加延迟，避免被服务器限制
2. **缓存**: 已下载的瓦片会自动跳过
3. **重试机制**: 内置3次重试机制
4. **User-Agent**: 已设置合适的User-Agent
5. **版权**: 注意Bing Maps的使用条款和版权

## 与现有流程集成

下载DOM后，可以替换现有的Google卫星影像，用于道路提取：

```python
# 1. 下载Bing DOM瓦片
downloader = BingDOMDownloader(output_dir="data/output/bing_dom_tiles")
downloader.download_bbox(west, south, east, north, zoom=19)

# 2. 使用TileCompositor拼接（需要适配Bing格式）
from core.tile_compositor import TileCompositor
compositor = TileCompositor(...)

# 3. 使用DOM影像进行道路提取（方向会更准确）
from core.road_extraction_lsoh import RoadExtractorLSOH
extractor = RoadExtractorLSOH(
    image_path="dom_composite.png",
    vector_path="roads.geojson",
    zoom=19
)
```

## 文件结构

下载后的文件结构：
```
data/output/bing_dom_tiles/
├── 19_431674_198666.jpeg
├── 19_431675_198666.jpeg
├── 19_431674_198667.jpeg
└── ...
```

文件名格式：`{zoom}_{tile_x}_{tile_y}.jpeg`





