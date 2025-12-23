"""Data Preprocessing Tab - integrates Download, Cleaning, and Stitching."""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
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

        # ============ GroupBox 1: 数据下载 ============
        download_group = self._build_download_group()
        main_layout.addWidget(download_group)

        # ============ GroupBox 2: 数据清洗 ============
        clean_group = self._build_clean_group()
        main_layout.addWidget(clean_group)

        # ============ GroupBox 3: 瓦片拼接 ============
        stitch_group = self._build_stitch_group()
        main_layout.addWidget(stitch_group)

        # ============ Shared Log ============
        log_label = QLabel("操作日志:")
        log_font = QFont()
        log_font.setBold(True)
        log_label.setFont(log_font)
        main_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
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

        # Range input (simplified - bbox only)
        range_layout = QFormLayout()
        bbox_layout = QHBoxLayout()
        
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
        
        bbox_layout.addWidget(QLabel("Left:"))
        bbox_layout.addWidget(self.bbox_left)
        bbox_layout.addWidget(QLabel("Bottom:"))
        bbox_layout.addWidget(self.bbox_bottom)
        bbox_layout.addWidget(QLabel("Right:"))
        bbox_layout.addWidget(self.bbox_right)
        bbox_layout.addWidget(QLabel("Top:"))
        bbox_layout.addWidget(self.bbox_top)
        
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

        # Vector file
        vec_layout = QHBoxLayout()
        self.stitch_vector = QLineEdit()
        self.stitch_vector.setPlaceholderText("选择矢量文件")
        vec_btn = QPushButton("浏览")
        vec_btn.setMaximumWidth(70)
        vec_btn.clicked.connect(self._select_stitch_vector)
        vec_layout.addWidget(self.stitch_vector)
        vec_layout.addWidget(vec_btn)
        form_layout.addRow("矢量文件:", vec_layout)

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
        stitch_btn = QPushButton("拼接瓦片并切割矢量")
        stitch_btn.setMinimumHeight(32)
        stitch_btn.clicked.connect(self._start_stitching)
        layout.addWidget(stitch_btn)

        return group

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
            self.cleaner = OSMCleaner(file_path)
            self.cleaner.extract_trunk_roads()
            self._log(f"[清洗] ✓ 提取完成，共{len(self.cleaner.trunk_roads)}条主干道")
            QMessageBox.information(self, "完成", f"提取了{len(self.cleaner.trunk_roads)}条主干道")
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
        vector_file = self.stitch_vector.text().strip()
        output_dir = self.stitch_output.text().strip()

        if not tiles_dir or not os.path.exists(tiles_dir):
            QMessageBox.warning(self, "错误", "请选择有效的瓦片目录")
            return

        if not vector_file or not os.path.exists(vector_file):
            QMessageBox.warning(self, "错误", "请选择有效的矢量文件")
            return

        if not output_dir:
            QMessageBox.warning(self, "错误", "请指定输出目录")
            return

        try:
            self._log(f"[拼接] 开始处理...")
            self._log(f"[拼接]   瓦片: {tiles_dir}")
            self._log(f"[拼接]   矢量: {vector_file}")
            
            self.compositor = TileCompositor(
                tiles_dir=tiles_dir,
                vector_path=vector_file,
                output_dir=output_dir,
                zoom_level=self.stitch_zoom.value()
            )
            
            self.compositor.process_all()
            self._log(f"[拼接] ✓ 完成！")
            QMessageBox.information(self, "完成", f"瓦片拼接完成！\n输出目录: {output_dir}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._log(f"[拼接] ✗ 错误: {e}")
            QMessageBox.critical(self, "错误", str(e))
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

    def run(self) -> None:
        try:
            from config.download_types import DOWNLOAD_TYPES
            dt = DOWNLOAD_TYPES[self.dtype_key]
            if dt.dtype == "vector":
                output = os.path.join(self.out_dir, "osm_features.geojson")
                self.log.emit(f"[OSM] bbox={self.bbox}, output={output}")
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
                
                downloader = TileDownloader(
                    url_template=url_template,
                    output_base_dir=tiles_dir,
                    max_workers=dt.max_workers,
                    per_thread_min_sleep=dt.per_thread_min_sleep,
                    per_thread_max_sleep=dt.per_thread_max_sleep,
                    max_retries=dt.max_retries,
                    backoff_factor=dt.backoff_factor,
                    request_timeout=dt.request_timeout,
                )
                downloader.download_tiles_from_bbox(self.bbox, self.zoom)
                self.finished.emit(f"瓦片下载完成，目录: {tiles_dir}")
        except Exception as e:
            logger.exception("Download worker failed")
            self.failed.emit(str(e))
