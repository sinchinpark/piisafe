"""
PII tokenization service with encryption/decryption capabilities.
"""
import logging
import os
import secrets
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from python_pii.exceptions import PIIDecryptionError, PIIEncryptionError
from python_pii.protocols import PIIStorageBackend

logger = logging.getLogger(__name__)


class PIITokenizationService:
    """
    Service for tokenizing PII (Personally Identifiable Information) data.
    
    This service handles generating tokens, encrypting and decrypting PII data,
    and interacting with a storage backend that implements the PIIStorageBackend protocol.
    """
    
    def __init__(self, storage: PIIStorageBackend, fernet_key: Optional[bytes] = None):
        """
        Initialize the PII tokenization service.
        
        Args:
            storage: The storage backend implementing PIIStorageBackend protocol.
            fernet_key: The key to use for encryption and decryption.
                If None, the key will be read from the FERNET_KEY environment variable.
                If the environment variable is not set, a new key will be generated.
        """
        self.storage = storage
        
        # Get the Fernet key from the environment variable or use the provided key
        if fernet_key is None:
            fernet_key_str = os.environ.get("FERNET_KEY")
            if fernet_key_str:
                fernet_key = fernet_key_str.encode()
            else:
                # Generate a new key if none is provided or found in the environment
                fernet_key = Fernet.generate_key()
                logger.warning(
                    f"No Fernet key provided or found in environment. Generated new key: {fernet_key.decode()}. "
                    "It is recommended to store this key securely and provide it via the FERNET_KEY environment variable."
                )
        
        self.fernet = Fernet(fernet_key)
    
    @staticmethod
    def generate_token() -> str:
        """
        Generate a unique token for PII data.
        
        Returns:
            A unique token.
        """
        return secrets.token_urlsafe(16)
    
    def encrypt_pii(self, data: str) -> str:
        """
        Encrypt PII data.
        
        Args:
            data: The PII data to encrypt.
        
        Returns:
            The encrypted PII data.
            
        Raises:
            PIIEncryptionError: If encryption fails.
        """
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            raise PIIEncryptionError(f"Failed to encrypt PII data: {str(e)}")
    
    def decrypt_pii(self, data: str) -> str:
        """
        Decrypt PII data.
        
        Args:
            data: The encrypted PII data to decrypt.
        
        Returns:
            The decrypted PII data.
            
        Raises:
            PIIDecryptionError: If decryption fails or token is invalid.
        """
        try:
            return self.fernet.decrypt(data.encode()).decode()
        except InvalidToken:
            raise PIIDecryptionError("Invalid or tampered encrypted data")
        except Exception as e:
            raise PIIDecryptionError(f"Failed to decrypt PII data: {str(e)}")
    
    async def tokenize_pii(self, pii_data: Dict[str, str]) -> str:
        """
        Tokenize PII data by encrypting it and storing it in the backend.
        
        Args:
            pii_data: A dictionary containing the PII data.
                The keys are the field names and the values are the field values.
        
        Returns:
            A token that can be used to retrieve the PII data.
        """
        # Generate a token
        token = self.generate_token()
        
        # Encrypt each field in the PII data
        encrypted_data = {
            field: self.encrypt_pii(value)
            for field, value in pii_data.items()
        }
        
        # Store the encrypted data in the backend
        await self.storage.store_pii(token, encrypted_data)
        
        return token
    
    async def retrieve_pii(self, token: str) -> Optional[Dict[str, str]]:
        """
        Retrieve and decrypt PII data using a token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            The decrypted PII data, or None if no data was found for the token.
        """
        # Retrieve the encrypted data from the backend
        encrypted_data = await self.storage.get_pii(token)
        
        if encrypted_data is None:
            return None
        
        # Decrypt each field in the PII data
        decrypted_data = {
            field: self.decrypt_pii(value)
            for field, value in encrypted_data.items()
        }
        
        return decrypted_data
    
    async def update_pii(self, token: str, pii_data: Dict[str, str]) -> bool:
        """
        Update PII data for an existing token.
        
        Args:
            token: The token used to store the PII data.
            pii_data: A dictionary containing the updated PII data.
                The keys are the field names and the values are the field values.
        
        Returns:
            True if the data was updated, False otherwise.
        """
        # Encrypt each field in the PII data
        encrypted_data = {
            field: self.encrypt_pii(value)
            for field, value in pii_data.items()
        }
        
        # Update the encrypted data in the backend
        return await self.storage.update_pii(token, encrypted_data)
    
    async def delete_pii(self, token: str) -> bool:
        """
        Delete PII data for a token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            True if the data was deleted, False otherwise.
        """
        return await self.storage.delete_pii(token)
