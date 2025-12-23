
import os
import shutil
import unittest
import logging
import cv2
import numpy as np
import mercantile
from pathlib import Path

# Import our modules
from core.tile_downloader import TileDownloader
from core.tile_compositor import TileCompositor
from core.logger import setup_logging
from config.download_types import DOWNLOAD_TYPES

# Initialize logging
setup_logging()
logger = logging.getLogger("IntegrationTest")

class TestIntegration(unittest.TestCase):
    """
    End-to-End Integration Test:
    1. Download real tiles (small area)
    2. Composite them into a large image
    3. Verify VRT and Image correctness
    """
    
    def setUp(self):
        self.test_dir = Path("test_integration_output")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)
        
        # Define a very small area (e.g., Forbidden City corner)
        # Zoom 17 to get a few tiles but not too many
        self.bbox = (116.390, 39.915, 116.394, 39.918)
        self.zoom = 17
        
    def tearDown(self):
        # Cleanup
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_download_and_composite(self):
        logger.info("=== Starting Integration Test ===")
        
        # --- Step 1: Download (using Amap as it's stable) ---
        tiles_dir = self.test_dir / "tiles"
        logger.info(f"1. Downloading tiles to {tiles_dir}...")
        
        dt = DOWNLOAD_TYPES["amap"]
        downloader = TileDownloader(
            url_template=dt.url_options, # Use the list for failover testing
            output_base_dir=str(tiles_dir),
            max_workers=4,
            max_retries=3
        )
        
        # Download
        downloader.download_tiles_from_bbox(self.bbox, self.zoom)
        
        # Verify download
        downloaded_files = list(tiles_dir.glob("*.png"))
        self.assertTrue(len(downloaded_files) > 0, "Should have downloaded at least one tile")
        logger.info(f"   Downloaded {len(downloaded_files)} tiles.")

        # --- Step 2: Composite ---
        output_dir = self.test_dir / "output"
        logger.info(f"2. Compositing tiles to {output_dir}...")
        
        compositor = TileCompositor(
            tiles_dir=tiles_dir,
            zoom=self.zoom,
            output_dir=output_dir
        )
        
        results = compositor.composite_and_save(output_dir)
        
        # Verify composite results
        self.assertTrue(len(results) > 0, "Should have generated at least one composite image")
        
        image_path, vrt_path = results[0]
        logger.info(f"   Generated image: {image_path}")
        logger.info(f"   Generated VRT: {vrt_path}")
        
        # --- Step 3: Verify Image Content ---
        self.assertTrue(image_path.exists(), "Composite image file must exist")
        img = cv2.imread(str(image_path))
        self.assertIsNotNone(img, "Composite image should be readable")
        self.assertEqual(img.shape[0], 1024, "Image height should be 1024 (4 tiles * 256)")
        self.assertEqual(img.shape[1], 1024, "Image width should be 1024")
        
        # Check if it's not all black (Amap usually has content)
        # Note: If network failed completely, it might be black, but we asserted download > 0
        non_zero_pixels = np.count_nonzero(img)
        self.assertTrue(non_zero_pixels > 0, "Composite image should not be completely empty/black")
        
        # --- Step 4: Verify VRT Content (Projection Fix Check) ---
        self.assertTrue(vrt_path.exists(), "VRT file must exist")
        with open(vrt_path, 'r', encoding='utf-8') as f:
            vrt_content = f.read()
            
        # Check for EPSG:3857 (Web Mercator)
        self.assertIn('EPSG","3857"', vrt_content, "VRT should use EPSG:3857 projection")
        self.assertIn('PROJCS["WGS 84 / Pseudo-Mercator"', vrt_content, "VRT should define Pseudo-Mercator")
        
        logger.info("=== Integration Test Passed Successfully ===")

if __name__ == "__main__":
    unittest.main()
