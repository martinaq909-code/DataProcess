import os
import shutil
import logging
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional
from tqdm import tqdm

logger = logging.getLogger(__name__)

class TileFilter:
    """Filter tiles based on black pixel ratio and optional road coverage."""

    def __init__(self, input_dir: str, output_dir: str, threshold_ratio: float = 1/16,
                 road_vector_path: Optional[str] = None, road_threshold: float = 0.5,
                 road_method: str = "length"):
        """
        Initialize TileFilter.

        Args:
            input_dir: Directory containing input images.
            output_dir: Directory to save filtered images.
            threshold_ratio: Max ratio of black pixels allowed (default 1/16). 
                             Images with black pixel ratio > threshold will be skipped.
            road_vector_path: Optional path to road vector file for road coverage filtering.
                              If provided, tiles with insufficient road coverage will be skipped.
            road_threshold: Minimum road coverage ratio required (default 0.5).
                            For 'length' method: road_length / diagonal_length >= threshold
            road_method: Road coverage calculation method ('length' or 'area').
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.threshold_ratio = threshold_ratio
        self.road_vector_path = road_vector_path
        self.road_threshold = road_threshold
        self.road_method = road_method
        self.road_analyzer = None
        
        # Initialize road coverage analyzer if vector path is provided
        if self.road_vector_path:
            try:
                from core.road_coverage_analyzer import RoadCoverageAnalyzer
                self.road_analyzer = RoadCoverageAnalyzer(self.road_vector_path, method=self.road_method)
                logger.info(f"Road coverage filtering enabled with threshold {self.road_threshold}")
            except Exception as e:
                logger.error(f"Failed to initialize road coverage analyzer: {e}")
                logger.warning("Road coverage filtering will be disabled")
                self.road_analyzer = None

    def process(self, callback=None):
        """
        Process images in input_dir and copy valid ones to output_dir.
        
        Args:
            callback: Optional callback function(msg) for logging/progress.
        """
        if not self.input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {self.input_dir}")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all images
        extensions = ['*.png', '*.jpg', '*.jpeg', '*.tif', '*.tiff']
        image_files = []
        for ext in extensions:
            image_files.extend(list(self.input_dir.glob(ext)))
            
        total_files = len(image_files)
        if callback:
            callback(f"找到 {total_files} 个图片文件，开始清洗...")
            
        processed = 0
        copied = 0
        skipped = 0
        skipped_black = 0  # Skipped due to black pixels
        skipped_road = 0   # Skipped due to insufficient road coverage
        
        for img_path in image_files:
            try:
                result, reason = self._check_image(img_path)
                if result:
                    # Valid image, copy to output
                    dest_path = self.output_dir / img_path.name
                    shutil.copy2(img_path, dest_path)
                    copied += 1
                else:
                    skipped += 1
                    if reason == 'black':
                        skipped_black += 1
                    elif reason == 'road':
                        skipped_road += 1
            except Exception as e:
                logger.error(f"Error processing {img_path}: {e}")
                if callback:
                    callback(f"错误: {img_path.name} - {e}")
            
            processed += 1
            if callback and processed % 10 == 0:
                if self.road_analyzer:
                    callback(f"进度: {processed}/{total_files} (保留: {copied}, 黑边过滤: {skipped_black}, 道路过滤: {skipped_road})")
                else:
                    callback(f"进度: {processed}/{total_files} (已复制: {copied}, 已跳过: {skipped})")
                
        if callback:
            if self.road_analyzer:
                callback(f"清洗完成！总计: {total_files}, 保留: {copied}, 剔除: {skipped} (黑边: {skipped_black}, 道路不足: {skipped_road})")
            else:
                callback(f"清洗完成！总计: {total_files}, 保留: {copied}, 剔除: {skipped}")
            
        return total_files, copied, skipped

    def _check_image(self, img_path: Path) -> tuple[bool, str]:
        """
        Check if image meets the requirements.
        
        Returns:
            (keep: bool, reason: str) - True if image should be kept, and reason for rejection if False.
            Possible reasons: 'black' (too many black pixels), 'road' (insufficient road coverage)
        """
        try:
            # Step 1: Check black pixel ratio
            with Image.open(img_path) as img:
                # Convert to numpy array
                # Handle different modes
                if img.mode != 'RGB' and img.mode != 'L':
                    img = img.convert('RGB')
                
                arr = np.array(img)
                
                # Calculate black pixels (assuming [0,0,0] is black)
                # For RGB: check if all channels are 0
                # For Grayscale: check if pixel is 0
                if len(arr.shape) == 3: # RGB/RGBA
                    # Check RGB channels only (ignore alpha if present)
                    is_black = np.all(arr[:, :, :3] == 0, axis=2)
                else: # Grayscale
                    is_black = (arr == 0)
                
                black_pixels = np.sum(is_black)
                total_pixels = arr.shape[0] * arr.shape[1]
                
                if total_pixels == 0:
                    return (False, 'black')
                    
                ratio = black_pixels / total_pixels
                
                # Keep if ratio is less than or equal to threshold
                # User requirement: "无数据范围大于1/16的图片都清洗掉" 
                # means keep if ratio <= 1/16
                if ratio > self.threshold_ratio:
                    return (False, 'black')
            
            # Step 2: Check road coverage (if enabled)
            if self.road_analyzer:
                from core.road_coverage_analyzer import RoadCoverageAnalyzer
                
                # Parse filename to get geographic bounds
                bbox = RoadCoverageAnalyzer.parse_filename(img_path.name)
                if bbox is None:
                    logger.warning(f"Could not parse filename for road analysis: {img_path.name}")
                    # If we can't parse filename, allow the image (fail safe)
                    return (True, '')
                
                # Calculate road coverage
                coverage = self.road_analyzer.calculate_coverage(bbox)
                
                # Check if coverage meets threshold
                if coverage < self.road_threshold:
                    logger.debug(f"Skipping {img_path.name}: road coverage {coverage:.4f} < {self.road_threshold}")
                    return (False, 'road')
            
            # If all checks pass, keep the image
            return (True, '')
                
        except Exception as e:
            logger.error(f"Failed to check image {img_path}: {e}")
            return (False, 'error')
