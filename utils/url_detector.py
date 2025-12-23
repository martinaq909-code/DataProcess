"""URL detection utility for testing tile server accessibility."""

import logging
import requests
from typing import Optional, List

logger = logging.getLogger(__name__)


def detect_working_urls(url_options: List[str], timeout: int = 5) -> List[str]:
    """
    Detect which URLs from options are accessible.
    
    Args:
        url_options: List of URL templates to test
        timeout: Timeout for each request
        
    Returns:
        List of working URL templates
    """
    # 测试坐标
    test_x, test_y, test_z = 215945, 101416, 18
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.google.com/"
    }
    
    working_urls = []
    
    for url_template in url_options:
        try:
            # 替换占位符
            if "{x}" in url_template:
                url = url_template.format(x=test_x, y=test_y, z=test_z)
            else:
                # Skip unsupported URL formats
                continue
                
            logger.info(f"Testing URL: {url[:60]}...")
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            # 检查是否是有效的图片响应
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "").lower()
                content_size = len(response.content)
                
                # 判断是否是有效的图片（大小 > 100 字节）
                if ("image" in content_type or content_size > 100) and content_size < 1000000:  # < 1MB
                    logger.info(f"✓ Working URL found: {url_template[:50]}... (size: {content_size/1024:.1f}KB)")
                    working_urls.append(url_template)
                    
        except Exception as e:
            logger.debug(f"URL test failed: {str(e)[:50]}")
            continue
    
    if not working_urls:
        logger.warning("No working URLs found in the provided options")
    
    return working_urls












