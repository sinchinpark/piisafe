"""
Storage protocol for PII tokenization backends.
"""
from typing import Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class PIIStorageBackend(Protocol):
    """
    Protocol defining the interface for PII storage backends.
    
    Any class implementing these four async methods can be used as a storage backend
    for the PIITokenizationService, regardless of the underlying storage mechanism
    (SQL, NoSQL, in-memory, etc.).
    """
    
    async def store_pii(self, token: str, encrypted_data: Dict[str, str]) -> None:
        """
        Store encrypted PII data with the given token.
        
        Args:
            token: The token to use as the key for the PII data.
            encrypted_data: A dictionary containing the encrypted PII data.
                The keys are field names and values are encrypted field values.
        """
        ...
    
    async def get_pii(self, token: str) -> Optional[Dict[str, str]]:
        """
        Retrieve the encrypted PII data for the given token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            The encrypted PII data, or None if no data was found for the token.
        """
        ...
    
    async def update_pii(self, token: str, encrypted_data: Dict[str, str]) -> bool:
        """
        Update the encrypted PII data for the given token.
        
        Args:
            token: The token used to store the PII data.
            encrypted_data: A dictionary containing the encrypted PII data.
        
        Returns:
            True if the data was updated, False otherwise.
        """
        ...
    
    async def delete_pii(self, token: str) -> bool:
        """
        Delete the PII data for the given token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            True if the data was deleted, False otherwise.
        """
        ...
