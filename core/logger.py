import sys
import os
import logging
import traceback
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Define log directory
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

def setup_logging():
    """
    Setup central logging configuration.
    Configures a rotating file handler for errors and a console handler.
    Installs a global exception hook to catch unhandled exceptions.
    """
    # Ensure log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Log file path
    log_file = LOG_DIR / "error.log"
    
    # Create a custom formatter
    # detailed format: Time | Level | File:Line | Function | Message
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup Root Logger
    root_logger = logging.getLogger()
    # Clear existing handlers to avoid duplicates if called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.setLevel(logging.INFO)  # Capture INFO and above globally
    
    # 1. File Handler for ERRORs (and CRITICAL)
    # RotatingFileHandler: 5MB max size, keep last 5 backups
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024, 
        backupCount=5, 
        encoding='utf-8'
    )
    file_handler.setLevel(logging.ERROR) # Only log errors to file
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 2. Console Handler (for standard output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 3. Global Exception Hook
    def handle_exception(exc_type, exc_value, exc_traceback):
        """
        Global exception handler to log unhandled exceptions.
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        logging.critical(
            "Uncaught exception detected:",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
    sys.excepthook = handle_exception
    
    logging.info("Logging initialized. Error log path: %s", log_file)
