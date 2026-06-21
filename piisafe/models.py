"""
Data models for PII tokenization using standard library dataclasses.
"""
from dataclasses import dataclass, field
from typing import Dict, List

MAX_FIELDS = 50
MAX_KEY_LENGTH = 256
MAX_VALUE_LENGTH = 10_000


@dataclass
class PIIData:
    """Request/response model for PII data."""
    data: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate data after initialization."""
        if not isinstance(self.data, dict):
            raise TypeError("data must be a dictionary")
        if len(self.data) > MAX_FIELDS:
            raise ValueError(f"data exceeds maximum of {MAX_FIELDS} fields")
        for k, v in self.data.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise TypeError("all keys and values must be strings")
            if len(k) > MAX_KEY_LENGTH:
                raise ValueError(f"key exceeds maximum length of {MAX_KEY_LENGTH}")
            if len(v) > MAX_VALUE_LENGTH:
                raise ValueError(f"value exceeds maximum length of {MAX_VALUE_LENGTH}")


@dataclass
class TokenResponse:
    """Response model for token operations."""
    token: str
    
    def __post_init__(self):
        """Validate token after initialization."""
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("token must be a non-empty string")


@dataclass(frozen=True)
class RotationFailure:
    """Details of a single token rotation failure."""
    token: str
    error_type: str
    message: str


@dataclass(frozen=True)
class RotationResult:
    """Result of rotate_all_peks operation."""
    total: int
    rotated: int
    failed: List[RotationFailure]

    @property
    def is_complete(self) -> bool:
        return len(self.failed) == 0
