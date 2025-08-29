"""
install-binary: A secure tool for installing binaries and scripts system-wide
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .installer import UniversalInstaller, HistoryManager
from .exceptions import InstallationError, ValidationError, PermissionError

__all__ = [
    "UniversalInstaller",
    "HistoryManager",
    "InstallationError",
    "ValidationError",
    "PermissionError",
]
