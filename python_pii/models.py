"""
Data models for PII tokenization using standard library dataclasses.
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PIIData:
    """Request/response model for PII data."""
    data: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate data after initialization."""
        if not isinstance(self.data, dict):
            raise TypeError("data must be a dictionary")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in self.data.items()):
            raise TypeError("all keys and values must be strings")


@dataclass
class TokenResponse:
    """Response model for token operations."""
    token: str
    
    def __post_init__(self):
        """Validate token after initialization."""
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("token must be a non-empty string")
