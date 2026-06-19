"""
In-memory storage backend for testing and development.
"""
from typing import Dict, List, Optional, Tuple


class InMemoryBackend:
    """
    In-memory storage backend for PII data.
    
    Useful for unit tests, prototyping, and local development.
    Data is not persisted — it is lost when the process exits.
    
    Example:
        from piisafe import PIITokenizationService
        from piisafe.backends import InMemoryBackend
        
        storage = InMemoryBackend()
        service = PIITokenizationService(storage=storage, kek_key=key)
    """
    
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
    
    async def list_tokens(self) -> List[str]:
        return list(self._storage.keys())
    
    def clear(self) -> None:
        """Remove all stored PII data."""
        self._storage.clear()
    
    def count(self) -> int:
        """Return the number of stored PII records."""
        return len(self._storage)
