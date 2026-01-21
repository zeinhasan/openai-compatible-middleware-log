import logging
import sys
from typing import Optional

project_name = 'openai-compatible-middleware-log'
logger = logging.getLogger(project_name)

def configure_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    log_format: str = "%(asctime)s - %(funcName)s - %(levelname)s - %(message)s"
) -> None:
    # Clear existing handlers to prevent duplicate logs
    if logging.root.handlers:
        for handler in logging.root.handlers:
            logging.root.removeHandler(handler)

    # Set the root logger level
    logging.root.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    # Suppress *all* loggers except yours
    for name in logging.root.manager.loggerDict:
        if name != project_name:
            logging.getLogger(name).setLevel(logging.CRITICAL + 1)

    
    formatter = logging.Formatter(log_format)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logging.root.addHandler(console_handler)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logging.root.addHandler(file_handler)
        except Exception as e:
            sys.stderr.write(f"Error setting up file logger to {log_file}: {e}\\n")
            if not log_to_console:
                sys.exit(1)
