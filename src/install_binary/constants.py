"""
Constants used throughout the install-binary tool
"""

import os
from pathlib import Path

# Directory constants
DEFAULT_INSTALL_DIR = "/usr/local/bin"
USER_INSTALL_DIR = ".local/bin"
HISTORY_FILE_NAME = "install-binary-history.json"
HISTORY_DIR_SYSTEM = "/var/log"
HISTORY_DIR_USER = ".local/share/install-binary"

# File operation constants
DEFAULT_PERMISSIONS = 0o755
CHUNK_SIZE = 4096

# Platform-specific constants
IS_WINDOWS = os.name == 'nt'
IS_POSIX = os.name == 'posix'
