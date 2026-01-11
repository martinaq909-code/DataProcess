import os
import math
import json
import time
import random
import logging
import threading
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
            logger.warning("无法加载 checkpoint，使用空进度。")
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


class AdaptiveRateLimiter:
    """
    自适应速率限制器 - 根据服务器响应动态调整下载速度
    
    核心策略:
    1. 正常响应 -> 逐步提速（成功计数累积）
    2. 检测到限速(403/429) -> 立即大幅降速
    3. 连续成功一定数量后 -> 尝试恢复速度
    """
    
    def __init__(
        self,
        min_sleep: float = 0.3,
        max_sleep: float = 3.0,
        initial_sleep: float = 0.8,
        speedup_threshold: int = 50,    # 连续成功N次后提速
        speedup_factor: float = 0.9,    # 提速时sleep乘以此系数
        slowdown_factor: float = 2.5,   # 降速时sleep乘以此系数
        min_workers: int = 1,
        max_workers: int = 6,
        initial_workers: int = 3,
    ):
        self.min_sleep = min_sleep
        self.max_sleep = max_sleep
        self.current_sleep = initial_sleep
        self.speedup_threshold = speedup_threshold
        self.speedup_factor = speedup_factor
        self.slowdown_factor = slowdown_factor
        
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.current_workers = initial_workers
        
        self.success_count = 0
        self.total_success = 0
        self.total_errors = 0
        self.rate_limit_events = 0
        
        self._lock = threading.Lock()
    
    def record_success(self):
        """记录成功请求，可能触发提速"""
        with self._lock:
            self.success_count += 1
            self.total_success += 1
            
            # 连续成功达到阈值，尝试提速
            if self.success_count >= self.speedup_threshold:
                old_sleep = self.current_sleep
                self.current_sleep = max(
                    self.min_sleep,
                    self.current_sleep * self.speedup_factor
                )
                # 也可以增加worker
                if self.current_workers < self.max_workers and self.success_count >= self.speedup_threshold * 2:
                    self.current_workers = min(self.max_workers, self.current_workers + 1)
                    logger.info(f"[自适应] 提速: workers {self.current_workers-1} -> {self.current_workers}")
                
                if old_sleep != self.current_sleep:
                    logger.info(f"[自适应] 提速: sleep {old_sleep:.2f}s -> {self.current_sleep:.2f}s")
                
                self.success_count = 0  # 重置计数
    
    def record_rate_limit(self):
        """记录限速事件(403/429)，立即降速"""
        with self._lock:
            self.rate_limit_events += 1
            self.total_errors += 1
            self.success_count = 0  # 重置成功计数
            
            old_sleep = self.current_sleep
            old_workers = self.current_workers
            
            # 大幅降速
            self.current_sleep = min(
                self.max_sleep,
                self.current_sleep * self.slowdown_factor
            )
            # 减少worker
            if self.current_workers > self.min_workers:
                self.current_workers = max(self.min_workers, self.current_workers - 1)
            
            logger.warning(
                f"[自适应] 检测到限速! 降速: sleep {old_sleep:.2f}s -> {self.current_sleep:.2f}s, "
                f"workers {old_workers} -> {self.current_workers}"
            )
    
    def record_error(self):
        """记录其他错误"""
        with self._lock:
            self.total_errors += 1
            # 轻微降速
            self.current_sleep = min(
                self.max_sleep,
                self.current_sleep * 1.2
            )
    
    def get_sleep_time(self) -> float:
        """获取当前应该sleep的时间（带随机抖动）"""
        with self._lock:
            base = self.current_sleep
        # 添加±30%的随机抖动，模拟人类行为
        jitter = random.uniform(0.7, 1.3)
        return base * jitter
    
    def get_current_workers(self) -> int:
        """获取当前建议的worker数量"""
        with self._lock:
            return self.current_workers
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                "current_sleep": self.current_sleep,
                "current_workers": self.current_workers,
                "total_success": self.total_success,
                "total_errors": self.total_errors,
                "rate_limit_events": self.rate_limit_events,
            }


class ServerRotator:
    """
    服务器轮询器 - 分散请求到多个服务器，避免单点压力
    """
    
    def __init__(self, url_templates: List[str]):
        if not url_templates:
            raise ValueError("至少需要一个URL模板")
        self.url_templates = url_templates
        self._index = 0
        self._lock = threading.Lock()
        self._failure_counts = {url: 0 for url in url_templates}
        self._cooldown_until = {url: 0.0 for url in url_templates}
    
    def get_next_url(self) -> str:
        """获取下一个可用的URL（轮询 + 冷却检查）"""
        with self._lock:
            now = time.time()
            attempts = 0
            while attempts < len(self.url_templates):
                url = self.url_templates[self._index]
                self._index = (self._index + 1) % len(self.url_templates)
                
                # 检查是否在冷却期
                if now >= self._cooldown_until[url]:
                    return url
                attempts += 1
            
            # 所有服务器都在冷却，返回冷却时间最短的
            min_cooldown_url = min(self._cooldown_until, key=self._cooldown_until.get)
            return min_cooldown_url
    
    def report_failure(self, url: str, is_rate_limit: bool = False):
        """报告服务器失败，可能触发冷却"""
        with self._lock:
            self._failure_counts[url] = self._failure_counts.get(url, 0) + 1
            
            if is_rate_limit:
                # 限速错误，冷却30-60秒
                cooldown = random.uniform(30, 60)
                self._cooldown_until[url] = time.time() + cooldown
                logger.warning(f"[轮询] 服务器 {url[:50]}... 触发限速，冷却 {cooldown:.0f}s")
    
    def report_success(self, url: str):
        """报告成功，重置失败计数"""
        with self._lock:
            self._failure_counts[url] = 0


# 全局自适应限速器实例（在TileDownloader中初始化）
_adaptive_limiter: Optional[AdaptiveRateLimiter] = None
_server_rotator: Optional[ServerRotator] = None


def _download_one(
    tile: mercantile.Tile,
    output_dir: str,
    url_template: Union[str, List[str]],
    session: requests.Session,
    max_retries: int,
    backoff_factor: float,
    request_timeout: float,
    adaptive_limiter: Optional[AdaptiveRateLimiter] = None,
    server_rotator: Optional[ServerRotator] = None,
) -> Tuple[str, bool, str]:
    """下载单个瓦片（支持自适应限速）"""
    filename = _tile_to_filename(tile)
    filepath = os.path.join(output_dir, filename)
    if os.path.exists(filepath):
        return filename, True, "exists"

    # 使用服务器轮询器或原始逻辑
    if server_rotator:
        urls = [server_rotator.get_next_url() for _ in range(min(3, max_retries))]
    elif isinstance(url_template, list):
        urls = list(url_template)
        random.shuffle(urls)
    else:
        urls = [url_template]

    last_error = "unknown_error"
    for url_fmt in urls:
        url = url_fmt.format(x=tile.x, y=tile.y, z=tile.z)
        
        attempt = 0
        while attempt <= max_retries:
            try:
                # 定期更换UA
                if attempt > 0 and attempt % 2 == 0:
                    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

                resp = session.get(url, stream=True, timeout=request_timeout)
                
                if resp.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # 记录成功
                    if adaptive_limiter:
                        adaptive_limiter.record_success()
                    if server_rotator:
                        server_rotator.report_success(url_fmt)
                    
                    return filename, True, "ok"
                    
                elif resp.status_code in (403, 429):
                    # 限速检测 - 触发自适应降速
                    if adaptive_limiter:
                        adaptive_limiter.record_rate_limit()
                    if server_rotator:
                        server_rotator.report_failure(url_fmt, is_rate_limit=True)
                    
                    wait = (backoff_factor ** attempt) * 2 + random.uniform(2, 5)
                    logger.warning(
                        f"限速 {resp.status_code} for tile {tile.z}/{tile.x}/{tile.y}. "
                        f"等待 {wait:.1f}s (尝试 {attempt}/{max_retries})"
                    )
                    time.sleep(wait)
                    last_error = f"rate_limit_{resp.status_code}"
                    
                elif 500 <= resp.status_code < 600:
                    wait = (backoff_factor ** attempt) + random.uniform(1, 3)
                    logger.warning(f"服务器错误 {resp.status_code}. 等待 {wait:.1f}s")
                    time.sleep(wait)
                    last_error = f"server_error_{resp.status_code}"
                    if adaptive_limiter:
                        adaptive_limiter.record_error()
                        
                else:
                    logger.error(f"意外状态码 {resp.status_code} for {url}")
                    last_error = f"status_{resp.status_code}"
                    if resp.status_code == 404:
                        break
                    
            except RequestException as e:
                wait = (backoff_factor ** attempt) + random.uniform(0.5, 2.0)
                logger.warning(f"请求异常: {e}. 等待 {wait:.1f}s")
                time.sleep(wait)
                last_error = f"request_error"
                if adaptive_limiter:
                    adaptive_limiter.record_error()
                    
            except Exception as e:
                logger.exception(f"未知异常: {e}")
                last_error = f"unknown_error"
                break

            attempt += 1

    return filename, False, f"failed: {last_error}"


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
    adaptive_limiter: Optional[AdaptiveRateLimiter] = None,
    server_rotator: Optional[ServerRotator] = None,
):
    """线程池工作函数，包含自适应速率控制"""
    # 初始随机延迟，错开请求
    time.sleep(random.uniform(0, 0.5))
    
    result = _download_one(
        tile, outdir, url_template, session, 
        max_retries, backoff_factor, request_timeout,
        adaptive_limiter, server_rotator
    )
    
    # 使用自适应sleep时间
    if adaptive_limiter:
        sleep_time = adaptive_limiter.get_sleep_time()
    else:
        sleep_time = random.uniform(min_sleep, max_sleep)
    
    time.sleep(sleep_time)
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
        logger.warning("矢量文件没有CRS信息，假设为WGS84（EPSG:4326）")
        src_crs = "EPSG:4326"

    # 如果不是WGS84，则转换
    if src_crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    bounds = gdf.total_bounds  # (minx, miny, maxx, maxy)
    return bounds[0], bounds[1], bounds[2], bounds[3]  # west, south, east, north


class TileDownloader:
    """瓦片下载器，支持从shapefile或bbox下载图像瓦片（带自适应限速）"""

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
        enable_adaptive: bool = True,  # 新增：启用自适应限速
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
        - enable_adaptive: 是否启用自适应限速（推荐开启）
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
        self.enable_adaptive = enable_adaptive
        
        self._stop_event = False
        self._executor = None

        self.session = _make_session(user_agent=user_agent, proxies=proxies)
        self.checkpoint = _load_checkpoint(checkpoint_path)
        
        # 初始化自适应限速器和服务器轮询器
        if enable_adaptive:
            self.adaptive_limiter = AdaptiveRateLimiter(
                min_sleep=per_thread_min_sleep,
                max_sleep=per_thread_max_sleep * 2,
                initial_sleep=(per_thread_min_sleep + per_thread_max_sleep) / 2,
                min_workers=1,
                max_workers=max_workers,
                initial_workers=min(3, max_workers),  # 保守起步
            )
            
            # 如果有多个URL，初始化轮询器
            if isinstance(url_template, list) and len(url_template) > 1:
                self.server_rotator = ServerRotator(url_template)
                logger.info(f"[自适应] 已启用服务器轮询，{len(url_template)}个节点")
            else:
                self.server_rotator = None
                
            logger.info("[自适应] 已启用自适应限速策略")
        else:
            self.adaptive_limiter = None
            self.server_rotator = None

    def stop(self):
        """Request stop."""
        self._stop_event = True
        if self._executor:
            self._executor.shutdown(wait=False)

    def _save_checkpoint(self):
        """保存检查点"""
        _save_checkpoint(self.checkpoint_path, self.checkpoint)

    def _download_tiles_impl(self, tiles: List[mercantile.Tile], callback=None):
        """实现瓦片下载的核心逻辑"""
        if not tiles:
            logging.error("No tiles to download.")
            if callback:
                callback("No tiles to download.")
            return

        try:
            msg = f"Total tiles to download: {len(tiles)}"
            logging.info(msg)
            if callback:
                callback(msg)

            os.makedirs(self.output_base_dir, exist_ok=True)

            already_done = set(self.checkpoint.get("done", []))
            pending_tiles = [t for t in tiles if _tile_to_filename(t) not in already_done]

            msg = f"{len(pending_tiles)} tiles pending (after checkpoint filter)."
            logging.info(msg)
            if callback:
                callback(msg)

            n = len(pending_tiles)
            if n == 0:
                logging.info("No pending tiles to download.")
                if callback:
                    callback("No pending tiles to download.")
                return

            total_batches = math.ceil(n / self.batch_size)
            msg = f"Splitting into {total_batches} batch(es) with batch_size={self.batch_size}"
            logging.info(msg)
            if callback:
                callback(msg)

            for batch_idx in range(total_batches):
                if self._stop_event:
                    msg = "Download stopped by user request."
                    logging.info(msg)
                    if callback:
                        callback(msg)
                    break
                    
                s = batch_idx * self.batch_size
                e = min((batch_idx + 1) * self.batch_size, n)
                batch_tiles = pending_tiles[s:e]
                msg = f"Starting batch {batch_idx + 1}/{total_batches}: tiles {s + 1}..{e}"
                logging.info(msg)
                if callback:
                    callback(msg)

                failures = []
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
                with self._executor as executor:
                    future_to_tile = {}
                    for tile in batch_tiles:
                        if self._stop_event: break
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
                            self.adaptive_limiter,
                            self.server_rotator,
                        )
                        future_to_tile[future] = tile

                    completed = 0
                    for future in as_completed(future_to_tile):
                        if self._stop_event: 
                            logging.info("Download stopping...")
                            break
                            
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
                        # 每10%进度输出一次
                        if completed % max(1, len(future_to_tile) // 10) == 0:
                            msg = f"Progress: {completed}/{len(future_to_tile)}"
                            logging.info(msg)
                            if callback:
                                callback(msg)

                self._save_checkpoint()
                msg = f"Batch {batch_idx + 1} finished. Success: {len(batch_tiles) - len(failures)}, Failures: {len(failures)}"
                logging.info(msg)
                if callback:
                    callback(msg)

                if failures:
                    fail_path = os.path.join(self.output_base_dir, f"failures_batch_{batch_idx+1}.json")
                    with open(fail_path, 'w', encoding='utf-8') as f:
                        json.dump(failures, f, ensure_ascii=False, indent=2)
                    logger.warning(f"失败记录已保存到 {fail_path}")

                if batch_idx < total_batches - 1 and not self._stop_event:
                    pause = random.uniform(self.batch_pause_min, self.batch_pause_max)
                    msg = f"Pausing {pause:.1f}s before next batch..."
                    logging.info(msg)
                    if callback:
                        callback(msg)
                    time.sleep(pause)

            # 最终统计
            if self.enable_adaptive and self.adaptive_limiter:
                final_stats = self.adaptive_limiter.get_stats()
                logger.info(
                    f"下载完成! 总计: 成功 {final_stats['total_success']}, "
                    f"错误 {final_stats['total_errors']}, 限速事件 {final_stats['rate_limit_events']}"
                )
            else:
                logger.info("所有批次下载完成。")
            
            self._save_checkpoint()
            
        except Exception as e:
            logging.exception(f"Error in _download_tiles_impl: {e}")
            if callback:
                callback(f"Error: {e}")


    def download_tiles_from_bbox(self, bbox: Union[str, tuple, list], zoom: int, callback=None):
        """从BBox下载瓦片"""
        west, south, east, north = _parse_bbox_input(bbox)
        tiles = list(mercantile.tiles(west, south, east, north, [zoom]))
        self._download_tiles_impl(tiles, callback=callback)

    def download_tiles_from_vector(self, vector_path: str, zoom: int, callback=None):
        """从矢量文件下载瓦片"""
        west, south, east, north = _prepare_bounds_from_vector(vector_path)
        tiles = list(mercantile.tiles(west, south, east, north, [zoom]))
        self._download_tiles_impl(tiles, callback=callback)

    def download_tiles(self, input_range: Union[str, tuple, list], zoom: int, is_vector: bool = False, callback=None):
        """
        统一的下载入口
        
        参数:
        - input_range: 矢量文件路径或BBox (west,south,east,north)
        - zoom: 缩放级别
        - is_vector: 是否为矢量输入
        - callback: 进度回调函数
        """
        if is_vector:
            self.download_tiles_from_vector(input_range, zoom, callback=callback)
        else:
            self.download_tiles_from_bbox(input_range, zoom, callback=callback)


