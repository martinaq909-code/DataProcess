"""Tile compositor: compose tiles into large images and align with vector data."""
from __future__ import annotations

import logging
import math
import os
from pathlib import Path
import re
from typing import List, Optional, Tuple, Union

import cv2
import geopandas as gpd
import mercantile
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# 瓦片大小和输出大小配置
TILE_SIZE = 256  # 单个瓦片大小 (像素)
COMPOSITE_SIZE = 1024  # 输出大图大小 (像素)
TILES_PER_SIDE = COMPOSITE_SIZE // TILE_SIZE  # 每边需要多少个瓦片


class TileCompositor:
    """瓦片拼接和矢量数据对齐工具。"""

    def __init__(
        self,
        tiles_dir: Union[str, Path],
        zoom: Optional[int] = None,
        vector_path: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
        zoom_level: Optional[int] = None,
    ) -> None:
        """初始化瓦片拼接器。
        
        Args:
            tiles_dir: 瓦片所在目录
            zoom: 瓦片缩放级别（可选）
            vector_path: 矢量文件路径（可选）
            output_dir: 输出基目录（可选）
            zoom_level: GUI 传入的缩放级别别名（可选）
        """
        self.tiles_dir = Path(tiles_dir)
        self.zoom = zoom if zoom is not None else (zoom_level if zoom_level is not None else 18)
        self.vector_path = Path(vector_path) if vector_path else None
        self.output_dir = Path(output_dir) if output_dir else None
        self.tiles_dict = {}  # {quadkey: filepath}
        self._load_tiles()

    def _load_tiles(self) -> None:
        """加载目录中的所有瓦片。"""
        if not self.tiles_dir.exists():
            raise FileNotFoundError(f"Tiles directory not found: {self.tiles_dir}")
        
        # 查找所有 .png 和 .jpeg 文件（支持两种格式：quadkey 或数字 quadkey）
        for tile_file in list(self.tiles_dir.glob("*.png")) + list(self.tiles_dir.glob("*.jpeg")) + list(self.tiles_dir.glob("*.jpg")):
            quadkey_or_numeric = tile_file.stem
            # Strict validation: only accept digits 0-3
            if re.fullmatch(r"[0-3]+", quadkey_or_numeric):
                self.tiles_dict[quadkey_or_numeric] = tile_file
            else:
                # If file naming is different (e.g. some tools save as x_y_z), we might need logic here
                # But current downloader saves as quadkey.png, so we stick to it.
                pass
        
        logger.info(f"Loaded {len(self.tiles_dict)} tiles from {self.tiles_dir}")

    def _quadkey_to_tile(self, quadkey: str) -> mercantile.Tile:
        """将 quadkey 转换为 tile 对象。"""
        # Ensure input is a string of digits
        if not re.fullmatch(r"[0-3]+", quadkey):
             raise ValueError(f"Invalid quadkey format: {quadkey}")
        return mercantile.quadkey_to_tile(quadkey)
    
    def _tile_to_numeric_quadkey(self, tile: mercantile.Tile) -> str:
        """将 tile 转换为数字 quadkey 格式（用于查找本地文件）。
        
        数字 quadkey 是将标准 quadkey（0,1,2,3）直接连接成数字字符串。
        例如：标准 quadkey '0123' 转换为 '0123'，zoom+17会产生类似 '132100103330332100' 的字符串。
        """
        qk = mercantile.quadkey(tile)
        return qk  # 数字 quadkey 实际上就是标准 quadkey 的字符串形式

    def _tile_to_bbox(self, tile: mercantile.Tile) -> Tuple[float, float, float, float]:
        """将 tile 转换为 WGS84 bbox (west, south, east, north)。"""
        bbox = mercantile.bounds(tile)
        return bbox.west, bbox.south, bbox.east, bbox.north

    def _get_composite_tiles(self, start_quadkey: str) -> List[str]:
        """获取一个复合图所需的所有瓦片 quadkey。
        
        Args:
            start_quadkey: 复合图的起始瓦片 quadkey（可能是标准格式或数字格式）
            
        Returns:
            TILES_PER_SIDE × TILES_PER_SIDE 个瓦片的标识符列表
        """
        start_tile = self._quadkey_to_tile(start_quadkey)
        tiles = []
        
        for dy in range(TILES_PER_SIDE):
            for dx in range(TILES_PER_SIDE):
                x = start_tile.x + dx
                y = start_tile.y + dy
                tile = mercantile.Tile(x, y, self.zoom)
                # 生成该 tile 对应的数字 quadkey 用于查找本地文件
                numeric_qk = self._tile_to_numeric_quadkey(tile)
                tiles.append(numeric_qk)
        
        return tiles

    def _load_tile_image(self, quadkey: str) -> Optional[np.ndarray]:
        """加载单个瓦片图像。
        
        Args:
            quadkey: 瓦片 quadkey
            
        Returns:
            numpy 数组或 None
        """
        if quadkey not in self.tiles_dict:
            logger.warning(f"Tile not found: {quadkey}")
            return None
        
        try:
            img = Image.open(self.tiles_dict[quadkey])
            return np.array(img)
        except Exception as e:
            logger.error(f"Failed to load tile {quadkey}: {e}")
            return None

    def _composite_tiles_to_image(self, tile_quadkeys: List[str], start_x: int = 0, start_y: int = 0) -> np.ndarray:
        """将瓦片拼接成一张大图。
        
        Args:
            tile_quadkeys: 要拼接的瓦片 quadkey 列表
            start_x: 瓦片网格的起始 x 坐标（默认 0）
            start_y: 瓦片网格的起始 y 坐标（默认 0）
            
        Returns:
            拼接后的大图 (COMPOSITE_SIZE × COMPOSITE_SIZE × 3)
        """
        composite = np.zeros((COMPOSITE_SIZE, COMPOSITE_SIZE, 3), dtype=np.uint8)
        
        # 首先创建瓦片位置映射
        tile_map = {}  # {(x, y): quadkey}
        for quadkey in tile_quadkeys:
            tile = self._quadkey_to_tile(quadkey)
            tile_map[(tile.x, tile.y)] = quadkey
        
        # 现在按照正确的顺序遍历并拼接
        max_x = max(tile.x for tile in [self._quadkey_to_tile(qk) for qk in tile_quadkeys])
        max_y = max(tile.y for tile in [self._quadkey_to_tile(qk) for qk in tile_quadkeys])
        
        for abs_y in range(start_y, max_y + 1):
            for abs_x in range(start_x, max_x + 1):
                # 计算相对位置
                rel_y = abs_y - start_y
                rel_x = abs_x - start_x
                
                # 检查是否超出复合图范围
                if rel_y >= TILES_PER_SIDE or rel_x >= TILES_PER_SIDE:
                    continue
                
                # 获取该位置的瓦片
                quadkey = tile_map.get((abs_x, abs_y))
                
                if quadkey:
                    tile_img = self._load_tile_image(quadkey)
                    if tile_img is None:
                        logger.warning(f"Tile not found: {quadkey}")
                        tile_img = np.zeros((TILE_SIZE, TILE_SIZE, 3), dtype=np.uint8)
                else:
                    logger.warning(f"No tile at position ({abs_x}, {abs_y})")
                    tile_img = np.zeros((TILE_SIZE, TILE_SIZE, 3), dtype=np.uint8)
                
                # 处理灰度图
                if len(tile_img.shape) == 2:
                    tile_img = cv2.cvtColor(tile_img, cv2.COLOR_GRAY2BGR)
                elif tile_img.shape[2] == 4:  # RGBA
                    tile_img = cv2.cvtColor(tile_img, cv2.COLOR_RGBA2BGR)
                
                y_start = rel_y * TILE_SIZE
                y_end = y_start + TILE_SIZE
                x_start = rel_x * TILE_SIZE
                x_end = x_start + TILE_SIZE
                
                composite[y_start:y_end, x_start:x_end] = tile_img
        
        return composite

    def _create_vrt(self, output_image_path: Path, vrt_path: Path, bounds: Tuple[float, float, float, float]) -> None:
        """创建 VRT 文件 (使用 EPSG:3857 Web Mercator 投影)。
        
        Args:
            output_image_path: 输出图像路径
            vrt_path: 输出 VRT 文件路径
            bounds: EPSG:3857 边界 (west, south, east, north) in Meters
        """
        west, south, east, north = bounds
        
        pixel_width = (east - west) / COMPOSITE_SIZE
        pixel_height = (south - north) / COMPOSITE_SIZE  # 应该是负值 (south < north)
        
        # VRT 在 vrts/xxx.vrt，PNG 在 images/xxx.png，所以相对路径是 ../images/xxx.png
        relative_image_path = f"../images/{output_image_path.name}"
        
        vrt_content = f"""<VRTDataset rasterXSize="{COMPOSITE_SIZE}" rasterYSize="{COMPOSITE_SIZE}">
  <SRS dataAxisToSRSAxisMapping="1,2">PROJCS["WGS 84 / Pseudo-Mercator",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Mercator_1SP"],PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],EXTENSION["PROJ4","+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs"],AUTHORITY["EPSG","3857"]]</SRS>
  <GeoTransform>{west}, {pixel_width}, 0, {north}, 0, {pixel_height}</GeoTransform>
  <VRTRasterBand dataType="Byte" band="1">
    <ColorInterp>Red</ColorInterp>
    <SimpleSource>
      <SourceFilename relativeToVRT="1">{relative_image_path}</SourceFilename>
      <SourceBand>1</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="{COMPOSITE_SIZE}" ySize="{COMPOSITE_SIZE}"/>
      <DstRect xOff="0" yOff="0" xSize="{COMPOSITE_SIZE}" ySize="{COMPOSITE_SIZE}"/>
    </SimpleSource>
  </VRTRasterBand>
  <VRTRasterBand dataType="Byte" band="2">
    <ColorInterp>Green</ColorInterp>
    <SimpleSource>
      <SourceFilename relativeToVRT="1">{relative_image_path}</SourceFilename>
      <SourceBand>2</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="{COMPOSITE_SIZE}" ySize="{COMPOSITE_SIZE}"/>
      <DstRect xOff="0" yOff="0" xSize="{COMPOSITE_SIZE}" ySize="{COMPOSITE_SIZE}"/>
    </SimpleSource>
  </VRTRasterBand>
  <VRTRasterBand dataType="Byte" band="3">
    <ColorInterp>Blue</ColorInterp>
    <SimpleSource>
      <SourceFilename relativeToVRT="1">{relative_image_path}</SourceFilename>
      <SourceBand>3</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="{COMPOSITE_SIZE}" ySize="{COMPOSITE_SIZE}"/>
      <DstRect xOff="0" yOff="0" xSize="{COMPOSITE_SIZE}" ySize="{COMPOSITE_SIZE}"/>
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>"""
        
        with open(vrt_path, 'w') as f:
            f.write(vrt_content)
        
        logger.info(f"Created VRT file: {vrt_path}")

    def _coords_to_filename(self, west: float, south: float, east: float, north: float) -> str:
        """将坐标转换为文件名。
        
        Args:
            west, south, east, north: WGS84 坐标
            
        Returns:
            文件名 (不含扩展名)
        """
        return f"{west:.6f}_{south:.6f}_{east:.6f}_{north:.6f}"

    def composite_and_save(self, output_base_dir: Union[str, Path], tile_quadkeys: Optional[List[str]] = None) -> List[Tuple[Path, Path]]:
        """拼接瓦片并保存为大图。
        
        Args:
            output_base_dir: 输出基目录
            tile_quadkeys: 要处理的瓦片 quadkey 列表（如果为 None 则处理所有）
            
        Returns:
            (image_path, vrt_path) 元组列表
        """
        output_base_dir = Path(output_base_dir)
        output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        images_dir = output_base_dir / "images"
        vrts_dir = output_base_dir / "vrts"
        images_dir.mkdir(exist_ok=True)
        vrts_dir.mkdir(exist_ok=True)
        
        # 确定要处理的瓦片
        if tile_quadkeys is None:
            tile_quadkeys = list(self.tiles_dict.keys())
        
        if not tile_quadkeys:
            logger.warning("No tiles to process")
            return []
        
        results = []
        
        logger.info(f"✓ 开始拼接瓦片")
        logger.info(f"  加载的瓦片总数: {len(self.tiles_dict)}")
        logger.info(f"  缩放级别: {self.zoom}")
        logger.info(f"  复合图尺寸: {COMPOSITE_SIZE}x{COMPOSITE_SIZE} 像素 ({TILES_PER_SIDE}x{TILES_PER_SIDE} 瓦片)")
        
        # 首先找出所有瓦片的范围
        min_x, max_x = None, None
        min_y, max_y = None, None
        
        for quadkey in tile_quadkeys:
            tile = self._quadkey_to_tile(quadkey)
            if min_x is None or tile.x < min_x:
                min_x = tile.x
            if max_x is None or tile.x > max_x:
                max_x = tile.x
            if min_y is None or tile.y < min_y:
                min_y = tile.y
            if max_y is None or tile.y > max_y:
                max_y = tile.y
        
        logger.info(f"  瓦片范围: x=[{min_x}, {max_x}], y=[{min_y}, {max_y}]")
        
        # 现在按照实际范围从左上角开始拼接
        # 每个复合图使用 TILES_PER_SIDE×TILES_PER_SIDE 瓦片网格（当前为 4×4，即1024×1024像素）
        composite_idx = 0
        x = min_x
        while x <= max_x:
            y = min_y
            while y <= max_y:
                # 定义当前复合图的范围
                composite_end_x = min(x + TILES_PER_SIDE - 1, max_x)
                composite_end_y = min(y + TILES_PER_SIDE - 1, max_y)
                
                # 获取这个范围内的所有瓦片
                composite_tiles = []
                for qk in tile_quadkeys:
                    tile = self._quadkey_to_tile(qk)
                    if x <= tile.x <= composite_end_x and y <= tile.y <= composite_end_y:
                        composite_tiles.append(qk)
                
                if composite_tiles:
                    composite_idx += 1
                    logger.info(f"  [{composite_idx}] 正在拼接复合图 (x:[{x}, {composite_end_x}], y:[{y}, {composite_end_y}])...")
                    logger.info(f"       ├─ 加载 {len(composite_tiles)} 个瓦片")
                    
                    # 拼接
                    composite_img = self._composite_tiles_to_image(composite_tiles, x, y)
                    
                    # 计算边界（从起始瓦片到结束瓦片）
                    # start_tile 是左上 (min_x, min_y)，end_tile 是右下 (max_x, max_y)
                    start_tile_obj = mercantile.Tile(x, y, self.zoom)
                    start_bounds = self._tile_to_bbox(start_tile_obj)  # (west, south, east, north)
                    
                    end_tile = mercantile.Tile(composite_end_x, composite_end_y, self.zoom)
                    end_bounds = self._tile_to_bbox(end_tile)  # (west, south, east, north)
                    
                    # 正确的坐标应该是：
                    # - 西边界来自 start_tile (x最小)
                    # - 东边界来自 end_tile (x最大)  
                    # - 北边界来自 start_tile (y最小，对应较高纬度)
                    # - 南边界来自 end_tile (y最大，对应较低纬度)
                    west = start_bounds[0]   # 西: start 的西边
                    east = end_bounds[2]     # 东: end 的东边
                    north = start_bounds[3]  # 北: start 的北边（y小对应高纬度）
                    south = end_bounds[1]    # 南: end 的南边（y大对应低纬度）
                    filename = self._coords_to_filename(west, south, east, north)
                    
                    # 计算 EPSG:3857 (Web Mercator) 边界用于 VRT
                    # VRT 必须使用 EPSG:3857，因为原始瓦片像素就是 Mercator 投影
                    # 混合使用 WGS84 坐标和 Mercator 像素会导致图像变形
                    start_bounds_m = mercantile.xy_bounds(start_tile_obj)
                    end_bounds_m = mercantile.xy_bounds(end_tile)
                    west_m = start_bounds_m.left
                    east_m = end_bounds_m.right
                    north_m = start_bounds_m.top
                    south_m = end_bounds_m.bottom
                    
                    # 保存图像到 images 目录
                    image_path = images_dir / f"{filename}.png"
                    cv2.imwrite(str(image_path), composite_img)
                    logger.info(f"       ├─ 已保存图像: {filename}.png ({composite_img.shape})")
                    
                    # 保存 VRT 到 vrts 目录 (使用 Meters 坐标)
                    vrt_path = vrts_dir / f"{filename}.vrt"
                    self._create_vrt(image_path, vrt_path, (west_m, south_m, east_m, north_m))
                    logger.info(f"       └─ 已保存 VRT: {filename}.vrt")
                    
                    results.append((image_path, vrt_path))
                
                y = composite_end_y + 1
            
            x = composite_end_x + 1
        
        logger.info(f"✓ 瓦片拼接完成: 生成 {len(results)} 个复合图")
        return results

    def process_all(self, vector_path: Optional[Union[str, Path]] = None, output_dir: Optional[Union[str, Path]] = None) -> List[Tuple[Path, Path]]:
        """一次性执行拼接与矢量切割，兼容 GUI 期望的调用方式。"""
        vp = Path(vector_path) if vector_path else self.vector_path
        out = Path(output_dir) if output_dir else self.output_dir
        if out is None:
            raise ValueError("output_dir is required")
        results = self.composite_and_save(out)
        if results and vp is not None:
            try:
                self.clip_vector_data(str(vp), out)
            except Exception as e:
                logger.error(f"Failed to clip vector data: {e}")
        return results

    def clip_vector_data(self, vector_file: Union[str, Path], output_base_dir: Union[str, Path], 
                        composite_bounds: Optional[List[Tuple[float, float, float, float]]] = None) -> None:
        """按复合图边界切割矢量数据。
        
        Args:
            vector_file: 输入矢量文件
            output_base_dir: 输出基目录
            composite_bounds: 复合图边界列表 [(west, south, east, north), ...]
        """
        output_base_dir = Path(output_base_dir)
        vectors_dir = output_base_dir / "vectors"
        vectors_dir.mkdir(exist_ok=True)
        
        logger.info(f"✓ 开始切割矢量数据")
        logger.info(f"  输入文件: {vector_file}")
        gdf = gpd.read_file(vector_file)
        logger.info(f"  加载的要素数: {len(gdf)}")
        
        if composite_bounds is None:
            # 从瓦片列表推断边界 - 使用实际瓦片范围，每个复合图使用 TILES_PER_SIDE×TILES_PER_SIDE 瓦片网格
            logger.info(f"  正在从瓦片推断复合图边界...")
            composite_bounds = []
            
            # 首先找出所有瓦片的范围
            min_x, max_x = None, None
            min_y, max_y = None, None
            
            for quadkey in self.tiles_dict.keys():
                tile = self._quadkey_to_tile(quadkey)
                if min_x is None or tile.x < min_x:
                    min_x = tile.x
                if max_x is None or tile.x > max_x:
                    max_x = tile.x
                if min_y is None or tile.y < min_y:
                    min_y = tile.y
                if max_y is None or tile.y > max_y:
                    max_y = tile.y
            
            # 按照实际范围从左上角开始生成边界
            x = min_x
            while x <= max_x:
                y = min_y
                while y <= max_y:
                    composite_end_x = min(x + TILES_PER_SIDE - 1, max_x)
                    composite_end_y = min(y + TILES_PER_SIDE - 1, max_y)
                    
                    start_tile = mercantile.Tile(x, y, self.zoom)
                    start_bounds = self._tile_to_bbox(start_tile)
                    
                    end_tile = mercantile.Tile(composite_end_x, composite_end_y, self.zoom)
                    end_bounds = self._tile_to_bbox(end_tile)
                    
                    # 正确的坐标：西和北来自 start，东和南来自 end
                    west = start_bounds[0]   # 西: start 的西边
                    east = end_bounds[2]     # 东: end 的东边
                    north = start_bounds[3]  # 北: start 的北边（y小对应高纬度）
                    south = end_bounds[1]    # 南: end 的南边（y大对应低纬度）
                    composite_bounds.append((west, south, east, north))
                    
                    y = composite_end_y + 1
                
                x = composite_end_x + 1
            
            logger.info(f"  推断出 {len(composite_bounds)} 个复合图边界")
        
        logger.info(f"正在按 {len(composite_bounds)} 个边界进行切割...")
        clip_idx = 0
        for west, south, east, north in composite_bounds:
            clip_idx += 1
            filename = self._coords_to_filename(west, south, east, north)
            
            logger.info(f"  [{clip_idx}/{len(composite_bounds)}] 切割范围: {filename}")
            
            # 创建裁剪范围 (bbox)
            from shapely.geometry import box
            clip_box = box(west, south, east, north)
            
            # 裁剪
            clipped = gpd.clip(gdf, clip_box)
            
            if len(clipped) == 0:
                logger.warning(f"No vector features in {filename}")
                # 创建空的GeoJSON文件而不是跳过
                empty_gdf = gpd.GeoDataFrame(columns=gdf.columns, crs=gdf.crs, geometry=[])
                output_path = vectors_dir / f"{filename}.geojson"
                empty_gdf.to_file(output_path, driver="GeoJSON")
                logger.info(f"Created empty GeoJSON: {output_path}")
            else:
                # 保存
                output_path = vectors_dir / f"{filename}.geojson"
                clipped.to_file(output_path, driver="GeoJSON")
                logger.info(f"Clipped {len(clipped)} features to {output_path}")
