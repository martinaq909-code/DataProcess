from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFileDialog,
    QMessageBox, QTextEdit, QFrame
)

# Import core functions
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.mask2labelme import mask_to_labelme
from core.labelme2mask import json_to_mask

class ConversionWorker(QThread):
    """Worker thread for running conversions to avoid freezing UI."""
    finished = Signal(str)
    error = Signal(str)
    
    def __init__(self, task_type, **kwargs):
        super().__init__()
        self.task_type = task_type
        self.kwargs = kwargs
        
    def run(self):
        try:
            if self.task_type == "mask2labelme":
                mask_to_labelme(
                    self.kwargs['mask_dir'],
                    self.kwargs['output_dir'],
                    self.kwargs['img_dir']
                )
                self.finished.emit(f"Mask to LabelMe conversion completed.\nSaved to: {self.kwargs['output_dir']}")
                
            elif self.task_type == "labelme2mask":
                json_to_mask(
                    self.kwargs['json_dir'],
                    self.kwargs['output_dir']
                )
                self.finished.emit(f"LabelMe to Mask conversion completed.\nSaved to: {self.kwargs['output_dir']}")
                
        except Exception as e:
            import traceback
            error_msg = f"Error during {self.task_type}:\n{str(e)}\n\n{traceback.format_exc()}"
            self.error.emit(error_msg)


class MaskConversionTab(QWidget):
    """Tab for converting between Masks and LabelMe JSONs, and launching LabelMe."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ============ Title ============
        title = QLabel("Mask格式转换")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        desc = QLabel("提供 Binary Mask 与 LabelMe JSON 的相互转换。")
        desc.setStyleSheet("color: #666;")
        main_layout.addWidget(desc)
        
        # ============ Section 1: Mask -> LabelMe ============
        group_m2l = QGroupBox("Mask 转 LabelMe JSON")
        layout_m2l = QFormLayout(group_m2l)
        layout_m2l.setSpacing(10)
        
        self.edit_m2l_mask_dir = self._add_browse_row(layout_m2l, "Mask 目录:", "data/output/masks")
        self.edit_m2l_img_dir = self._add_browse_row(layout_m2l, "影像目录:", "data/output/images")
        self.edit_m2l_out_dir = self._add_browse_row(layout_m2l, "输出 JSON 目录:", "data/output/labelme_json")
        
        btn_run_m2l = QPushButton("执行转换 (Mask -> JSON)")
        btn_run_m2l.clicked.connect(self._run_mask2labelme)
        btn_run_m2l.setStyleSheet("background-color: #0d7377; color: white; padding: 6px;")
        layout_m2l.addRow(btn_run_m2l)
        
        main_layout.addWidget(group_m2l)

        # ============ Section 2: LabelMe -> Mask ============
        group_l2m = QGroupBox("LabelMe JSON 转 Mask")
        layout_l2m = QFormLayout(group_l2m)
        layout_l2m.setSpacing(10)
        
        self.edit_l2m_json_dir = self._add_browse_row(layout_l2m, "JSON 目录:", "data/output/labelme_json")
        self.edit_l2m_out_dir = self._add_browse_row(layout_l2m, "输出 Mask 目录:", "data/output/final_masks")
        
        btn_run_l2m = QPushButton("执行转换 (JSON -> Mask)")
        btn_run_l2m.clicked.connect(self._run_labelme2mask)
        btn_run_l2m.setStyleSheet("background-color: #0d7377; color: white; padding: 6px;")
        layout_l2m.addRow(btn_run_l2m)
        
        main_layout.addWidget(group_l2m)

        # ============ Log Area ============
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("操作日志将显示在这里...")
        main_layout.addWidget(self.log_area)
        
    def _add_browse_row(self, layout, label_text, default_path=""):
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        
        line_edit = QLineEdit()
        line_edit.setText(default_path)
        
        btn_browse = QPushButton("浏览")
        btn_browse.setFixedWidth(60)
        btn_browse.clicked.connect(lambda: self._browse_dir(line_edit))
        
        h_layout.addWidget(line_edit)
        h_layout.addWidget(btn_browse)
        
        layout.addRow(label_text, container)
        return line_edit

    def _browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择目录", line_edit.text())
        if d:
            line_edit.setText(d)

    def _log(self, msg):
        self.log_area.append(msg)

    def _run_mask2labelme(self):
        mask_dir = self.edit_m2l_mask_dir.text()
        img_dir = self.edit_m2l_img_dir.text()
        out_dir = self.edit_m2l_out_dir.text()
        
        if not os.path.exists(mask_dir) or not os.path.exists(img_dir):
            QMessageBox.warning(self, "错误", "输入目录不存在！")
            return
            
        self.worker = ConversionWorker("mask2labelme", mask_dir=mask_dir, img_dir=img_dir, output_dir=out_dir)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        
        self._log("正在执行 Mask -> LabelMe 转换...")
        self.worker.start()

    def _run_labelme2mask(self):
        json_dir = self.edit_l2m_json_dir.text()
        out_dir = self.edit_l2m_out_dir.text()
        
        if not os.path.exists(json_dir):
            QMessageBox.warning(self, "错误", "输入目录不存在！")
            return
            
        self.worker = ConversionWorker("labelme2mask", json_dir=json_dir, output_dir=out_dir)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        
        self._log("正在执行 LabelMe -> Mask 转换...")
        self.worker.start()

    def _on_finished(self, msg):
        self._log(msg)
        QMessageBox.information(self, "完成", msg)

    def _on_error(self, msg):
        self._log(f"错误: {msg}")
        QMessageBox.critical(self, "错误", msg)
