import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
DOWNLOAD_LOG = os.path.join(LOG_DIR, 'download.log')
ERROR_LOG = os.path.join(LOG_DIR, 'error.log')

os.makedirs(LOG_DIR, exist_ok=True)

# Formatter
formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Download logger
_download_handler = RotatingFileHandler(DOWNLOAD_LOG, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
_download_handler.setFormatter(formatter)
_download_logger = logging.getLogger('civitai.download')
_download_logger.setLevel(logging.INFO)
_download_logger.addHandler(_download_handler)
_download_logger.propagate = False

# Error logger
_error_handler = RotatingFileHandler(ERROR_LOG, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
_error_handler.setFormatter(formatter)
_error_logger = logging.getLogger('civitai.error')
_error_logger.setLevel(logging.WARNING)
_error_logger.addHandler(_error_handler)
_error_logger.propagate = False

# Convenience functions
def get_download_logger():
    return _download_logger

def get_error_logger():
    return _error_logger

# Example usage:
# log = get_download_logger()
# log.info('Download started')
# err = get_error_logger()
# err.error('Download failed')
