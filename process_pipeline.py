#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据清洗完整流程 - 命令行工具

功能：
1. 从矢量边界文件读取范围
2. 下载卫星瓦片
3. 下载并清洗OSM道路数据
4. 拼接瓦片
5. 清洗瓦片（黑边检测 + 道路筛选）

使用示例：
    python process_pipeline.py \\
        --boundary "path/to/boundary.shp" \\
        --output "output/directory" \\
        --road-threshold 0.5 \\
        --black-threshold 0.0625 \\
        --zoom 17

作者: DataProcess Team
日期: 2025-12-29
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime
import json
from uuid import uuid4
from typing import Any, Dict, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

import geopandas as gpd
import mercantile
from core.tile_downloader import TileDownloader
from core.osm_fetcher import fetch_osm_features
from core.osm_cleaner import OSMCleaner
from core.tile_compositor import TileCompositor
from core.tile_filter import TileFilter
from config.download_types import DOWNLOAD_TYPES


def setup_logging(output_dir, verbose=False):
    """配置日志系统"""
    log_dir = Path(output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    level = logging.DEBUG if verbose else logging.INFO
    
    # 配置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return log_file


def _save_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _file_info(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    try:
        p = Path(path)
        if not p.exists():
            return {"path": str(p), "exists": False}
        st = p.stat()
        return {
            "path": str(p.resolve()),
            "exists": True,
            "size_bytes": int(st.st_size),
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
        }
    except Exception:
        return {"path": str(path), "exists": False, "error": "stat_failed"}


class DataProcessingPipeline:
    """数据处理流程管理器"""
    
    def __init__(self, boundary_file, output_dir, zoom=17, 
                 road_threshold=0.5, black_threshold=0.0625,
                 enable_road_filter=True):
        """
        初始化处理流程
        
        Args:
            boundary_file: 矢量边界文件路径
            output_dir: 输出目录
            zoom: 瓦片缩放级别
            road_threshold: 道路筛选阈值（道路长度/对角线长度）
            black_threshold: 黑边筛选阈值（黑像素比例）
            enable_road_filter: 是否启用道路筛选
        """
        self.boundary_file = Path(boundary_file)
        self.output_dir = Path(output_dir)
        self.zoom = zoom
        self.road_threshold = road_threshold
        self.black_threshold = black_threshold
        self.enable_road_filter = enable_road_filter
        
        # 创建输出子目录
        self.tiles_dir = self.output_dir / f"tiles_z{zoom}"
        self.osm_dir = self.output_dir / "osm_data"
        self.composited_dir = self.output_dir / "composited"
        self.filtered_dir = self.output_dir / "filtered_images"
        
        for d in [self.tiles_dir, self.osm_dir, self.composited_dir, self.filtered_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        self.bbox = None
        self.logger = logging.getLogger(self.__class__.__name__)

        self.run_id = uuid4().hex
        self.manifest_path = self.output_dir / "pipeline_manifest.json"
        self._manifest = {
            "type": "data_processing_pipeline",
            "run_id": self.run_id,
            "started_at": None,
            "finished_at": None,
            "inputs": {
                "boundary_file": str(self.boundary_file.resolve()),
            },
            "config": {
                "zoom": int(self.zoom),
                "road_threshold": float(self.road_threshold),
                "black_threshold": float(self.black_threshold),
                "enable_road_filter": bool(self.enable_road_filter),
            },
            "bbox_wgs84": None,
            "steps": {},
            "artifacts": {
                "tiles_dir": str(self.tiles_dir.resolve()),
                "tiles_manifest": None,
                "osm_raw": None,
                "osm_cleaned": None,
                "composited_dir": str(self.composited_dir.resolve()),
                "filtered_dir": str(self.filtered_dir.resolve()),
                "log_dir": str((self.output_dir / "logs").resolve()),
            },
            "metrics": {},
            "status": "running",
            "error": None,
        }

    def _manifest_update(self, **kwargs) -> None:
        self._manifest.update(kwargs)
        try:
            _save_json_atomic(self.manifest_path, self._manifest)
        except Exception:
            self.logger.exception("写入 pipeline_manifest.json 失败")

    def _step_start(self, name: str, extra: Optional[Dict[str, Any]] = None) -> None:
        steps = self._manifest.setdefault("steps", {})
        step = steps.setdefault(name, {})
        step.update({
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "duration_seconds": None,
            "metrics": step.get("metrics", {}),
            "artifacts": step.get("artifacts", {}),
            "error": None,
        })
        if extra:
            step.update(extra)
        self._manifest_update()

    def _step_finish(self, name: str, status: str = "success", error: Optional[str] = None) -> None:
        steps = self._manifest.setdefault("steps", {})
        step = steps.setdefault(name, {})
        finished_at = datetime.now()
        step["finished_at"] = finished_at.isoformat()
        try:
            if step.get("started_at"):
                started_at = datetime.fromisoformat(step["started_at"])
                step["duration_seconds"] = float((finished_at - started_at).total_seconds())
        except Exception:
            step["duration_seconds"] = None
        step["status"] = status
        step["error"] = error
        self._manifest_update()
    
    def step1_read_boundary(self):
        """步骤1: 读取矢量边界"""
        self.logger.info("="*80)
        self.logger.info("步骤 1/7: 读取矢量边界")
        self.logger.info("="*80)

        self._step_start("read_boundary", {
            "artifacts": {
                "boundary_file": _file_info(self.boundary_file),
            }
        })
        
        if not self.boundary_file.exists():
            raise FileNotFoundError(f"边界文件不存在: {self.boundary_file}")
        
        self.logger.info(f"读取文件: {self.boundary_file}")
        gdf = gpd.read_file(str(self.boundary_file))
        
        # 转换到WGS84
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            self.logger.info(f"转换坐标系: {gdf.crs} -> EPSG:4326")
            gdf = gdf.to_crs("EPSG:4326")
        
        bbox_arr = gdf.total_bounds
        self.bbox = (float(bbox_arr[0]), float(bbox_arr[1]), 
                    float(bbox_arr[2]), float(bbox_arr[3]))
        
        self.logger.info(f"边界范围 (WGS84): {self.bbox}")
        self.logger.info(f"要素数量: {len(gdf)}")
        
        # 计算预计瓦片数
        tiles = list(mercantile.tiles(*self.bbox, [self.zoom]))
        self.logger.info(f"预计下载瓦片数: {len(tiles)}")

        self._manifest["bbox_wgs84"] = [self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3]]
        self._manifest.setdefault("metrics", {})["estimated_tiles"] = int(len(tiles))
        self._manifest["steps"]["read_boundary"].setdefault("metrics", {})["features"] = int(len(gdf))
        self._manifest["steps"]["read_boundary"].setdefault("metrics", {})["estimated_tiles"] = int(len(tiles))
        self._manifest["steps"]["read_boundary"].setdefault("artifacts", {})["bbox"] = self._manifest["bbox_wgs84"]
        self._manifest_update()

        self._step_finish("read_boundary", status="success")
        
        return self.bbox
    
    def step2_download_tiles(self):
        """步骤2: 下载卫星瓦片"""
        self.logger.info("="*80)
        self.logger.info("步骤 2/7: 下载卫星瓦片")
        self.logger.info("="*80)

        self._step_start("download_tiles", {
            "metrics": {
                "zoom": int(self.zoom),
            },
            "artifacts": {
                "tiles_dir": _file_info(self.tiles_dir),
            }
        })
        
        dt = DOWNLOAD_TYPES['google']
        
        self.logger.info(f"瓦片来源: Google Satellite")
        self.logger.info(f"缩放级别: {self.zoom}")
        self.logger.info(f"输出目录: {self.tiles_dir}")
        
        downloader = TileDownloader(
            url_template=dt.url_options[0],
            output_base_dir=str(self.tiles_dir),
            max_workers=4,
            per_thread_min_sleep=0.5,
            per_thread_max_sleep=1.0
        )
        
        downloader.download_tiles_from_bbox(self.bbox, self.zoom)
        
        # 统计下载结果
        downloaded = len(list(self.tiles_dir.glob("*.png")))
        self.logger.info(f"✓ 下载完成，共 {downloaded} 个瓦片")

        tiles_manifest = self.tiles_dir / "download_manifest.json"
        self._manifest["artifacts"]["tiles_manifest"] = str(tiles_manifest.resolve()) if tiles_manifest.exists() else None
        self._manifest.setdefault("metrics", {})["tiles_downloaded"] = int(downloaded)
        self._manifest["steps"]["download_tiles"].setdefault("metrics", {})["tiles_downloaded"] = int(downloaded)
        self._manifest["steps"]["download_tiles"].setdefault("artifacts", {})["tiles_manifest"] = _file_info(tiles_manifest)
        self._manifest_update()

        self._step_finish("download_tiles", status="success")
        
        return downloaded
    
    def step3_download_osm(self):
        """步骤3: 下载OSM道路数据"""
        self.logger.info("="*80)
        self.logger.info("步骤 3/7: 下载OSM道路数据")
        self.logger.info("="*80)

        self._step_start("download_osm", {
            "artifacts": {
                "osm_raw": _file_info(self.osm_dir / "osm_roads.geojson"),
            }
        })
        
        osm_file = self.osm_dir / "osm_roads.geojson"
        
        bbox_str = f"{self.bbox[0]},{self.bbox[1]},{self.bbox[2]},{self.bbox[3]}"
        self.logger.info(f"范围: {bbox_str}")
        
        try:
            result = fetch_osm_features(
                vector_path=None,
                bbox=bbox_str,
                output_path=str(osm_file),
                data_types=["road"]
            )
            
            if result is not None and len(result) > 0:
                self.logger.info(f"✓ 下载完成，共 {len(result)} 条道路要素")
                self._manifest["artifacts"]["osm_raw"] = str(osm_file.resolve())
                self._manifest.setdefault("metrics", {})["osm_features"] = int(len(result))
                self._manifest["steps"]["download_osm"].setdefault("metrics", {})["osm_features"] = int(len(result))
                self._manifest["steps"]["download_osm"].setdefault("artifacts", {})["osm_raw"] = _file_info(osm_file)
                self._manifest_update()
                self._step_finish("download_osm", status="success")
                return osm_file
            else:
                self.logger.warning("未获取到道路要素，跳过道路筛选功能")
                self._manifest["artifacts"]["osm_raw"] = str(osm_file.resolve()) if osm_file.exists() else None
                self._manifest.setdefault("metrics", {})["osm_features"] = 0
                self._manifest["steps"]["download_osm"].setdefault("metrics", {})["osm_features"] = 0
                self._manifest["steps"]["download_osm"].setdefault("artifacts", {})["osm_raw"] = _file_info(osm_file)
                self._manifest_update()
                self._step_finish("download_osm", status="success")
                return None
        except Exception as e:
            self.logger.error(f"OSM下载失败: {e}")
            self.logger.warning("将跳过道路筛选功能")
            self._manifest["artifacts"]["osm_raw"] = str(osm_file.resolve()) if osm_file.exists() else None
            self._manifest["error"] = f"osm_download_failed: {e}"
            self._manifest_update()
            self._step_finish("download_osm", status="failed", error=str(e))
            return None
    
    def step4_clean_osm(self, osm_file):
        """步骤4: 清洗OSM数据"""
        self.logger.info("="*80)
        self.logger.info("步骤 4/7: 清洗OSM道路数据")
        self.logger.info("="*80)

        self._step_start("clean_osm", {
            "artifacts": {
                "osm_raw": _file_info(osm_file) if osm_file else None,
            }
        })
        
        if osm_file is None or not osm_file.exists():
            self.logger.warning("OSM文件不存在，跳过")
            self._step_finish("clean_osm", status="skipped", error="osm_missing")
            return None
        
        cleaned_file = self.osm_dir / "osm_trunk_roads.geojson"
        
        self.logger.info(f"输入文件: {osm_file}")
        self.logger.info(f"输出文件: {cleaned_file}")
        
        cleaner = OSMCleaner(str(osm_file))
        trunk_roads = cleaner.extract_trunk_roads()
        cleaner.save(str(cleaned_file))
        
        self.logger.info(f"✓ 提取完成，保留 {len(trunk_roads)} 条主干道")

        self._manifest["artifacts"]["osm_cleaned"] = str(cleaned_file.resolve()) if cleaned_file.exists() else None
        self._manifest.setdefault("metrics", {})["osm_trunk_roads"] = int(len(trunk_roads))
        self._manifest["steps"]["clean_osm"].setdefault("metrics", {})["osm_trunk_roads"] = int(len(trunk_roads))
        self._manifest["steps"]["clean_osm"].setdefault("artifacts", {})["osm_cleaned"] = _file_info(cleaned_file)
        self._manifest_update()

        self._step_finish("clean_osm", status="success")
        
        return cleaned_file
    
    def step5_composite_tiles(self):
        """步骤5: 拼接瓦片"""
        self.logger.info("="*80)
        self.logger.info("步骤 5/7: 拼接瓦片")
        self.logger.info("="*80)

        self._step_start("composite_tiles", {
            "artifacts": {
                "tiles_dir": _file_info(self.tiles_dir),
                "composited_dir": _file_info(self.composited_dir),
            }
        })
        
        self.logger.info(f"瓦片目录: {self.tiles_dir}")
        self.logger.info(f"输出目录: {self.composited_dir}")
        
        compositor = TileCompositor(
            tiles_dir=str(self.tiles_dir),
            zoom_level=self.zoom,
            output_dir=str(self.composited_dir)
        )
        
        results = compositor.composite_and_save(
            output_base_dir=str(self.composited_dir),
            generate_vrt=False
        )
        
        self.logger.info(f"✓ 拼接完成，生成 {len(results)} 个复合图")

        self._manifest.setdefault("metrics", {})["composited_images"] = int(len(results))
        self._manifest["steps"]["composite_tiles"].setdefault("metrics", {})["composited_images"] = int(len(results))
        self._manifest_update()

        self._step_finish("composite_tiles", status="success")
        
        return len(results)
    
    def step6_filter_black(self):
        """步骤6: 黑边检测"""
        self.logger.info("="*80)
        self.logger.info("步骤 6/7: 黑边检测")
        self.logger.info("="*80)

        self._step_start("filter_black", {
            "metrics": {
                "black_threshold": float(self.black_threshold),
            },
            "artifacts": {
                "input_images_dir": _file_info(self.composited_dir / "images"),
            }
        })
        
        input_images = self.composited_dir / "images"
        temp_dir = self.output_dir / "temp_filtered_black"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        if not input_images.exists():
            raise FileNotFoundError(f"拼接图像目录不存在: {input_images}")
        
        self.logger.info(f"黑边阈值: {self.black_threshold}")
        
        tile_filter = TileFilter(
            input_dir=str(input_images),
            output_dir=str(temp_dir),
            threshold_ratio=self.black_threshold
        )
        
        total, copied, skipped = tile_filter.process()
        
        self.logger.info(f"✓ 黑边检测完成")
        self.logger.info(f"  总计: {total}")
        self.logger.info(f"  保留: {copied}")
        self.logger.info(f"  剔除: {skipped}")

        self._manifest.setdefault("metrics", {})["black_filter_total"] = int(total)
        self._manifest.setdefault("metrics", {})["black_filter_kept"] = int(copied)
        self._manifest.setdefault("metrics", {})["black_filter_removed"] = int(skipped)
        self._manifest["steps"]["filter_black"].setdefault("metrics", {}).update({
            "total": int(total),
            "kept": int(copied),
            "removed": int(skipped),
        })
        self._manifest_update()

        self._step_finish("filter_black", status="success")
        
        return temp_dir, total, copied, skipped
    
    def step7_filter_road(self, input_dir, cleaned_osm_file):
        """步骤7: 道路筛选"""
        self.logger.info("="*80)
        self.logger.info("步骤 7/7: 道路筛选")
        self.logger.info("="*80)

        self._step_start("filter_road", {
            "metrics": {
                "road_threshold": float(self.road_threshold),
                "enable_road_filter": bool(self.enable_road_filter),
            },
            "artifacts": {
                "input_dir": _file_info(Path(input_dir)),
                "osm_cleaned": _file_info(cleaned_osm_file) if cleaned_osm_file else None,
                "filtered_dir": _file_info(self.filtered_dir),
            }
        })
        
        if not self.enable_road_filter:
            self.logger.info("道路筛选未启用，直接使用黑边筛选结果")
            # 复制文件到最终输出目录
            import shutil
            for img in input_dir.glob("*.png"):
                shutil.copy2(img, self.filtered_dir / img.name)
            self._manifest.setdefault("metrics", {})["road_filter_enabled"] = False
            self._manifest.setdefault("metrics", {})["final_kept"] = int(len(list(self.filtered_dir.glob("*.png"))))
            self._manifest_update()
            self._step_finish("filter_road", status="skipped", error="road_filter_disabled")
            return len(list(self.filtered_dir.glob("*.png"))), 0, 0
        
        if cleaned_osm_file is None or not cleaned_osm_file.exists():
            self.logger.warning("OSM文件不存在，跳过道路筛选")
            # 复制文件到最终输出目录
            import shutil
            for img in input_dir.glob("*.png"):
                shutil.copy2(img, self.filtered_dir / img.name)
            self._manifest.setdefault("metrics", {})["road_filter_enabled"] = False
            self._manifest.setdefault("metrics", {})["final_kept"] = int(len(list(self.filtered_dir.glob("*.png"))))
            self._manifest_update()
            self._step_finish("filter_road", status="skipped", error="osm_missing")
            return len(list(self.filtered_dir.glob("*.png"))), 0, 0
        
        self.logger.info(f"矢量文件: {cleaned_osm_file}")
        self.logger.info(f"道路阈值: {self.road_threshold}")
        
        tile_filter = TileFilter(
            input_dir=str(input_dir),
            output_dir=str(self.filtered_dir),
            threshold_ratio=self.black_threshold,
            road_vector_path=str(cleaned_osm_file),
            road_threshold=self.road_threshold,
            road_method="length"
        )
        
        total, copied, skipped = tile_filter.process()
        
        # 计算额外过滤数
        black_filtered_count = len(list(input_dir.glob("*.png")))
        additional_filtered = black_filtered_count - copied
        
        self.logger.info(f"✓ 道路筛选完成")
        self.logger.info(f"  总计: {total}")
        self.logger.info(f"  保留: {copied}")
        self.logger.info(f"  剔除: {skipped}")
        self.logger.info(f"  额外过滤（道路不足）: {additional_filtered}")

        self._manifest.setdefault("metrics", {})["road_filter_enabled"] = True
        self._manifest.setdefault("metrics", {})["road_filter_total"] = int(total)
        self._manifest.setdefault("metrics", {})["road_filter_kept"] = int(copied)
        self._manifest.setdefault("metrics", {})["road_filter_removed"] = int(skipped)
        self._manifest.setdefault("metrics", {})["road_filter_additional_removed"] = int(additional_filtered)
        self._manifest.setdefault("metrics", {})["final_kept"] = int(copied)
        self._manifest_update()

        self._step_finish("filter_road", status="success")
        
        return total, copied, additional_filtered
    
    def run(self):
        """运行完整流程"""
        start_time = datetime.now()
        self._manifest["started_at"] = start_time.isoformat()
        self._manifest_update()
        
        self.logger.info("="*80)
        self.logger.info("数据清洗流程开始")
        self.logger.info("="*80)
        self.logger.info(f"边界文件: {self.boundary_file}")
        self.logger.info(f"输出目录: {self.output_dir}")
        self.logger.info(f"缩放级别: {self.zoom}")
        self.logger.info(f"黑边阈值: {self.black_threshold}")
        self.logger.info(f"道路阈值: {self.road_threshold}")
        self.logger.info(f"道路筛选: {'启用' if self.enable_road_filter else '禁用'}")
        self.logger.info("="*80)
        
        try:
            # 步骤1: 读取边界
            self.step1_read_boundary()
            
            # 步骤2: 下载瓦片
            tile_count = self.step2_download_tiles()
            
            # 步骤3: 下载OSM
            osm_file = self.step3_download_osm()
            
            # 步骤4: 清洗OSM
            cleaned_osm_file = self.step4_clean_osm(osm_file)
            
            # 步骤5: 拼接
            composite_count = self.step5_composite_tiles()
            
            # 步骤6: 黑边检测
            temp_dir, total, kept_black, removed_black = self.step6_filter_black()
            
            # 步骤7: 道路筛选
            total_final, kept_final, additional_removed = self.step7_filter_road(
                temp_dir, cleaned_osm_file
            )
            
            # 清理临时目录
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # 总结
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self._manifest["finished_at"] = end_time.isoformat()
            self._manifest.setdefault("metrics", {})["duration_seconds"] = float(duration)
            self._manifest["status"] = "success"
            self._manifest["error"] = None

            # 在成功结束时补充主要产物文件信息
            self._manifest["artifacts"]["tiles_manifest"] = self._manifest["artifacts"].get("tiles_manifest")
            self._manifest["artifacts"]["boundary_file"] = str(self.boundary_file.resolve())
            self._manifest["artifacts"]["boundary_file_info"] = _file_info(self.boundary_file)
            self._manifest["artifacts"]["osm_raw_info"] = _file_info(Path(self._manifest["artifacts"]["osm_raw"])) if self._manifest["artifacts"].get("osm_raw") else None
            self._manifest["artifacts"]["osm_cleaned_info"] = _file_info(Path(self._manifest["artifacts"]["osm_cleaned"])) if self._manifest["artifacts"].get("osm_cleaned") else None
            self._manifest_update()
            
            self.logger.info("="*80)
            self.logger.info("处理完成！")
            self.logger.info("="*80)
            self.logger.info(f"总耗时: {duration:.2f} 秒")
            self.logger.info(f"下载瓦片: {tile_count}")
            self.logger.info(f"拼接图像: {composite_count}")
            self.logger.info(f"黑边过滤后: {kept_black}/{total}")
            if self.enable_road_filter and cleaned_osm_file:
                self.logger.info(f"道路筛选后: {kept_final}/{total_final} (额外过滤: {additional_removed})")
            else:
                self.logger.info(f"最终保留: {kept_final}")
            self.logger.info(f"输出目录: {self.filtered_dir}")
            self.logger.info("="*80)
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理失败: {e}", exc_info=True)
            self._manifest["finished_at"] = datetime.now().isoformat()
            self._manifest["status"] = "failed"
            self._manifest["error"] = str(e)
            # 标记当前未完成 step
            for name, step in self._manifest.get("steps", {}).items():
                if step.get("status") == "running":
                    self._step_finish(name, status="failed", error=str(e))
                    break
            self._manifest_update()
            return False


def main():
    """主函数：解析命令行参数并运行流程"""
    parser = argparse.ArgumentParser(
        description='数据清洗完整流程 - 从矢量边界到筛选后的卫星图像',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:

  基本用法：
    python process_pipeline.py -b boundary.shp -o output/

  完整参数：
    python process_pipeline.py \\
        --boundary "C:/data/boundary.shp" \\
        --output "D:/output" \\
        --road-threshold 0.5 \\
        --black-threshold 0.0625 \\
        --zoom 17 \\
        --no-road-filter  # 禁用道路筛选

  查看详细日志：
    python process_pipeline.py -b boundary.shp -o output/ -v

注意：
  - 边界文件支持 Shapefile, GeoJSON, GeoPackage 等格式
  - 输出目录会自动创建子目录组织数据
  - 日志文件保存在 output/logs/ 目录下
        """
    )
    
    # 必需参数
    parser.add_argument(
        '-b', '--boundary',
        required=True,
        help='矢量边界文件路径 (Shapefile, GeoJSON, etc.)'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='输出目录路径'
    )
    
    # 可选参数
    parser.add_argument(
        '--road-threshold',
        type=float,
        default=0.5,
        help='道路筛选阈值 (道路长度/对角线长度，默认: 0.5)'
    )
    
    parser.add_argument(
        '--black-threshold',
        type=float,
        default=0.0625,
        help='黑边筛选阈值 (黑像素比例，默认: 0.0625 即 1/16)'
    )
    
    parser.add_argument(
        '--zoom',
        type=int,
        default=17,
        choices=range(10, 20),
        metavar='10-19',
        help='瓦片缩放级别 (默认: 17)'
    )
    
    parser.add_argument(
        '--no-road-filter',
        action='store_true',
        help='禁用道路筛选，只使用黑边检测'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细日志信息'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    log_file = setup_logging(args.output, args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info(f"日志文件: {log_file}")
    
    # 创建并运行流程
    pipeline = DataProcessingPipeline(
        boundary_file=args.boundary,
        output_dir=args.output,
        zoom=args.zoom,
        road_threshold=args.road_threshold,
        black_threshold=args.black_threshold,
        enable_road_filter=not args.no_road_filter
    )
    
    success = pipeline.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
