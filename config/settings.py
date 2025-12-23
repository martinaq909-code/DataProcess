"""
默认配置设置
"""
from pathlib import Path
import sys

# 项目根目录
if getattr(sys, "frozen", False):
    # 如果是打包后的 exe，根目录为 exe 所在目录
    PROJECT_ROOT = Path(sys.executable).parent
else:
    # 如果是源代码运行，根目录为当前文件的上上级目录
    PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录配置
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"

# OSM数据类型配置
OSM_DATA_TYPES = {
    "road": {
        "name": "道路",
        "tags": {"highway": True},
        "primary_tag": "highway",
        "road_types_only": [
            "motorway", "motorway_link", "trunk", "trunk_link",
            "primary", "primary_link", "secondary", "secondary_link",
            "tertiary", "tertiary_link", "unclassified", "residential",
            "service", "living_street"
        ],
    },
    "railway": {
        "name": "铁路",
        "tags": {"railway": True},
        "primary_tag": "railway",
    },
    "waterway": {
        "name": "水系",
        "tags": {"waterway": True},
        "primary_tag": "waterway",
    },
    "building": {
        "name": "建筑物",
        "tags": {"building": True},
        "primary_tag": "building",
    },
    "landuse": {
        "name": "土地利用",
        "tags": {"landuse": True},
        "primary_tag": "landuse",
    },
    "natural": {
        "name": "自然要素",
        "tags": {"natural": True},
        "primary_tag": "natural",
    },
    "boundary": {
        "name": "行政边界",
        "tags": {"boundary": True},
        "primary_tag": "boundary",
    },
}

# OSM下载默认配置
DEFAULT_OSM_CONFIG = {
    "max_tile_deg": 0.5,  # 单个请求的最大经纬度尺寸
    "buffer_deg": 0.01,  # 边界扩展（度）
    "data_types": ["road"],  # 下载的数据类型，可多选
    "cache_dir": str(CACHE_DIR),  # 缓存目录
}

# 瓦片下载默认配置
DEFAULT_TILE_CONFIG = {
    "max_workers": 4,  # 并发线程数
    "per_thread_min_sleep": 0.3,  # 每线程最小睡眠时间（秒）
    "per_thread_max_sleep": 1.2,  # 每线程最大睡眠时间（秒）
    "batch_size": 3000,  # 每个批次的瓦片数量
    "batch_pause_min": 60.0,  # 批次间最小暂停时间（秒）
    "batch_pause_max": 180.0,  # 批次间最大暂停时间（秒）
    "max_retries": 6,  # 单个请求最大重试次数
    "backoff_factor": 1.5,  # 重试退避因子
    "url_template": "https://khms1.google.com/kh/v=994?x={x}&y={y}&z={z}",  # 默认 Google 卫星影像 (v=994 可用)
    "zoom": 18,  # 默认缩放级别
}

# 常用瓦片 URL 模板
TILE_URL_PRESETS = {
    "Google Satellite v=994": "https://khms1.google.com/kh/v=994?x={x}&y={y}&z={z}",
    "Google Satellite v=995": "https://khms1.google.com/kh/v=995?x={x}&y={y}&z={z}",
    "Google Satellite v=1000": "https://khms1.google.com/kh/v=1000?x={x}&y={y}&z={z}",
    "USGS Satellite": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSSatelliteImagery/MapServer/tile/{z}/{y}/{x}",
    "Amap 导航地图": "http://webrd01.is.autonavi.com/appmall/navi/v3/tile?x={x}&y={y}&z={z}",
    "Sentinel-2 Satellite": "https://tiles.maps.eosinterpret.com/geoserver/ows?service=WMS&version=1.1.0&request=GetMap&layers=Sentinel2&bbox={west},{south},{east},{north}&width=256&height=256&srs=EPSG:4326&format=image/png",
    "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "OpenTopoMap": "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
    "CartoDB": "https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
}

# 输出格式配置
OUTPUT_FORMATS = {
    "geojson": "GeoJSON",
    "shp": "ESRI Shapefile",
    "gpkg": "GPKG",
}

# 默认配置字典
DEFAULT_CONFIG = {
    "data_dir": str(DATA_DIR),
    "input_dir": str(INPUT_DIR),
    "output_dir": str(OUTPUT_DIR),
    "cache_dir": str(CACHE_DIR),
    "osm": DEFAULT_OSM_CONFIG,
    "tile": DEFAULT_TILE_CONFIG,
    "output_formats": OUTPUT_FORMATS,
    "osm_data_types": OSM_DATA_TYPES,
}

