import os
import shutil
import logging
import numpy as np
from PIL import Image
from pathlib import Path
from tqdm import tqdm

logger = logging.getLogger(__name__)

class TileFilter:
    """Filter tiles based on black pixel ratio."""

    def __init__(self, input_dir: str, output_dir: str, threshold_ratio: float = 1/16):
        """
        Initialize TileFilter.

        Args:
            input_dir: Directory containing input images.
            output_dir: Directory to save filtered images.
            threshold_ratio: Max ratio of black pixels allowed (default 1/16). 
                             Images with black pixel ratio > threshold will be skipped.
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.threshold_ratio = threshold_ratio

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
        
        for img_path in image_files:
            try:
                if self._check_image(img_path):
                    # Valid image, copy to output
                    dest_path = self.output_dir / img_path.name
                    shutil.copy2(img_path, dest_path)
                    copied += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Error processing {img_path}: {e}")
                if callback:
                    callback(f"错误: {img_path.name} - {e}")
            
            processed += 1
            if callback and processed % 10 == 0:
                callback(f"进度: {processed}/{total_files} (已复制: {copied}, 已跳过: {skipped})")
                
        if callback:
            callback(f"清洗完成！总计: {total_files}, 保留: {copied}, 剔除: {skipped}")
            
        return total_files, copied, skipped

    def _check_image(self, img_path: Path) -> bool:
        """
        Check if image meets the requirements.
        Returns True if image should be kept (black pixel ratio <= threshold).
        """
        try:
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
                    return False
                    
                ratio = black_pixels / total_pixels
                
                # Keep if ratio is less than or equal to threshold
                # User requirement: "无数据范围大于1/16的图片都清洗掉" 
                # means keep if ratio <= 1/16
                return ratio <= self.threshold_ratio
                
        except Exception as e:
            logger.error(f"Failed to check image {img_path}: {e}")
            return False
