"""
Storage protocol for PII tokenization backends.
"""
from typing import Dict, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class PIIStorageBackend(Protocol):
    """
    Protocol defining the interface for PII storage backends.
    
    Any class implementing these four async methods can be used as a storage backend
    for the PIITokenizationService, regardless of the underlying storage mechanism
    (SQL, NoSQL, in-memory, etc.).
    """
    
    async def store_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> None:
        """
        Store encrypted PII data with its wrapped PEK.
        
        Args:
            token: The token to use as the key for the PII data.
            encrypted_pek: The PEK encrypted by the KEK.
            encrypted_data: A dictionary containing the encrypted PII data.
                The keys are field names and values are encrypted field values.
        """
        ...
    
    async def get_pii(self, token: str) -> Optional[Tuple[str, Dict[str, str]]]:
        """
        Retrieve the wrapped PEK and encrypted PII data for the given token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            A tuple of (encrypted_pek, encrypted_data), or None if not found.
        """
        ...
    
    async def update_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> bool:
        """
        Update the encrypted PII data and wrapped PEK for the given token.
        
        Args:
            token: The token used to store the PII data.
            encrypted_pek: The new PEK encrypted by the KEK.
            encrypted_data: A dictionary containing the encrypted PII data.
        
        Returns:
            True if the data was updated, False otherwise.
        """
        ...
    
    async def delete_pii(self, token: str) -> bool:
        """
        Delete the PII data for a token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            True if the data was deleted, False otherwise.
        """
        ...
