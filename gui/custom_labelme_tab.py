from __future__ import annotations

import os
import sys
import glob
import json
import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QPointF, QSettings
from PyQt5.QtGui import QPixmap, QColor, QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, 
    QScrollArea, QLabel, QMenu, QDialog, QLineEdit, QFormLayout, QDialogButtonBox,
    QTabWidget, QAction
)

logger = logging.getLogger(__name__)

# Try to import labelme components from the environment
# We defer import to avoid early QWidget instantiation or Qt conflicts
Canvas = None
Shape = None

class LoadDirectoriesDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Load Directories")
        self.resize(500, 200)
        self.settings = settings
        
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        
        # Image Directory
        self.img_dir_edit = QLineEdit()
        self.btn_img_dir = QPushButton("Browse")
        self.btn_img_dir.clicked.connect(lambda: self.browse_dir(self.img_dir_edit, "last_img_dir"))
        h_layout_1 = QHBoxLayout()
        h_layout_1.addWidget(self.img_dir_edit)
        h_layout_1.addWidget(self.btn_img_dir)
        self.form_layout.addRow("Image Dir:", h_layout_1)
        
        # JSON Directory
        self.json_dir_edit = QLineEdit()
        self.btn_json_dir = QPushButton("Browse")
        self.btn_json_dir.clicked.connect(lambda: self.browse_dir(self.json_dir_edit, "last_json_dir"))
        h_layout_2 = QHBoxLayout()
        h_layout_2.addWidget(self.json_dir_edit)
        h_layout_2.addWidget(self.btn_json_dir)
        self.form_layout.addRow("JSON Dir:", h_layout_2)
        
        # Save Directory
        self.save_dir_edit = QLineEdit()
        self.btn_save_dir = QPushButton("Browse")
        self.btn_save_dir.clicked.connect(lambda: self.browse_dir(self.save_dir_edit, "last_save_dir"))
        h_layout_3 = QHBoxLayout()
        h_layout_3.addWidget(self.save_dir_edit)
        h_layout_3.addWidget(self.btn_save_dir)
        self.form_layout.addRow("Save Dir:", h_layout_3)
        
        self.layout.addLayout(self.form_layout)
        
        # Dialog Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        # Restore last used paths
        if self.settings:
            self.img_dir_edit.setText(self.settings.value("last_img_dir", ""))
            self.json_dir_edit.setText(self.settings.value("last_json_dir", ""))
            self.save_dir_edit.setText(self.settings.value("last_save_dir", ""))

    def browse_dir(self, line_edit, setting_key):
        start_dir = line_edit.text() if line_edit.text() else ""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory", start_dir)
        if dir_path:
            line_edit.setText(dir_path)
            if self.settings:
                self.settings.setValue(setting_key, dir_path)

    def get_directories(self):
        return self.img_dir_edit.text(), self.json_dir_edit.text(), self.save_dir_edit.text()

class CustomLabelMeTab(QWidget):
    """Integrated LabelMe Tab for mask refinement."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        global Canvas, Shape
        if Canvas is None:
            os.environ["QT_API"] = "pyqt5"
            try:
                # Patch numpy.bool for compatibility with older libraries in newer numpy environments
                import numpy as np
                if not hasattr(np, 'bool'):
                    np.bool = bool

                from labelme.widgets import Canvas as LCanvas
                from labelme.shape import Shape as LShape
                Canvas = LCanvas
                Shape = LShape
            except ImportError as e:
                logger.error(f"Error: 'labelme' module not found or failed to import. Details: {e}")
        
        if Canvas is None:
            self._build_error_ui()
            return

        # Settings
        self.settings = QSettings("CustomLabelme", "MaskRefinement")
        
        # UI Components
        self.layout = QVBoxLayout(self)
        
        # Toolbar / Buttons
        self.button_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Directories")
        self.btn_prev = QPushButton("Prev")
        self.btn_next = QPushButton("Next")
        self.btn_save = QPushButton("Save")
        self.btn_create_poly = QPushButton("Create Polygon")
        self.btn_edit_mode = QPushButton("Edit Mode")
        
        self.button_layout.addWidget(self.btn_load)
        self.button_layout.addWidget(self.btn_prev)
        self.button_layout.addWidget(self.btn_next)
        self.button_layout.addWidget(self.btn_save)
        self.button_layout.addWidget(self.btn_create_poly)
        self.button_layout.addWidget(self.btn_edit_mode)
        
        self.lbl_file_info = QLabel("No file loaded")
        self.button_layout.addWidget(self.lbl_file_info)
        self.button_layout.addStretch()
        
        self.layout.addLayout(self.button_layout)
        
        # Canvas and ScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        
        # Initialize Canvas
        try:
            self.canvas = Canvas(epsilon=10.0, double_click="close")
            self.canvas.setFocusPolicy(Qt.StrongFocus)
            
            self.scroll_area.setWidget(self.canvas)
            self.layout.addWidget(self.scroll_area)
        except Exception as e:
            print(f"Error initializing Canvas: {e}")
            # Remove partial UI if needed, but easier to just show error overlay
            self._build_error_ui(f"Error initializing LabelMe Canvas:\n{e}\n\nThis may be due to PySide6/PyQt5 conflict.")
            return

        # State
        self.image_files = []
        self.current_index = -1
        self.img_dir = None
        self.json_dir = None
        self.save_dir = None
        self.image_path = None
        
        # Connections
        self.btn_load.clicked.connect(self.show_load_dialog)
        self.btn_prev.clicked.connect(self.load_prev_image)
        self.btn_next.clicked.connect(self.load_next_image)
        self.btn_save.clicked.connect(self.save_current_file)
        self.btn_create_poly.clicked.connect(self.set_create_mode)
        self.btn_edit_mode.clicked.connect(self.set_edit_mode)
        
        # Canvas Signals
        self.canvas.zoomRequest.connect(self.zoom_request)
        self.canvas.scrollRequest.connect(self.scroll_request)
        self.canvas.newShape.connect(self.new_shape)
        
        # Context Menu
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.show_context_menu)

        # Actions & Shortcuts
        self.action_delete = QAction("Delete", self)
        self.action_delete.setShortcuts([QKeySequence.Delete, QKeySequence("D")])
        self.action_delete.triggered.connect(self.delete_selection)
        self.addAction(self.action_delete)
        
        # Note: Canvas doesn't inherit addAction directly in PySide6 same way as PyQt5 potentially, 
        # but adding to self (QWidget) should work for shortcuts if widget has focus.
        # Ideally we add to canvas too.
        self.canvas.addAction(self.action_delete)

        self.action_prev = QAction("Previous Image", self)
        self.action_prev.setShortcut(QKeySequence("Q"))
        self.action_prev.triggered.connect(self.load_prev_image)
        self.addAction(self.action_prev)
        self.canvas.addAction(self.action_prev)

        self.action_next = QAction("Next Image", self)
        self.action_next.setShortcut(QKeySequence("E"))
        self.action_next.triggered.connect(self.load_next_image)
        self.addAction(self.action_next)
        self.canvas.addAction(self.action_next)

        self.action_create_poly = QAction("Create Polygon", self)
        self.action_create_poly.setShortcut(QKeySequence("A"))
        self.action_create_poly.triggered.connect(self.set_create_mode)
        self.addAction(self.action_create_poly)
        self.canvas.addAction(self.action_create_poly)

        self.action_undo = QAction("Undo", self)
        self.action_undo.setShortcut(QKeySequence.Undo)
        self.action_undo.triggered.connect(self.undo_last_action)
        self.addAction(self.action_undo)
        self.canvas.addAction(self.action_undo)

        self.action_add_point = QAction("Add Point", self)
        self.action_add_point.setShortcut(QKeySequence("S"))
        self.action_add_point.triggered.connect(self.add_point_to_edge)
        self.addAction(self.action_add_point)
        self.canvas.addAction(self.action_add_point)

        # Attempt to auto-load if settings exist
        last_img_dir = self.settings.value("last_img_dir")
        last_json_dir = self.settings.value("last_json_dir")
        last_save_dir = self.settings.value("last_save_dir")
        
        if last_img_dir and os.path.exists(last_img_dir):
            self.load_directories(last_img_dir, last_json_dir, last_save_dir)

    def _build_error_ui(self, message=None):
        # Clear existing layout if any
        if self.layout():
            QWidget().setLayout(self.layout()) # Hack to delete layout
        
        layout = QVBoxLayout(self)
        if message is None:
            message = "Error: 'labelme' library not found.\nPlease install it using: pip install labelme"
        
        msg = QLabel(message)
        msg.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg)

    def show_load_dialog(self):
        dialog = LoadDirectoriesDialog(self, self.settings)
        if dialog.exec_() == QDialog.Accepted:
            img_dir, json_dir, save_dir = dialog.get_directories()
            if not img_dir or not os.path.exists(img_dir):
                QMessageBox.warning(self, "Error", "Image directory is required and must exist.")
                return

            self.settings.setValue("last_img_dir", img_dir)
            self.settings.setValue("last_json_dir", json_dir)
            self.settings.setValue("last_save_dir", save_dir)
            self.load_directories(img_dir, json_dir, save_dir)

    def load_directories(self, img_dir, json_dir, save_dir):
        self.img_dir = img_dir
        self.json_dir = json_dir
        self.save_dir = save_dir
        
        # Find all images
        exts = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.JPG', '*.JPEG', '*.PNG', '*.BMP']
        self.image_files = []
        for ext in exts:
            self.image_files.extend(glob.glob(os.path.join(img_dir, ext)))
        self.image_files = sorted(list(set(self.image_files)))
        
        if not self.image_files:
            QMessageBox.warning(self, "Warning", "No images found in image directory.")
            return
            
        # Try to restore last file index
        last_file = self.settings.value("last_file")
        if last_file and last_file in self.image_files:
            self.current_index = self.image_files.index(last_file)
        else:
            self.current_index = 0
            
        self.load_image(self.image_files[self.current_index])

    def get_json_path(self, image_path, use_save_dir=False):
        basename = os.path.splitext(os.path.basename(image_path))[0]
        json_filename = basename + ".json"
        
        if use_save_dir and self.save_dir:
            return os.path.join(self.save_dir, json_filename)
        
        if self.json_dir and os.path.exists(os.path.join(self.json_dir, json_filename)):
            return os.path.join(self.json_dir, json_filename)
            
        img_dir_json = os.path.splitext(image_path)[0] + ".json"
        if os.path.exists(img_dir_json):
            return img_dir_json
            
        return img_dir_json

    def load_image(self, image_path):
        self.image_path = image_path
        self.settings.setValue("last_file", image_path)
        
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Error", f"Failed to load {image_path}")
            return
            
        self.canvas.loadPixmap(pixmap)
        
        # Fit image to window
        self.fit_window()
        
        # Load corresponding JSON
        target_json_path = None
        basename = os.path.splitext(os.path.basename(image_path))[0] + ".json"
        
        if self.save_dir and os.path.exists(os.path.join(self.save_dir, basename)):
            target_json_path = os.path.join(self.save_dir, basename)
        elif self.json_dir and os.path.exists(os.path.join(self.json_dir, basename)):
            target_json_path = os.path.join(self.json_dir, basename)
        elif os.path.exists(os.path.splitext(image_path)[0] + ".json"):
            target_json_path = os.path.splitext(image_path)[0] + ".json"
            
        if target_json_path and os.path.exists(target_json_path):
            self.load_json_file(target_json_path)
        else:
            self.canvas.loadShapes([]) 
            
        self.update_info()

    def fit_window(self):
        if not self.canvas.pixmap:
            return
        
        canvas_width = self.scroll_area.width()
        canvas_height = self.scroll_area.height()
        pixmap_width = self.canvas.pixmap.width()
        pixmap_height = self.canvas.pixmap.height()
        
        if pixmap_width > 0 and pixmap_height > 0:
            scale_w = canvas_width / pixmap_width
            scale_h = canvas_height / pixmap_height
            scale = min(scale_w, scale_h) * 0.95 
            self.canvas.scale = scale
            self.canvas.adjustSize()

    def load_json_file(self, json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            shapes = []
            for s in data.get('shapes', []):
                label = s.get('label', 'road')
                points = s.get('points', [])
                shape_type = s.get('shape_type', 'polygon')
                flags = s.get('flags', {})
                group_id = s.get('group_id')
                
                shape = Shape(label=label, shape_type=shape_type, group_id=group_id)
                for p in points:
                    shape.addPoint(QPointF(p[0], p[1]))
                shape.close()
                shapes.append(shape)
            
            self.canvas.loadShapes(shapes)
        except Exception as e:
            print(f"Error loading JSON: {e}")

    def save_current_file(self):
        if not self.image_path:
            return

        basename = os.path.splitext(os.path.basename(self.image_path))[0] + ".json"
        if self.save_dir:
            if not os.path.exists(self.save_dir):
                try:
                    os.makedirs(self.save_dir)
                except OSError:
                    QMessageBox.warning(self, "Error", f"Could not create save directory: {self.save_dir}")
                    return
            json_path = os.path.join(self.save_dir, basename)
        else:
            json_path = os.path.splitext(self.image_path)[0] + ".json"
        
        shapes_data = []
        for shape in self.canvas.shapes:
            points = [[p.x(), p.y()] for p in shape.points]
            shapes_data.append({
                "label": shape.label if shape.label else "road",
                "points": points,
                "group_id": shape.group_id,
                "shape_type": shape.shape_type,
                "flags": shape.flags
            })
        
        data = {
            "version": "5.0.1",
            "flags": {},
            "shapes": shapes_data,
            "imagePath": os.path.basename(self.image_path),
            "imageData": None,
            "imageHeight": self.canvas.pixmap.height(),
            "imageWidth": self.canvas.pixmap.width()
        }
        
        try:
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.exception("Failed to save JSON")
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def load_next_image(self):
        if not self.image_files:
            return
        self.save_current_file()
        self.current_index = (self.current_index + 1) % len(self.image_files)
        self.load_image(self.image_files[self.current_index])

    def load_prev_image(self):
        if not self.image_files:
            return
        self.save_current_file()
        self.current_index = (self.current_index - 1) % len(self.image_files)
        self.load_image(self.image_files[self.current_index])

    def update_info(self):
        if self.image_files:
            self.lbl_file_info.setText(f"{self.current_index + 1}/{len(self.image_files)}: {os.path.basename(self.image_path)}")
        else:
            self.lbl_file_info.setText("No file loaded")

    def undo_last_action(self):
        if self.canvas.isShapeRestorable:
            self.canvas.restoreShape()
            self.canvas.update()
            
    def add_point_to_edge(self):
        if self.canvas.hShape is None or self.canvas.hEdge is None:
             return
        if self.canvas.prevMovePoint:
             self.canvas.addPointToEdge()
             self.canvas.storeShapes()
             self.canvas.update()

    def set_create_mode(self):
        self.canvas.setEditing(False)
        self.canvas.createMode = "polygon"
        
    def set_edit_mode(self):
        self.canvas.setEditing(True)

    def new_shape(self):
        if self.canvas.shapes:
            last_shape = self.canvas.shapes[-1]
            if not last_shape.label:
                last_shape.label = "road"
        self.canvas.setEditing(True)

    def zoom_request(self, delta, pos):
        units = delta // (8 * 15)
        scale = 1.1
        if units > 0:
            self.canvas.scale *= scale
        else:
            self.canvas.scale /= scale
        self.canvas.adjustSize()
        
    def scroll_request(self, delta, orientation):
        units = -delta // (8 * 15)
        bar = self.scroll_area.verticalScrollBar() if orientation == Qt.Vertical else self.scroll_area.horizontalScrollBar()
        bar.setValue(bar.value() + bar.singleStep() * units)

    def delete_selection(self):
        if self.canvas.hVertex is not None and self.canvas.hShape is not None:
            shape = self.canvas.hShape
            index = self.canvas.hVertex
            if shape.canRemovePoint():
                 shape.removePoint(index)
                 self.canvas.storeShapes()
                 self.canvas.update()
            else:
                 QMessageBox.warning(self, "Warning", "Cannot remove point: Polygon must have at least 3 points.")
            return

        if self.canvas.selectedShapes:
            self.canvas.deleteSelected()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        action_delete = QAction("Delete", self)
        action_delete.triggered.connect(self.delete_selection)
        
        if self.canvas.selectedShapes or self.canvas.hVertex is not None:
            menu.addAction(self.action_delete)
            
        menu.exec_(self.canvas.mapToGlobal(pos))
