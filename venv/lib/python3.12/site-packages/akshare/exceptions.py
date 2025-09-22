"""
AKShare 异常处理模块
"""


class AkshareException(Exception):
    """Base exception for akshare library"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class APIError(AkshareException):
    """Raised when API request fails"""

    def __init__(self, message, status_code=None):
        self.status_code = status_code
        super().__init__(f"API Error: {message} (Status code: {status_code})")


class DataParsingError(AkshareException):
    """Raised when data parsing fails"""

    pass


class InvalidParameterError(AkshareException):
    """Raised when an invalid parameter is provided"""

    pass


class NetworkError(AkshareException):
    """Raised when network-related issues occur"""

    pass


class RateLimitError(AkshareException):
    """Raised when API rate limit is exceeded"""

    pass
