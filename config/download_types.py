"""Download types configuration with URL management and detection."""

from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class DownloadType:
    """Download type configuration."""
    name: str  # 显示名称
    key: str  # 类型键值
    description: str  # 描述
    dtype: str  # 类型: "vector" 或 "tiles"
    url_options: List[str]  # URL 选项列表（瓦片下载）
    default_zoom: int = 18
    max_workers: int = 4
    per_thread_min_sleep: float = 0.5
    per_thread_max_sleep: float = 1.5
    batch_size: int = 3000
    batch_pause_min: float = 60.0
    batch_pause_max: float = 180.0
    request_timeout: float = 10.0  # 请求超时时间（秒）
    max_retries: int = 3  # 最大重试次数（更少）
    backoff_factor: float = 1.0  # 退避因子（减少重试延迟）
    
    def get_display_name(self) -> str:
        """Get display name with description."""
        return f"{self.name} - {self.description}"


# 下载类型定义
DOWNLOAD_TYPES = {
    "osm_vector": DownloadType(
        name="OpenStreetMap",
        key="osm_vector",
        description="开源地图数据 (矢量要素)",
        dtype="vector",
        url_options=[],  # 矢量数据不需要 URL
        default_zoom=18,
    ),
    "google": DownloadType(
        name="Google Satellite",
        key="google",
        description="Google 卫星影像 (高质量)",
        dtype="tiles",
        url_options=[
            "https://khms1.google.com/kh/v=994?x={x}&y={y}&z={z}",
            "https://khms1.google.com/kh/v=995?x={x}&y={y}&z={z}",
            "https://khms1.google.com/kh/v=1000?x={x}&y={y}&z={z}",
        ],
        default_zoom=18,
        max_workers=8,  # 增加并发线程
        per_thread_min_sleep=0.1,  # 减少线程延迟
        per_thread_max_sleep=0.5,  # 减少线程延迟
        request_timeout=8.0,  # 减少超时时间
        max_retries=2,  # 减少重试次数
        backoff_factor=1.0,  # 线性退避而不是指数
    ),
    "amap": DownloadType(
        name="Amap",
        key="amap",
        description="高德地图导航 (瓦片地图)",
        dtype="tiles",
        url_options=[
            "http://webrd01.is.autonavi.com/appmall/navi/v3/tile?x={x}&y={y}&z={z}",
        ],
        default_zoom=18,
        max_workers=6,  # 增加并发线程
        per_thread_min_sleep=0.1,  # 减少线程延迟
        per_thread_max_sleep=0.5,  # 减少线程延迟
        request_timeout=8.0,  # 减少超时时间
        max_retries=2,  # 减少重试次数
        backoff_factor=1.0,  # 线性退避
    ),
    "usgs": DownloadType(
        name="USGS",
        key="usgs",
        description="美国地质调查局卫星影像",
        dtype="tiles",
        url_options=[
            "https://basemap.nationalmap.gov/arcgis/rest/services/USGSSatelliteImagery/MapServer/tile/{z}/{y}/{x}",
        ],
        default_zoom=18,
        max_workers=8,  # 增加并发线程
        per_thread_min_sleep=0.1,  # 减少线程延迟
        per_thread_max_sleep=0.5,  # 减少线程延迟
        request_timeout=8.0,  # 减少超时时间
        max_retries=2,  # 减少重试次数
        backoff_factor=1.0,  # 线性退避
    ),
}

# 默认下载类型
DEFAULT_DOWNLOAD_TYPE = "osm_vector"
