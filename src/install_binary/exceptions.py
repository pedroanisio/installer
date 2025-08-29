"""
Custom exceptions for install-binary tool
"""


class InstallationError(Exception):
    """Base exception for installation errors"""
    pass


class ValidationError(InstallationError):
    """Raised when validation fails"""
    pass


class PermissionError(InstallationError):
    """Raised when permission operations fail"""
    pass
