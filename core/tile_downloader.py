import os
import math
import json
import time
import random
import logging
from typing import Tuple, Optional, Union, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.exceptions import RequestException
import mercantile
import geopandas as gpd
from shapely.geometry import box

logger = logging.getLogger(__name__)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def _make_session(user_agent: Optional[str] = None, proxies: Optional[dict] = None) -> requests.Session:
    """创建一个自定义的requests会话"""
    session = requests.Session()
    ua = user_agent or random.choice(USER_AGENTS)
    session.headers.update({
        "User-Agent": ua,
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/",
        "Accept-Language": "en-US,en;q=0.9",
    })
    if proxies:
        session.proxies.update(proxies)
    return session


def _load_checkpoint(path: str) -> dict:
    """加载断点续传检查点"""
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            logging.warning("无法加载 checkpoint，使用空进度。")
            return {}
    return {}


def _save_checkpoint(path: str, checkpoint: dict) -> None:
    """保存断点续传检查点"""
    tmp = path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _tile_to_filename(tile: mercantile.Tile) -> str:
    """将瓦片对象转换为文件名（使用quadkey）"""
    return f"{mercantile.quadkey(tile)}.png"


def _download_one(
    tile: mercantile.Tile,
    output_dir: str,
    url_template: Union[str, List[str]],
    session: requests.Session,
    max_retries: int,
    backoff_factor: float,
    request_timeout: float,
) -> Tuple[str, bool, str]:
    """下载单个瓦片"""
    filename = _tile_to_filename(tile)
    filepath = os.path.join(output_dir, filename)
    if os.path.exists(filepath):
        return filename, True, "exists"

    if isinstance(url_template, list):
        # Randomly shuffle URLs for load balancing and retry sequence
        urls = list(url_template)
        random.shuffle(urls)
    else:
        urls = [url_template]

    # Iterate through all available URLs
    last_error = "unknown_error"
    for url_fmt in urls:
        url = url_fmt.format(x=tile.x, y=tile.y, z=tile.z)
        
        attempt = 0
        while attempt <= max_retries:
            try:
                # Randomize UA occasionally on retries (every 2nd retry) to avoid fingerprinting
                if attempt > 0 and attempt % 2 == 0:
                    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

                resp = session.get(url, stream=True, timeout=request_timeout)
                if resp.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    return filename, True, "ok"
                elif resp.status_code in (403, 429):
                    wait = (backoff_factor ** attempt) + random.uniform(0.5, 2.0)
                    logging.warning(
                        f"Got {resp.status_code} for {url}. Backing off {wait:.1f}s (attempt {attempt}/{max_retries})"
                    )
                    time.sleep(wait)
                    last_error = f"status_{resp.status_code}"
                    
                    # If 403 Forbidden, sometimes it's IP ban or URL specific.
                    # If we have other URLs, maybe we should break early and try next URL?
                    # But let's stick to retry logic for now, unless max retries reached.
                elif 500 <= resp.status_code < 600:
                    wait = (backoff_factor ** attempt) + random.uniform(0.5, 2.0)
                    logging.warning(
                        f"Server error {resp.status_code} for {url}. Backing off {wait:.1f}s"
                    )
                    time.sleep(wait)
                    last_error = f"status_{resp.status_code}"
                else:
                    logging.error(f"Unexpected status {resp.status_code} for {url}")
                    last_error = f"status_{resp.status_code}"
                    # For 404 or other 4xx errors, might be better to try next URL immediately
                    if resp.status_code == 404:
                         break # Break retry loop to try next URL
                    
            except RequestException as e:
                wait = (backoff_factor ** attempt) + random.uniform(0.5, 2.0)
                logging.warning(
                    f"RequestException for {url}: {e}. Backing off {wait:.1f}s (attempt {attempt}/{max_retries})"
                )
                time.sleep(wait)
                last_error = f"error_{e}"
            except Exception as e:
                logging.exception(f"未知异常: {e}")
                last_error = f"error_{e}"
                break # Fatal error, try next URL or exit

            attempt += 1
        
        # If we are here, it means we exhausted retries for THIS url or broke out.
        # Continue to next URL in the list.
        logging.info(f"Failed with {url}, trying next available URL...")

    return filename, False, f"all_urls_failed: {last_error}"


def _worker_download_with_rate(
    tile: mercantile.Tile,
    outdir: str,
    url_template: Union[str, List[str]],
    session: requests.Session,
    max_retries: int,
    backoff_factor: float,
    min_sleep: float,
    max_sleep: float,
    request_timeout: float,
):
    """线程池工作函数，包含速率控制"""
    time.sleep(random.uniform(0, 0.5))
    result = _download_one(tile, outdir, url_template, session, max_retries, backoff_factor, request_timeout)
    time.sleep(random.uniform(min_sleep, max_sleep))
    return result


def _parse_bbox_input(bbox_input: Union[str, tuple, list]) -> Tuple[float, float, float, float]:
    """解析BBox输入（字符串或序列），返回 (west, south, east, north)"""
    if isinstance(bbox_input, str):
        parts = bbox_input.split(',')
        if len(parts) != 4:
            raise ValueError("BBox字符串格式应为: west,south,east,north")
        try:
            return tuple(float(p.strip()) for p in parts)
        except ValueError:
            raise ValueError("BBox坐标必须是数字")
    elif isinstance(bbox_input, (tuple, list)) and len(bbox_input) == 4:
        return tuple(float(x) for x in bbox_input)
    else:
        raise ValueError("BBox输入无效")


def _prepare_bounds_from_vector(vector_path: str) -> Tuple[float, float, float, float]:
    """从矢量文件读取边界，自动转换到WGS84"""
    try:
        gdf = gpd.read_file(vector_path)
    except Exception as e:
        raise ValueError(f"无法读取矢量文件: {e}")

    if gdf.empty:
        raise ValueError("矢量文件为空")

    # 获取原始CRS
    src_crs = gdf.crs
    if src_crs is None:
        logging.warning("矢量文件没有CRS信息，假设为WGS84（EPSG:4326）")
        src_crs = "EPSG:4326"

    # 如果不是WGS84，则转换
    if src_crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    bounds = gdf.total_bounds  # (minx, miny, maxx, maxy)
    return bounds[0], bounds[1], bounds[2], bounds[3]  # west, south, east, north


class TileDownloader:
    """瓦片下载器，支持从shapefile或bbox下载图像瓦片"""

    def __init__(
        self,
        url_template: Union[str, List[str]],
        output_base_dir: str,
        checkpoint_path: str = "tile_checkpoint.json",
        user_agent: Optional[str] = None,
        proxies: Optional[dict] = None,
        max_workers: int = 4,
        per_thread_min_sleep: float = 0.3,
        per_thread_max_sleep: float = 1.2,
        batch_size: int = 3000,
        batch_pause_min: float = 60.0,
        batch_pause_max: float = 180.0,
        max_retries: int = 6,
        backoff_factor: float = 1.5,
        request_timeout: float = 10.0,
    ):
        """
        初始化TileDownloader

        参数说明:
        - url_template: 瓦片 URL 模板，包含 {x} {y} {z}
        - output_base_dir: 瓦片保存根目录
        - checkpoint_path: 断点续传文件路径（json）
        - max_workers: 并发线程数（建议 3~6）
        - per_thread_min_sleep/max_sleep: 每个线程下载后随机 sleep 的区间（秒）
        - batch_size: 每个批次要下载的瓦片数量
        - batch_pause_min/max: 批次之间的随机休眠时间（秒）
        - max_retries: 单个请求的最大重试次数
        - backoff_factor: 重试退避因子
        - request_timeout: 单个请求超时时间（秒）
        - proxies: requests proxies dict
        """
        self.url_template = url_template
        self.output_base_dir = output_base_dir
        self.checkpoint_path = checkpoint_path
        self.max_workers = max_workers
        self.per_thread_min_sleep = per_thread_min_sleep
        self.per_thread_max_sleep = per_thread_max_sleep
        self.batch_size = batch_size
        self.batch_pause_min = batch_pause_min
        self.batch_pause_max = batch_pause_max
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.request_timeout = request_timeout
        self.proxies = proxies

        self.session = _make_session(user_agent=user_agent, proxies=proxies)
        self.checkpoint = _load_checkpoint(checkpoint_path)

    def _save_checkpoint(self):
        """保存检查点"""
        _save_checkpoint(self.checkpoint_path, self.checkpoint)

    def _download_tiles_impl(self, tiles: List[mercantile.Tile]):
        """实现瓦片下载的核心逻辑"""
        if not tiles:
            logging.error("No tiles to download.")
            return

        try:
            logging.info(f"Total tiles to download: {len(tiles)}")

            os.makedirs(self.output_base_dir, exist_ok=True)

            already_done = set(self.checkpoint.get("done", []))
            pending_tiles = [t for t in tiles if _tile_to_filename(t) not in already_done]

            logging.info(f"{len(pending_tiles)} tiles pending (after checkpoint filter).")

            n = len(pending_tiles)
            if n == 0:
                logging.info("No pending tiles to download.")
                return

            total_batches = math.ceil(n / self.batch_size)
            logging.info(f"Splitting into {total_batches} batch(es) with batch_size={self.batch_size}")

            for batch_idx in range(total_batches):
                s = batch_idx * self.batch_size
                e = min((batch_idx + 1) * self.batch_size, n)
                batch_tiles = pending_tiles[s:e]
                logging.info(f"Starting batch {batch_idx + 1}/{total_batches}: tiles {s + 1}..{e}")

                failures = []
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_tile = {}
                    for tile in batch_tiles:
                        future = executor.submit(
                            _worker_download_with_rate,
                            tile,
                            self.output_base_dir,
                            self.url_template,
                            self.session,
                            self.max_retries,
                            self.backoff_factor,
                            self.per_thread_min_sleep,
                            self.per_thread_max_sleep,
                            self.request_timeout,
                        )
                        future_to_tile[future] = tile

                    completed = 0
                    for future in as_completed(future_to_tile):
                        tile = future_to_tile[future]
                        try:
                            filename, success, msg = future.result()
                            if success:
                                done_list = self.checkpoint.setdefault("done", [])
                                if filename not in done_list:
                                    done_list.append(filename)
                            else:
                                failures.append((_tile_to_filename(tile), msg))
                        except Exception as exc:
                            failures.append((_tile_to_filename(tile), str(exc)))
                        
                        completed += 1
                        if completed % max(1, len(future_to_tile) // 10) == 0:
                            logging.info(f"Progress: {completed}/{len(future_to_tile)}")

                self._save_checkpoint()
                logging.info(
                    f"Batch {batch_idx + 1} finished. Success: {len(batch_tiles) - len(failures)}, Failures: {len(failures)}"
                )

                if failures:
                    fail_path = os.path.join(self.output_base_dir, f"failures_batch_{batch_idx+1}.json")
                    with open(fail_path, 'w', encoding='utf-8') as f:
                        json.dump(failures, f, ensure_ascii=False, indent=2)
                    logging.warning(f"Saved batch failures to {fail_path}")

                if batch_idx < total_batches - 1:
                    pause = random.uniform(self.batch_pause_min, self.batch_pause_max)
                    logging.info(f"Pausing {pause:.1f}s before next batch...")
                    time.sleep(pause)

            logging.info("All batches finished.")
            self._save_checkpoint()
        except Exception as e:
            logging.exception(f"Error in _download_tiles_impl: {e}")

    def download_tiles_from_bbox(self, bbox: Union[str, tuple, list], zoom: int):
        """从BBox下载瓦片"""
        west, south, east, north = _parse_bbox_input(bbox)
        tiles = list(mercantile.tiles(west, south, east, north, [zoom]))
        self._download_tiles_impl(tiles)

    def download_tiles_from_vector(self, vector_path: str, zoom: int):
        """从矢量文件下载瓦片"""
        west, south, east, north = _prepare_bounds_from_vector(vector_path)
        tiles = list(mercantile.tiles(west, south, east, north, [zoom]))
        self._download_tiles_impl(tiles)

    def download_tiles(self, input_range: Union[str, tuple, list], zoom: int, is_vector: bool = False):
        """
        统一的下载入口
        
        参数:
        - input_range: 矢量文件路径或BBox (west,south,east,north)
        - zoom: 缩放级别
        - is_vector: 是否为矢量输入
        """
        if is_vector:
            self.download_tiles_from_vector(input_range, zoom)
        else:
            self.download_tiles_from_bbox(input_range, zoom)


