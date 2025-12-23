"""GUI application - simplified version with 3 tabs."""
from __future__ import annotations

import sys
import os
import warnings
from pathlib import Path

# Suppress warnings about np.bool which is deprecated/removed in newer numpy versions
# but still used by older libraries like labelme
warnings.filterwarnings("ignore", category=FutureWarning, message=".*np.bool.*")
# AttributeError is not a Warning subclass, so we cannot filter it with warnings module.
# The previous AttributeError was a hard crash, not a warning, and it has been fixed by the patch.
# warnings.filterwarnings("ignore", category=AttributeError, message=".*np.bool.*")

# Force qtpy (used by labelme) to use PyQt5
os.environ["QT_API"] = "pyqt5"
# Also force matplotlib backend via env var, which is often more robust
os.environ["MPLBACKEND"] = "Agg"

# Import sys and os first
import sys
import os

# Important: Initialize QApplication early to prevent "Must construct a QApplication before a QWidget" error
# This must happen before any potential QWidget initialization in imported modules
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget

# Ensure app instance exists
if not QApplication.instance():
    # Keep reference to avoid garbage collection
    _app = QApplication(sys.argv)
    _app.setStyle('Fusion')

# IMPORTANT: Import PyQt5 ONLY AFTER setting matplotlib backend
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

# Import tabs
# We defer imports of tabs until run_gui to avoid early initialization issues
# sys.path.insert(0, str(Path(__file__).parent.parent))
# from gui.datapreprocessing_tab import DataPreprocessingTab
# from gui.mask_gen_tab import MaskGenTab
# from gui.mask_editor_tab import MaskEditorTab
# from gui.mask_conversion_tab import MaskConversionTab
# from gui.custom_labelme_tab import CustomLabelMeTab


# Stylesheet
STYLESHEET = """
QMainWindow {
    background-color: #f5f5f5;
}

QGroupBox {
    color: #333;
    border: 1px solid #ddd;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px 0 3px;
}

QPushButton {
    background-color: #0d7377;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #14919b;
}

QPushButton:pressed {
    background-color: #0a5a60;
}

QPushButton:disabled {
    background-color: #ccc;
    color: #999;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 5px;
    background-color: white;
    color: #333;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #0d7377;
    background-color: #f9f9f9;
}

QTextEdit {
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: white;
    font-family: Courier New;
    font-size: 10px;
}

QTabWidget::pane {
    border: 1px solid #ddd;
}

QTabBar::tab {
    background-color: #eee;
    color: #333;
    padding: 8px 20px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: white;
    color: #0d7377;
    border-bottom: 3px solid #0d7377;
}

QLabel {
    color: #333;
}
"""


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("道路数据处理工具")
        self.setGeometry(100, 100, 1000, 750)
        self.setStyleSheet(STYLESHEET)
        
        # Defer imports of tabs to here
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from gui.datapreprocessing_tab import DataPreprocessingTab
        # Removed tabs are now in deprecated_features/
        from gui.mask_conversion_tab import MaskConversionTab
        from gui.custom_labelme_tab import CustomLabelMeTab
        
        self.tabs = QTabWidget()
        
        # 1. 数据预处理 Tab (合并了下载、清洗、拼接)
        self.preprocess_tab = DataPreprocessingTab()
        self.tabs.addTab(self.preprocess_tab, "数据预处理")
        
        # 2. Mask转换与标注 Tab
        self.conversion_tab = MaskConversionTab()
        self.tabs.addTab(self.conversion_tab, "标注转换")

        # 3. 自定义 LabelMe Tab
        self.labelme_tab = CustomLabelMeTab()
        self.tabs.addTab(self.labelme_tab, "自定义 LabelMe")
        
        self.setCentralWidget(self.tabs)

    def closeEvent(self, event) -> None:
        """Handle window close event - stop all worker threads."""
        event.accept()


def run_gui() -> None:
    """Launch the GUI application."""
    # QApplication is already initialized at module level
    app = QApplication.instance()
    # app.setStyle('Fusion') # Already set
    window = MainWindow()
    window.show()

    app.exec_()


if __name__ == "__main__":
    run_gui()
