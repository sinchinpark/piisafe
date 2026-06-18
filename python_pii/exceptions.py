"""
PII-specific exceptions with HTTP status codes.
"""


class PIIError(Exception):
    """Base exception for all PII-related errors."""
    
    def __init__(self, message: str, status_code: int, code: str):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class PIITokenNotFoundError(PIIError):
    """Raised when a PII token is not found in storage."""
    
    def __init__(self, message: str = "PII data not found for token"):
        super().__init__(
            message=message,
            status_code=404,
            code="PII_TOKEN_NOT_FOUND"
        )


class PIITokenInvalidError(PIIError):
    """Raised when a PII token format is invalid."""
    
    def __init__(self, message: str = "Invalid PII token format"):
        super().__init__(
            message=message,
            status_code=400,
            code="PII_INVALID_TOKEN"
        )


class PIIEncryptionError(PIIError):
    """Raised when there is an error encrypting PII data."""
    
    def __init__(self, message: str = "Error encrypting PII data"):
        super().__init__(
            message=message,
            status_code=500,
            code="PII_ENCRYPTION_ERROR"
        )


class PIIDecryptionError(PIIError):
    """Raised when there is an error decrypting PII data."""
    
    def __init__(self, message: str = "Error decrypting PII data"):
        super().__init__(
            message=message,
            status_code=500,
            code="PII_DECRYPTION_ERROR"
        )


class PIIKeyError(PIIError):
    """Raised when encryption key is missing or cannot be loaded."""
    
    def __init__(self, message: str = "Encryption key not configured"):
        super().__init__(
            message=message,
            status_code=500,
            code="PII_KEY_ERROR"
        )
