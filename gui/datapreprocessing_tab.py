"""Data Preprocessing Tab - integrates Download, Cleaning, and Stitching."""
from __future__ import annotations

import os
import sys
import logging
import mercantile
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFileDialog,
    QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QMessageBox,
    QRadioButton, QStackedWidget, QScrollArea
)

# Import modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.download_types import DOWNLOAD_TYPES, DEFAULT_DOWNLOAD_TYPE
from utils.url_detector import detect_working_urls
from core.tile_downloader import TileDownloader
from core.osm_fetcher import fetch_osm_features
from core.osm_cleaner import OSMCleaner
from core.tile_compositor import TileCompositor
from core.tile_filter import TileFilter


class DataPreprocessingTab(QWidget):
    """Unified data preprocessing tab."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.worker = None
        self.download_worker = None
        self.cleaner: Optional[OSMCleaner] = None
        self.compositor: Optional[TileCompositor] = None
        self._build_ui()

    def _build_ui(self) -> None:
        # Create scroll area for the entire tab
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Title
        title = QLabel("数据预处理")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # Create Grid Layout for 4 features
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        # Ensure equal column width
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)

        # ============ GroupBox 1: 数据下载 ============
        download_group = self._build_download_group()
        grid_layout.addWidget(download_group, 0, 0)

        # ============ GroupBox 2: 数据清洗 ============
        clean_group = self._build_clean_group()
        grid_layout.addWidget(clean_group, 0, 1)

        # ============ GroupBox 3: 瓦片拼接 ============
        stitch_group = self._build_stitch_group()
        grid_layout.addWidget(stitch_group, 1, 0)

        # ============ GroupBox 4: 瓦片清洗 ============
        filter_group = self._build_filter_group()
        grid_layout.addWidget(filter_group, 1, 1)

        # Add grid to main layout
        main_layout.addLayout(grid_layout)

        # ============ Shared Log ============
        log_label = QLabel("操作日志:")
        log_font = QFont()
        log_font.setBold(True)
        log_label.setFont(log_font)
        main_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(250)
        main_layout.addWidget(self.log_text)

        main_layout.addStretch()
        
        scroll.setWidget(content_widget)
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

    def _build_download_group(self) -> QGroupBox:
        """Build data download GroupBox."""
        group = QGroupBox("1. 数据下载")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Download type
        type_layout = QFormLayout()
        self.download_type_combo = QComboBox()
        for key, dtype in DOWNLOAD_TYPES.items():
            self.download_type_combo.addItem(dtype.get_display_name(), key)
        type_layout.addRow("下载类型:", self.download_type_combo)
        layout.addLayout(type_layout)

        # Vector BBox loader
        vec_bbox_layout = QHBoxLayout()
        self.bbox_vector_file = QLineEdit()
        self.bbox_vector_file.setPlaceholderText("选择矢量文件以读取范围...")
        vec_bbox_btn = QPushButton("浏览")
        vec_bbox_btn.setMaximumWidth(60)
        vec_bbox_btn.clicked.connect(self._select_bbox_vector)
        
        load_bbox_btn = QPushButton("读取")
        load_bbox_btn.setMaximumWidth(60)
        load_bbox_btn.clicked.connect(self._load_bbox_from_vector)
        
        vec_bbox_layout.addWidget(QLabel("从矢量:"))
        vec_bbox_layout.addWidget(self.bbox_vector_file)
        vec_bbox_layout.addWidget(vec_bbox_btn)
        vec_bbox_layout.addWidget(load_bbox_btn)
        layout.addLayout(vec_bbox_layout)

        # Range input (simplified - bbox only)
        range_layout = QFormLayout()
        
        self.bbox_left = QDoubleSpinBox()
        self.bbox_left.setRange(-180, 180)
        self.bbox_left.setDecimals(6)
        self.bbox_bottom = QDoubleSpinBox()
        self.bbox_bottom.setRange(-90, 90)
        self.bbox_bottom.setDecimals(6)
        self.bbox_right = QDoubleSpinBox()
        self.bbox_right.setRange(-180, 180)
        self.bbox_right.setDecimals(6)
        self.bbox_top = QDoubleSpinBox()
        self.bbox_top.setRange(-90, 90)
        self.bbox_top.setDecimals(6)

        # Use Grid Layout for BBox to save horizontal space
        bbox_layout = QGridLayout()
        bbox_layout.setSpacing(5)
        
        # Row 0: Left, Right (MinX, MaxX)
        bbox_layout.addWidget(QLabel("Left:"), 0, 0)
        bbox_layout.addWidget(self.bbox_left, 0, 1)
        bbox_layout.addWidget(QLabel("Right:"), 0, 2)
        bbox_layout.addWidget(self.bbox_right, 0, 3)
        
        # Row 1: Bottom, Top (MinY, MaxY)
        bbox_layout.addWidget(QLabel("Bottom:"), 1, 0)
        bbox_layout.addWidget(self.bbox_bottom, 1, 1)
        bbox_layout.addWidget(QLabel("Top:"), 1, 2)
        bbox_layout.addWidget(self.bbox_top, 1, 3)
        
        range_layout.addRow("BBox:", bbox_layout)
        layout.addLayout(range_layout)

        # Output
        out_layout = QHBoxLayout()
        self.download_output = QLineEdit("data/output")
        out_btn = QPushButton("浏览")
        out_btn.setMaximumWidth(70)
        out_btn.clicked.connect(lambda: self._select_dir(self.download_output))
        out_layout.addWidget(self.download_output)
        out_layout.addWidget(out_btn)
        
        out_form = QFormLayout()
        out_form.addRow("输出目录:", out_layout)
        layout.addLayout(out_form)

        # Download button
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setMinimumHeight(32)
        self.download_btn.clicked.connect(self._start_download)
        layout.addWidget(self.download_btn)

        return group

    def _build_clean_group(self) -> QGroupBox:
        """Build data cleaning GroupBox."""
        group = QGroupBox("2. 数据清洗")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Input file
        file_layout = QHBoxLayout()
        self.clean_input = QLineEdit()
        self.clean_input.setPlaceholderText("选择OSM GeoJSON文件")
        file_btn = QPushButton("浏览")
        file_btn.setMaximumWidth(70)
        file_btn.clicked.connect(self._select_clean_input)
        file_layout.addWidget(self.clean_input)
        file_layout.addWidget(file_btn)
        
        file_form = QFormLayout()
        file_form.addRow("输入文件:", file_layout)
        layout.addLayout(file_form)

        # Output file
        out_layout = QHBoxLayout()
        self.clean_output = QLineEdit("data/output/osm_trunk_roads.geojson")
        out_btn = QPushButton("浏览")
        out_btn.setMaximumWidth(70)
        out_btn.clicked.connect(lambda: self._select_save_file(self.clean_output))
        out_layout.addWidget(self.clean_output)
        out_layout.addWidget(out_btn)
        
        out_form = QFormLayout()
        out_form.addRow("输出文件:", out_layout)
        layout.addLayout(out_form)

        # Extract and save buttons
        btn_layout = QHBoxLayout()
        extract_btn = QPushButton("提取主干道")
        extract_btn.clicked.connect(self._extract_trunk_roads)
        save_btn = QPushButton("保存结果")
        save_btn.clicked.connect(self._save_cleaned)
        btn_layout.addWidget(extract_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        return group

    def _build_stitch_group(self) -> QGroupBox:
        """Build tile stitching GroupBox."""
        group = QGroupBox("3. 瓦片拼接")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        form_layout = QFormLayout()

        # Tiles directory
        tiles_layout = QHBoxLayout()
        self.stitch_tiles_dir = QLineEdit("data/output/googletiles_l17")
        tiles_btn = QPushButton("浏览")
        tiles_btn.setMaximumWidth(70)
        tiles_btn.clicked.connect(lambda: self._select_dir(self.stitch_tiles_dir))
        tiles_layout.addWidget(self.stitch_tiles_dir)
        tiles_layout.addWidget(tiles_btn)
        form_layout.addRow("瓦片目录:", tiles_layout)

        # Output directory
        out_layout = QHBoxLayout()
        self.stitch_output = QLineEdit("data/output/composited")
        out_btn = QPushButton("浏览")
        out_btn.setMaximumWidth(70)
        out_btn.clicked.connect(lambda: self._select_dir(self.stitch_output))
        out_layout.addWidget(self.stitch_output)
        out_layout.addWidget(out_btn)
        form_layout.addRow("输出目录:", out_layout)

        # Zoom
        self.stitch_zoom = QSpinBox()
        self.stitch_zoom.setRange(0, 20)
        self.stitch_zoom.setValue(18)
        form_layout.addRow("缩放级别:", self.stitch_zoom)

        layout.addLayout(form_layout)

        # Stitch button
        stitch_btn = QPushButton("仅拼接瓦片 (无VRT)")
        stitch_btn.setMinimumHeight(32)
        stitch_btn.clicked.connect(self._start_stitching)
        layout.addWidget(stitch_btn)

        return group

    def _build_filter_group(self) -> QGroupBox:
        """Build tile filtering GroupBox."""
        group = QGroupBox("4. 瓦片清洗")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        form_layout = QFormLayout()

        # Input directory
        in_layout = QHBoxLayout()
        self.filter_input = QLineEdit("data/output/composited/images")
        in_btn = QPushButton("浏览")
        in_btn.setMaximumWidth(70)
        in_btn.clicked.connect(lambda: self._select_dir(self.filter_input))
        in_layout.addWidget(self.filter_input)
        in_layout.addWidget(in_btn)
        form_layout.addRow("输入目录:", in_layout)

        # Output directory
        out_layout = QHBoxLayout()
        self.filter_output = QLineEdit("data/output/filtered_images")
        out_btn = QPushButton("浏览")
        out_btn.setMaximumWidth(70)
        out_btn.clicked.connect(lambda: self._select_dir(self.filter_output))
        out_layout.addWidget(self.filter_output)
        out_layout.addWidget(out_btn)
        form_layout.addRow("输出目录:", out_layout)

        # Threshold (Black pixel ratio)
        self.filter_threshold = QDoubleSpinBox()
        self.filter_threshold.setRange(0.0, 1.0)
        self.filter_threshold.setSingleStep(0.01)
        self.filter_threshold.setValue(0.0625) # 1/16
        self.filter_threshold.setDecimals(4)
        form_layout.addRow("黑边阈值 (默认1/16):", self.filter_threshold)

        layout.addLayout(form_layout)

        # Filter button
        filter_btn = QPushButton("执行清洗 (复制有效瓦片)")
        filter_btn.setMinimumHeight(32)
        filter_btn.clicked.connect(self._start_filtering)
        layout.addWidget(filter_btn)

        return group

    def _select_bbox_vector(self) -> None:
        """Select vector file for BBox."""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择矢量文件", "",
            "Vector Files (*.geojson *.shp *.gpkg *.kml);;All Files (*)"
        )
        if path:
            self.bbox_vector_file.setText(path)
            self._load_bbox_from_vector()

    def _load_bbox_from_vector(self) -> None:
        """Load bbox from vector file."""
        path = self.bbox_vector_file.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "错误", "请先选择有效的矢量文件")
            return

        try:
            import geopandas as gpd
            # Show wait cursor
            from PyQt5.QtWidgets import QApplication
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            gdf = gpd.read_file(path)
            # Ensure WGS84
            if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            
            bounds = gdf.total_bounds # [minx, miny, maxx, maxy]
            
            self.bbox_left.setValue(bounds[0])
            self.bbox_bottom.setValue(bounds[1])
            self.bbox_right.setValue(bounds[2])
            self.bbox_top.setValue(bounds[3])
            
            self._log(f"[BBox] 已加载范围: {bounds}")
            QMessageBox.information(self, "成功", f"已从文件读取范围:\n{path}\n\nBBox: {bounds}")
            
        except Exception as e:
            self._log(f"[BBox] 加载失败: {e}")
            QMessageBox.critical(self, "错误", f"读取矢量文件失败:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _select_dir(self, line_edit: QLineEdit) -> None:
        """Select directory."""
        path = QFileDialog.getExistingDirectory(self, "选择目录", line_edit.text())
        if path:
            line_edit.setText(path)

    def _select_clean_input(self) -> None:
        """Select input file for cleaning."""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择OSM数据文件", "",
            "GeoJSON Files (*.geojson);;All Files (*)"
        )
        if path:
            self.clean_input.setText(path)

    def _select_save_file(self, line_edit: QLineEdit) -> None:
        """Select save file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "保存为", line_edit.text(),
            "GeoJSON Files (*.geojson)"
        )
        if path:
            line_edit.setText(path)

    def _select_stitch_vector(self) -> None:
        """Select vector file for stitching."""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择矢量", "",
            "GeoJSON Files (*.geojson);;Shapefile (*.shp)"
        )
        if path:
            self.stitch_vector.setText(path)

    def _log(self, msg: str) -> None:
        """Append to log."""
        self.log_text.append(msg)
        self.log_text.ensureCursorVisible()

    def _start_download(self) -> None:
        dtype_key = self.download_type_combo.currentData()
        from config.download_types import DOWNLOAD_TYPES
        dt = DOWNLOAD_TYPES.get(dtype_key)
        if dt is None:
            QMessageBox.warning(self, "错误", "请选择下载类型")
            return

        # 读取bbox
        bbox = (
            float(self.bbox_left.value()),
            float(self.bbox_bottom.value()),
            float(self.bbox_right.value()),
            float(self.bbox_top.value()),
        )
        if not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
            bbox = (116.3, 39.8, 116.5, 39.9)
            QMessageBox.information(self, "提示", "BBox无效，已使用默认演示范围: 116.3,39.8,116.5,39.9")
        out_dir = self.download_output.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "错误", "请指定输出目录")
            return

        zoom = dt.default_zoom
        
        # Calculate tile count and estimate time
        if dt.dtype != "vector":
            tiles = list(mercantile.tiles(bbox[0], bbox[1], bbox[2], bbox[3], [zoom]))
            total_tiles = len(tiles)
            
            # Estimation logic: 
            # Assume ~0.5s per tile with 4 threads (conservative estimate including retries/sleep)
            # 4 threads -> effective rate ~8 tiles/sec? 
            # Let's be conservative: 4 workers, each takes 1s per tile (network+sleep) -> 4 tiles/sec
            tiles_per_sec = 4
            est_seconds = total_tiles / tiles_per_sec
            
            if est_seconds < 60:
                est_time_str = f"{est_seconds:.1f} 秒"
            elif est_seconds < 3600:
                est_time_str = f"{est_seconds/60:.1f} 分钟"
            else:
                est_time_str = f"{est_seconds/3600:.1f} 小时"
                
            msg = (
                f"准备下载:\n"
                f"类型: {dt.name}\n"
                f"Zoom: {zoom}\n"
                f"瓦片数量: {total_tiles}\n"
                f"预计耗时: {est_time_str}\n\n"
                f"是否继续?"
            )
            
            reply = QMessageBox.question(self, "下载确认", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                return

        self._log(f"[下载] 类型={dt.name}, zoom={zoom}")
        self._log(f"[下载] BBox={bbox}")
        self._log(f"[下载] 输出目录={out_dir}")

        # 启动后台下载
        self.download_worker = DownloadWorker(dtype_key, bbox, out_dir, zoom)
        self.download_worker.log.connect(self._log)
        def on_ok(msg):
            self._log(f"[下载] ✓ {msg}")
            QMessageBox.information(self, "完成", msg)
            self.download_btn.setEnabled(True)
        def on_fail(msg):
            self._log(f"[下载] ✗ {msg}")
            QMessageBox.critical(self, "错误", msg)
            self.download_btn.setEnabled(True)
        self.download_worker.finished.connect(on_ok)
        self.download_worker.failed.connect(on_fail)
        self.download_btn.setEnabled(False)
        self.download_worker.start()

    def _extract_trunk_roads(self) -> None:
        """Extract trunk roads."""
        file_path = self.clean_input.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "错误", "请选择有效的输入文件")
            return

        try:
            self._log(f"[清洗] 加载文件: {file_path}")
            # Use worker for cleaning
            self.clean_worker = CleanWorker(file_path)
            self.clean_worker.log.connect(self._log)
            
            def on_ok(trunk_roads):
                self.cleaner = self.clean_worker.cleaner # Keep reference to cleaner
                self._log(f"[清洗] ✓ 提取完成，共{len(trunk_roads)}条主干道")
                QMessageBox.information(self, "完成", f"提取了{len(trunk_roads)}条主干道")
                
            def on_fail(msg):
                self._log(f"[清洗] ✗ 错误: {msg}")
                QMessageBox.critical(self, "错误", msg)
                
            self.clean_worker.finished.connect(on_ok)
            self.clean_worker.failed.connect(on_fail)
            self.clean_worker.start()
            
        except Exception as e:
            self._log(f"[清洗] ✗ 错误: {e}")
            QMessageBox.critical(self, "错误", str(e))

    def _save_cleaned(self) -> None:
        """Save cleaned data."""
        if not self.cleaner or not hasattr(self.cleaner, 'trunk_roads'):
            QMessageBox.warning(self, "错误", "请先提取主干道")
            return

        output_path = self.clean_output.text().strip()
        if not output_path:
            QMessageBox.warning(self, "错误", "请指定输出文件")
            return

        try:
            self.cleaner.save(output_path)
            self._log(f"[清洗] ✓ 已保存到: {output_path}")
            QMessageBox.information(self, "完成", f"已保存到:\n{output_path}")
        except Exception as e:
            self._log(f"[清洗] ✗ 保存失败: {e}")
            QMessageBox.critical(self, "错误", str(e))

    def _start_stitching(self) -> None:
        """Start tile stitching."""
        tiles_dir = self.stitch_tiles_dir.text().strip()
        output_dir = self.stitch_output.text().strip()

        if not tiles_dir or not os.path.exists(tiles_dir):
            QMessageBox.warning(self, "错误", "请选择有效的瓦片目录")
            return

        if not output_dir:
            QMessageBox.warning(self, "错误", "请指定输出目录")
            return

        try:
            self._log(f"[拼接] 开始处理...")
            self._log(f"[拼接]   瓦片: {tiles_dir}")
            
            # Use worker for stitching
            self.stitch_worker = StitchWorker(
                tiles_dir=tiles_dir,
                output_dir=output_dir,
                zoom_level=self.stitch_zoom.value()
            )
            self.stitch_worker.log.connect(self._log)
            
            def on_ok(msg):
                self._log(f"[拼接] ✓ {msg}")
                QMessageBox.information(self, "完成", f"瓦片拼接完成！\n输出目录: {output_dir}")
                
            def on_fail(msg):
                self._log(f"[拼接] ✗ 错误: {msg}")
                QMessageBox.critical(self, "错误", msg)
                
            self.stitch_worker.finished.connect(on_ok)
            self.stitch_worker.failed.connect(on_fail)
            self.stitch_worker.start()

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._log(f"[拼接] ✗ 错误: {e}")
            QMessageBox.critical(self, "错误", str(e))
            
    def _start_filtering(self) -> None:
        """Start tile filtering."""
        input_dir = self.filter_input.text().strip()
        output_dir = self.filter_output.text().strip()
        threshold = self.filter_threshold.value()

        if not input_dir or not os.path.exists(input_dir):
            QMessageBox.warning(self, "错误", "请选择有效的输入目录")
            return

        if not output_dir:
            QMessageBox.warning(self, "错误", "请指定输出目录")
            return

        try:
            self._log(f"[清洗] 开始过滤无效瓦片...")
            self._log(f"[清洗]   输入: {input_dir}")
            self._log(f"[清洗]   输出: {output_dir}")
            self._log(f"[清洗]   黑边阈值: {threshold}")
            
            self.filter_worker = FilterWorker(input_dir, output_dir, threshold)
            self.filter_worker.log.connect(self._log)
            self.filter_worker.finished.connect(lambda msg: QMessageBox.information(self, "完成", msg))
            self.filter_worker.failed.connect(lambda msg: QMessageBox.critical(self, "错误", msg))
            
            self.filter_worker.start()
            
        except Exception as e:
            self._log(f"[清洗] ✗ 错误: {e}")
            QMessageBox.critical(self, "错误", str(e))

class FilterWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, input_dir, output_dir, threshold):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.threshold = threshold

    def run(self):
        try:
            filter_tool = TileFilter(self.input_dir, self.output_dir, self.threshold)
            
            def callback(msg):
                self.log.emit(f"[清洗] {msg}")
                
            total, copied, skipped = filter_tool.process(callback)
            self.finished.emit(f"清洗完成！\n总计: {total}\n保留: {copied}\n剔除: {skipped}")
        except Exception as e:
            self.failed.emit(str(e))

class DownloadWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, dtype_key: str, bbox: tuple, out_dir: str, zoom: int) -> None:
        super().__init__()
        self.dtype_key = dtype_key
        self.bbox = bbox
        self.out_dir = out_dir
        self.zoom = zoom
        self._is_running = True
        self._downloader = None

    def stop(self):
        """Request stop."""
        self._is_running = False
        if self._downloader:
            self._downloader.stop()
        self.requestInterruption()
        self.wait(2000) # Wait up to 2s
        if self.isRunning():
            self.terminate() # Force kill if stuck

    def run(self) -> None:
        try:
            if not self._is_running: return
            
            from config.download_types import DOWNLOAD_TYPES
            dt = DOWNLOAD_TYPES[self.dtype_key]
            if dt.dtype == "vector":
                output = os.path.join(self.out_dir, "osm_features.geojson")
                self.log.emit(f"[OSM] bbox={self.bbox}, output={output}")
                # OSM fetcher is synchronous, hard to interrupt gracefully without refactoring core
                if self._is_running:
                    res = fetch_osm_features(
                        vector_path=None,
                        bbox=f"{self.bbox[0]},{self.bbox[1]},{self.bbox[2]},{self.bbox[3]}",
                        output_path=output,
                        data_types=["road"],
                    )
                    if res is None:
                        self.failed.emit("未下载到任何要素")
                    else:
                        self.finished.emit(f"OSM下载完成，共{len(res)}条要素")
            else:
                valid_urls = detect_working_urls(dt.url_options)
                if not valid_urls:
                    valid_urls = dt.url_options
                
                # Use list if multiple URLs are available for load balancing
                url_template = valid_urls if len(valid_urls) > 1 else valid_urls[0]

                tiles_dir = os.path.join(self.out_dir, f"{self.dtype_key}_tiles_z{self.zoom}")
                os.makedirs(tiles_dir, exist_ok=True)
                
                log_msg = f"Multiple URLs ({len(url_template)})" if isinstance(url_template, list) else url_template
                self.log.emit(f"[Tiles] zoom={self.zoom} url={log_msg}")
                
                self._downloader = TileDownloader(
                    url_template=url_template,
                    output_base_dir=tiles_dir,
                    max_workers=dt.max_workers,
                    per_thread_min_sleep=dt.per_thread_min_sleep,
                    per_thread_max_sleep=dt.per_thread_max_sleep,
                    max_retries=dt.max_retries,
                    backoff_factor=dt.backoff_factor,
                    request_timeout=dt.request_timeout,
                )
                
                def callback(msg):
                    self.log.emit(f"[Tiles] {msg}")
                    
                self._downloader.download_tiles_from_bbox(self.bbox, self.zoom, callback=callback)
                
                if self._is_running:
                    self.finished.emit(f"瓦片下载完成，目录: {tiles_dir}")
                else:
                    self.log.emit("[Tiles] 下载已停止")
        except Exception as e:
            if self._is_running:
                logger.exception("Download worker failed")
                self.failed.emit(str(e))

class CleanWorker(QThread):
    finished = Signal(object) # Returns trunk_roads
    failed = Signal(str)
    log = Signal(str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.cleaner = None
        
    def run(self):
        try:
            self.cleaner = OSMCleaner(self.file_path)
            
            def callback(msg):
                self.log.emit(f"[清洗] {msg}")
                
            trunk_roads = self.cleaner.extract_trunk_roads(callback=callback)
            self.finished.emit(trunk_roads)
        except Exception as e:
            self.failed.emit(str(e))

class StitchWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)
    log = Signal(str)
    
    def __init__(self, tiles_dir, output_dir, zoom_level):
        super().__init__()
        self.tiles_dir = tiles_dir
        self.output_dir = output_dir
        self.zoom_level = zoom_level
        
    def run(self):
        try:
            compositor = TileCompositor(
                tiles_dir=self.tiles_dir,
                vector_path=None,
                output_dir=self.output_dir,
                zoom_level=self.zoom_level
            )
            
            def callback(msg):
                self.log.emit(f"[拼接] {msg}")
                
            compositor.process_all(generate_vrt=False, callback=callback)
            self.finished.emit("拼接完成")
        except Exception as e:
            self.failed.emit(str(e))
