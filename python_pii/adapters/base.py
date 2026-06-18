"""
Base adapter class for framework adapters.
"""
from abc import ABC, abstractmethod
from typing import Any

from python_pii.service import PIITokenizationService


class BaseAdapter(ABC):
    """Base class for framework adapters."""
    
    def __init__(self, service: PIITokenizationService, prefix: str = "/pii"):
        """
        Initialize the adapter.
        
        Args:
            service: The PIITokenizationService instance to use.
            prefix: URL prefix for all routes (default: "/pii").
        """
        self.service = service
        self.prefix = prefix
    
    @abstractmethod
    def get_router(self) -> Any:
        """
        Return a framework-specific router/blueprint/app.
        
        Returns:
            Framework-specific routing object (APIRouter, Blueprint, Sanic app, etc.)
        """
        pass
    
    @abstractmethod
    def _handle_exception(self, exc: Exception) -> Any:
        """
        Convert PII exceptions to framework-specific error responses.
        
        Args:
            exc: The exception to handle
            
        Returns:
            Framework-specific error response
        """
        pass
