"""
Shared test fixtures for fastapi-pii tests.
"""
from typing import Dict, Optional, Tuple

import pytest
from cryptography.fernet import Fernet

from python_pii import PIIStorageBackend, PIITokenizationService


class InMemoryPIIBackend:
    """In-memory storage backend for testing."""
    
    def __init__(self):
        self._storage: Dict[str, Tuple[str, Dict[str, str]]] = {}
    
    async def store_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> None:
        self._storage[token] = (encrypted_pek, encrypted_data)
    
    async def get_pii(self, token: str) -> Optional[Tuple[str, Dict[str, str]]]:
        return self._storage.get(token)
    
    async def update_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> bool:
        if token in self._storage:
            self._storage[token] = (encrypted_pek, encrypted_data)
            return True
        return False
    
    async def delete_pii(self, token: str) -> bool:
        if token in self._storage:
            del self._storage[token]
            return True
        return False


@pytest.fixture
def storage_backend():
    """Provide an in-memory storage backend."""
    return InMemoryPIIBackend()


@pytest.fixture
def fernet_key():
    """Provide a test Fernet key."""
    return Fernet.generate_key()


@pytest.fixture
def pii_service(storage_backend, fernet_key):
    """Provide a PIITokenizationService instance."""
    return PIITokenizationService(storage=storage_backend, kek_key=fernet_key)
