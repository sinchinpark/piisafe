"""
PII tokenization service with encryption/decryption capabilities.
"""
import os
import secrets
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from python_pii.exceptions import PIIDecryptionError, PIIEncryptionError, PIIKeyError
from python_pii.protocols import PIIStorageBackend


class PIITokenizationService:
    """
    Service for tokenizing PII (Personally Identifiable Information) data.
    
    Uses a PEK/KEK key hierarchy:
    - KEK (Key Encryption Key): Master key that wraps/unwraps PEKs. Never touches PII directly.
    - PEK (Presentation Encryption Key): Per-record key that encrypts/decrypts PII data.
    
    This design limits blast radius — a compromised PEK exposes only one record.
    """
    
    def __init__(self, storage: PIIStorageBackend, kek_key: Optional[bytes] = None):
        """
        Initialize the PII tokenization service.
        
        Args:
            storage: The storage backend implementing PIIStorageBackend protocol.
            kek_key: The KEK (Key Encryption Key) for wrapping/unwrapping PEKs.
                If None, reads from the FERNET_KEY environment variable.
                Raises PIIKeyError if no key is available.
        """
        self.storage = storage
        
        if kek_key is None:
            kek_key_str = os.environ.get("FERNET_KEY")
            if kek_key_str:
                kek_key = kek_key_str.encode()
            else:
                raise PIIKeyError(
                    "No encryption key provided. Pass kek_key to the constructor "
                    "or set the FERNET_KEY environment variable."
                )
        
        self.kek = Fernet(kek_key)
    
    @staticmethod
    def generate_token() -> str:
        """
        Generate a unique token for PII data.
        
        Returns:
            A unique token.
        """
        return secrets.token_urlsafe(16)
    
    @staticmethod
    def _encrypt_with_pek(data: str, pek: Fernet) -> str:
        """Encrypt data using a PEK."""
        try:
            return pek.encrypt(data.encode()).decode()
        except Exception as e:
            raise PIIEncryptionError(f"Failed to encrypt PII data: {str(e)}")
    
    @staticmethod
    def _decrypt_with_pek(data: str, pek: Fernet) -> str:
        """Decrypt data using a PEK."""
        try:
            return pek.decrypt(data.encode()).decode()
        except InvalidToken:
            raise PIIDecryptionError("Invalid or tampered encrypted data")
        except Exception as e:
            raise PIIDecryptionError(f"Failed to decrypt PII data: {str(e)}")
    
    def _wrap_pek(self, pek_key: bytes) -> str:
        """Wrap a PEK with the KEK."""
        try:
            return self.kek.encrypt(pek_key).decode()
        except Exception as e:
            raise PIIEncryptionError(f"Failed to wrap encryption key: {str(e)}")
    
    def _unwrap_pek(self, encrypted_pek: str) -> bytes:
        """Unwrap a PEK using the KEK."""
        try:
            return self.kek.decrypt(encrypted_pek.encode())
        except InvalidToken:
            raise PIIDecryptionError("Invalid or tampered encryption key")
        except Exception as e:
            raise PIIDecryptionError(f"Failed to unwrap encryption key: {str(e)}")
    
    async def tokenize_pii(self, pii_data: Dict[str, str]) -> str:
        """
        Tokenize PII data by encrypting it and storing it in the backend.
        
        Each token gets its own PEK, wrapped by the KEK for storage.
        
        Args:
            pii_data: A dictionary containing the PII data.
                The keys are the field names and the values are the field values.
        
        Returns:
            A token that can be used to retrieve the PII data.
        """
        token = self.generate_token()
        pek_key = Fernet.generate_key()
        pek = Fernet(pek_key)
        
        encrypted_data = {
            field: self._encrypt_with_pek(value, pek)
            for field, value in pii_data.items()
        }
        encrypted_pek = self._wrap_pek(pek_key)
        
        await self.storage.store_pii(token, encrypted_pek, encrypted_data)
        
        return token
    
    async def retrieve_pii(self, token: str) -> Optional[Dict[str, str]]:
        """
        Retrieve and decrypt PII data using a token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            The decrypted PII data, or None if no data was found for the token.
        """
        result = await self.storage.get_pii(token)
        
        if result is None:
            return None
        
        encrypted_pek, encrypted_data = result
        pek_key = self._unwrap_pek(encrypted_pek)
        pek = Fernet(pek_key)
        
        return {
            field: self._decrypt_with_pek(value, pek)
            for field, value in encrypted_data.items()
        }
    
    async def update_pii(self, token: str, pii_data: Dict[str, str]) -> bool:
        """
        Update PII data for an existing token.
        
        Generates a new PEK for the updated data.
        
        Args:
            token: The token used to store the PII data.
            pii_data: A dictionary containing the updated PII data.
                The keys are the field names and the values are the field values.
        
        Returns:
            True if the data was updated, False otherwise.
        """
        pek_key = Fernet.generate_key()
        pek = Fernet(pek_key)
        
        encrypted_data = {
            field: self._encrypt_with_pek(value, pek)
            for field, value in pii_data.items()
        }
        encrypted_pek = self._wrap_pek(pek_key)
        
        return await self.storage.update_pii(token, encrypted_pek, encrypted_data)
    
    async def delete_pii(self, token: str) -> bool:
        """
        Delete PII data for a token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            True if the data was deleted, False otherwise.
        """
        return await self.storage.delete_pii(token)
