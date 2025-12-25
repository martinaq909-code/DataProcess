"""OSM data cleaning and filtering utilities."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Set, Union

import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)


class OSMCleaner:
    """OSM data cleaning and filtering tool."""
    
    # 主干道类型定义（排除以下类型）
    NON_TRUNK_TYPES = {
        "footway",
        "cycleway", 
        "path",
        "service",
        "pedestrian",
        "track",
        "bridleway",
    }
    
    # 地下道路识别
    UNDERGROUND_INDICATORS = {
        "tunnel",  # tunnel=yes 表示地下
    }
    
    # 需要过滤的层数值（负值通常表示地下设施）
    FILTERED_LAYERS = {-1}  # layer=-1 表示地下一层

    def __init__(self, osm_file: Union[str, Path]) -> None:
        """Initialize OSM cleaner with a GeoJSON file.
        
        Args:
            osm_file: Path to OSM GeoJSON file
        """
        self.osm_file = Path(osm_file)
        self.gdf: Optional[gpd.GeoDataFrame] = None
        self.highway_types: Set[str] = set()
        self.trunk_roads: Optional[gpd.GeoDataFrame] = None
        self._load_data()

    def _load_data(self) -> None:
        """Load OSM data from file."""
        if not self.osm_file.exists():
            raise FileNotFoundError(f"OSM file not found: {self.osm_file}")
        
        self.gdf = gpd.read_file(self.osm_file)
        logger.info(f"Loaded {len(self.gdf)} features from {self.osm_file}")
        
        # Detect highway types
        if "highway" in self.gdf.columns:
            self.highway_types = set(self.gdf["highway"].dropna().unique())
            logger.info(f"Found {len(self.highway_types)} highway types")

    def get_highway_types(self) -> List[str]:
        """Get all unique highway types in the dataset.
        
        Returns:
            Sorted list of highway types
        """
        return sorted(list(self.highway_types))

    def get_column_info(self) -> dict:
        """Get information about all columns in the dataset.
        
        Returns:
            Dict with column names and their data types
        """
        if self.gdf is None:
            return {}
        
        info = {}
        for col in self.gdf.columns:
            info[col] = {
                "dtype": str(self.gdf[col].dtype),
                "non_null_count": self.gdf[col].notna().sum(),
                "null_count": self.gdf[col].isna().sum(),
            }
        return info

    def filter_by_highway_types(self, keep_types: List[str]) -> gpd.GeoDataFrame:
        """Filter OSM data to keep only specified highway types.
        
        Args:
            keep_types: List of highway types to keep
            
        Returns:
            Filtered GeoDataFrame
        """
        if self.gdf is None:
            raise ValueError("No data loaded")
        
        if "highway" not in self.gdf.columns:
            raise ValueError("'highway' column not found")
        
        filtered = self.gdf[self.gdf["highway"].isin(keep_types)].copy()
        logger.info(f"Filtered to {len(filtered)} features with highway types: {keep_types}")
        return filtered

    def remove_underground_roads(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Remove underground roads from dataset.
        
        Args:
            gdf: GeoDataFrame to filter
            
        Returns:
            Filtered GeoDataFrame
        """
        if "tunnel" not in gdf.columns:
            return gdf.copy()
        
        # Remove roads marked as tunnel (tunnel != yes)
        before_count = len(gdf)
        filtered = gdf[gdf["tunnel"] != "yes"].copy()
        removed_count = before_count - len(filtered)
        logger.info(f"Removed {removed_count} underground roads (tunnel=yes)")
        return filtered
    
    def remove_negative_layer_roads(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Remove roads with negative layer values from dataset.
        
        Args:
            gdf: GeoDataFrame to filter
            
        Returns:
            Filtered GeoDataFrame
        """
        if "layer" not in gdf.columns:
            return gdf.copy()
        
        gdf_copy = gdf.copy()

        # 数值解析：支持 int/float 类型和字符串数值
        gdf_copy["layer_numeric"] = pd.to_numeric(gdf_copy["layer"], errors="coerce")
        numeric_mask = gdf_copy["layer_numeric"].isin(self.FILTERED_LAYERS)

        # 文本解析：处理诸如 "-1", "-1;0", "-1 | 0" 等形式
        layer_str = gdf_copy["layer"].astype(str).str.strip()
        text_mask = layer_str.str.contains(r"(?<!\d)-1(?!\d)", regex=True, na=False)

        combined_mask = numeric_mask | text_mask

        before_count = len(gdf_copy)
        filtered = gdf_copy[~combined_mask].copy()
        filtered = filtered.drop(columns=["layer_numeric"])
        removed_count = before_count - len(filtered)

        logger.info(
            "Removed %d roads with layer value containing -1 (numeric/text matches)",
            removed_count,
        )
        return filtered

    def extract_trunk_roads(self, callback=None) -> gpd.GeoDataFrame:
        """Extract trunk roads (main roads) by removing non-trunk types, underground roads, and negative layer roads.
        
        Args:
            callback: Optional callback function(msg) for progress reporting.
            
        Returns:
            GeoDataFrame with trunk roads only
        """
        if self.gdf is None:
            raise ValueError("No data loaded")
        
        if "highway" not in self.gdf.columns:
            raise ValueError("'highway' column not found")
        
        msg = f"✓ 开始提取主干道"
        logger.info(msg)
        if callback:
            callback(msg)
            
        msg = f"  原始要素数: {len(self.gdf)}"
        logger.info(msg)
        if callback:
            callback(msg)
        
        # Remove non-trunk types
        before_type_filter = len(self.gdf)
        trunk_roads = self.gdf[~self.gdf["highway"].isin(self.NON_TRUNK_TYPES)].copy()
        removed_by_type = before_type_filter - len(trunk_roads)
        
        msg = f"  移除非主干道类型后: {len(trunk_roads)} (移除 {removed_by_type} 个)"
        logger.info(msg)
        if callback:
            callback(msg)
        
        # Remove underground roads
        trunk_roads = self.remove_underground_roads(trunk_roads)
        msg = f"  移除地下道路后: {len(trunk_roads)}"
        logger.info(msg)
        if callback:
            callback(msg)
        
        # Remove roads with negative layer values (e.g., layer=-1)
        trunk_roads = self.remove_negative_layer_roads(trunk_roads)
        msg = f"  移除负层数值道路后: {len(trunk_roads)}"
        logger.info(msg)
        if callback:
            callback(msg)
        
        msg = f"✓ 主干道提取完成: 保留 {len(trunk_roads)} 个要素"
        logger.info(msg)
        if callback:
            callback(msg)
            
        self.trunk_roads = trunk_roads
        return trunk_roads

    def keep_columns(self, gdf: gpd.GeoDataFrame, columns: List[str]) -> gpd.GeoDataFrame:
        """Keep only specified columns in the dataset.
        
        Args:
            gdf: GeoDataFrame to process
            columns: List of column names to keep
            
        Returns:
            GeoDataFrame with only specified columns
        """
        # Always keep geometry column
        if "geometry" not in columns:
            columns = columns + ["geometry"]
        
        available_cols = [col for col in columns if col in gdf.columns]
        missing_cols = set(columns) - set(available_cols)
        
        if missing_cols:
            logger.warning(f"Columns not found: {missing_cols}")
        
        result = gdf[available_cols].copy()
        logger.info(f"Kept {len(available_cols)} columns: {available_cols}")
        return result

    def save_data(self, gdf: gpd.GeoDataFrame, output_path: Union[str, Path], driver: str = "GeoJSON") -> None:
        """Save GeoDataFrame to file.
        
        Args:
            gdf: GeoDataFrame to save
            output_path: Output file path
            driver: Output driver (default: GeoJSON)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"正在保存数据...")
        logger.info(f"  输出路径: {output_path}")
        logger.info(f"  要素数: {len(gdf)}")
        gdf.to_file(output_path, driver=driver)
        logger.info(f"✓ 数据保存完成")

    def save(self, output_path: Union[str, Path], driver: str = "GeoJSON") -> None:
        """Save cleaned trunk roads currently stored in the cleaner.
        Raises:
            ValueError: if trunk roads have not been extracted
        """
        if self.trunk_roads is None:
            raise ValueError("No trunk roads to save. Call extract_trunk_roads() first.")
        self.save_data(self.trunk_roads, output_path, driver=driver)
