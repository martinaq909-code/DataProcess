import sys
import os
from PyQt5.QtWidgets import QApplication
from core.logger import setup_logging
from gui.app import MainWindow

def main():
    """
    Application Entry Point.
    """
    # Initialize logging first
    setup_logging()

    # Create the application instance
    app = QApplication(sys.argv)
    
    # Set application style if needed
    # app.setStyle('Fusion') 
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Run the event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
