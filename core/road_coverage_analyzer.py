"""Road coverage analyzer for filtering tiles by road density."""

import re
import logging
from pathlib import Path
from typing import Tuple, Optional
import geopandas as gpd
from shapely.geometry import box
from pyproj import Geod

logger = logging.getLogger(__name__)


class RoadCoverageAnalyzer:
    """分析拼接瓦片中的道路覆盖率"""
    
    def __init__(self, vector_path: str, method: str = "length"):
        """
        初始化道路覆盖率分析器
        
        Args:
            vector_path: 道路矢量文件路径 (GeoJSON, Shapefile等)
            method: 计算方法 ("length" 或 "area")
        """
        self.vector_path = Path(vector_path)
        self.method = method
        self.gdf = None
        self._load_vector()
    
    def _load_vector(self):
        """加载矢量数据并转换为 WGS84"""
        if not self.vector_path.exists():
            raise FileNotFoundError(f"Vector file not found: {self.vector_path}")
            
        logger.info(f"Loading vector file: {self.vector_path}")
        self.gdf = gpd.read_file(self.vector_path)
        
        # 统一转换为 WGS84 (EPSG:4326)
        if self.gdf.crs is None:
            logger.warning("Vector file has no CRS, assuming EPSG:4326")
            self.gdf.set_crs("EPSG:4326", inplace=True)
        elif self.gdf.crs.to_epsg() != 4326:
            logger.info(f"Converting from {self.gdf.crs} to EPSG:4326")
            self.gdf = self.gdf.to_crs("EPSG:4326")
        
        logger.info(f"Loaded {len(self.gdf)} road features")
    
    @staticmethod
    def parse_filename(filename: str) -> Optional[Tuple[float, float, float, float]]:
        """
        从文件名解析地理范围
        
        Args:
            filename: 文件名（可含扩展名）
        
        Returns:
            (west, south, east, north) 或 None
        
        Examples:
            >>> RoadCoverageAnalyzer.parse_filename("120.123456_30.123456_120.234567_30.234567.png")
            (120.123456, 30.123456, 120.234567, 30.234567)
            >>> RoadCoverageAnalyzer.parse_filename("-120.123456_-30.123456_-120.234567_-30.234567.png")
            (-120.123456, -30.123456, -120.234567, -30.234567)
        """
        pattern = r"(-?\d+\.\d+)_(-?\d+\.\d+)_(-?\d+\.\d+)_(-?\d+\.\d+)"
        match = re.search(pattern, filename)
        if match:
            west, south, east, north = map(float, match.groups())
            return (west, south, east, north)
        return None
    
    def calculate_coverage(self, bbox: Tuple[float, float, float, float]) -> float:
        """
        计算指定范围内的道路覆盖率
        
        Args:
            bbox: (west, south, east, north) WGS84 坐标
        
        Returns:
            覆盖率 (0.0 ~ 1.0+)，对于 length 方法，值可能大于 1.0
        """
        west, south, east, north = bbox
        
        # 创建裁剪框
        clip_box = box(west, south, east, north)
        
        # 裁剪矢量数据
        try:
            clipped = gpd.clip(self.gdf, clip_box)
        except Exception as e:
            logger.error(f"Failed to clip vector data for bbox {bbox}: {e}")
            return 0.0
        
        if len(clipped) == 0:
            logger.debug(f"No road features found in bbox {bbox}")
            return 0.0
        
        if self.method == "length":
            return self._calculate_length_ratio(clipped, bbox)
        elif self.method == "area":
            return self._calculate_area_ratio(clipped, bbox)
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def _calculate_length_ratio(self, clipped_gdf: gpd.GeoDataFrame, 
                                 bbox: Tuple[float, float, float, float]) -> float:
        """
        计算道路长度占比
        
        Args:
            clipped_gdf: 裁剪后的道路矢量数据
            bbox: (west, south, east, north)
        
        Returns:
            长度占比（总长度 / 对角线长度）
        """
        geod = Geod(ellps="WGS84")
        
        # 计算道路总长度（米）
        total_length = 0.0
        for geom in clipped_gdf.geometry:
            if geom is None or geom.is_empty:
                continue
                
            if geom.geom_type == 'LineString':
                length = geod.geometry_length(geom)
                total_length += length
            elif geom.geom_type == 'MultiLineString':
                for line in geom.geoms:
                    length = geod.geometry_length(line)
                    total_length += length
            # 忽略其他几何类型（Point, Polygon等）
        
        # 计算瓦片对角线长度作为参考（米）
        west, south, east, north = bbox
        diagonal_length = geod.inv(west, south, east, north)[2]  # 大圆距离
        
        if diagonal_length == 0:
            logger.warning(f"Diagonal length is 0 for bbox {bbox}")
            return 0.0
        
        ratio = total_length / diagonal_length
        logger.debug(f"Road length: {total_length:.2f}m, Diagonal: {diagonal_length:.2f}m, Ratio: {ratio:.4f}")
        return ratio
    
    def _calculate_area_ratio(self, clipped_gdf: gpd.GeoDataFrame,
                               bbox: Tuple[float, float, float, float]) -> float:
        """
        计算道路缓冲区面积占比
        
        Args:
            clipped_gdf: 裁剪后的道路矢量数据
            bbox: (west, south, east, north)
        
        Returns:
            面积占比（缓冲区面积 / 瓦片面积）
        """
        try:
            # 转换到适合面积计算的投影坐标系（Web Mercator）
            clipped_proj = clipped_gdf.to_crs("EPSG:3857")
            
            # 创建 10 米缓冲区
            buffered = clipped_proj.buffer(10)
            total_area = buffered.unary_union.area  # 平方米
            
            # 计算瓦片面积
            west, south, east, north = bbox
            tile_box = box(west, south, east, north)
            tile_gdf = gpd.GeoDataFrame([1], geometry=[tile_box], crs="EPSG:4326")
            tile_proj = tile_gdf.to_crs("EPSG:3857")
            tile_area = tile_proj.geometry[0].area  # 平方米
            
            if tile_area == 0:
                logger.warning(f"Tile area is 0 for bbox {bbox}")
                return 0.0
            
            ratio = total_area / tile_area
            logger.debug(f"Road area: {total_area:.2f}m², Tile area: {tile_area:.2f}m², Ratio: {ratio:.4f}")
            return ratio
        except Exception as e:
            logger.error(f"Failed to calculate area ratio for bbox {bbox}: {e}")
            return 0.0
