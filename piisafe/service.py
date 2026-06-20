"""
PII tokenization service with encryption/decryption capabilities.
"""
import logging
import os
import re
import secrets
from typing import List, Optional, Dict

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from piisafe.exceptions import PIIDecryptionError, PIIEncryptionError, PIIKeyError, PIITokenInvalidError
from piisafe.protocols import PIIStorageBackend

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{16,43}$")


class PIITokenizationService:
    """
    Service for tokenizing PII (Personally Identifiable Information) data.
    
    Uses a PEK/KEK key hierarchy:
    - KEK (Key Encryption Key): Master key(s) that wrap/unwrap PEKs. Never touches PII directly.
    - PEK (Presentation Encryption Key): Per-record key that encrypts/decrypts PII data.
    
    Supports key rotation via MultiFernet — pass multiple KEKs with the newest first.
    """
    
    def __init__(
        self,
        storage: PIIStorageBackend,
        kek_keys: Optional[bytes | List[bytes]] = None,
    ):
        """
        Initialize the PII tokenization service.
        
        Args:
            storage: The storage backend implementing PIIStorageBackend protocol.
            kek_keys: KEK(s) for wrapping/unwrapping PEKs. Accepts:
                - bytes: A single key
                - List[bytes]: Multiple keys for rotation (newest first)
                The first key is used for encryption; all keys are tried for decryption.
        
        Key resolution priority:
            kek_keys param > FERNET_KEYS env > FERNET_KEY env
        
        Raises:
            PIIKeyError: If no key is available or keys are invalid.
        """
        self.storage = storage
        
        if kek_keys is not None:
            if isinstance(kek_keys, bytes):
                keys = [kek_keys]
            else:
                keys = kek_keys
        else:
            keys = self._load_keys_from_env()
        
        if not keys:
            raise PIIKeyError(
                "No encryption key provided. Pass kek_keys to the constructor "
                "or set the FERNET_KEY/FERNET_KEYS environment variable."
            )
        
        try:
            self._multi_kek = MultiFernet([Fernet(k) for k in keys])
        except (ValueError, Exception) as e:
            raise PIIKeyError(f"Invalid KEK: {e}") from e
    
    @staticmethod
    def _load_keys_from_env() -> List[bytes]:
        """Load KEK(s) from environment variables."""
        keys_str = os.environ.get("FERNET_KEYS")
        if keys_str:
            return [k.strip().encode() for k in keys_str.split(",") if k.strip()]
        
        single_key = os.environ.get("FERNET_KEY")
        if single_key:
            return [single_key.encode()]
        
        return []
    
    @staticmethod
    def generate_token() -> str:
        """
        Generate a unique token for PII data.
        
        Returns:
            A unique token.
        """
        return secrets.token_urlsafe(16)
    
    @staticmethod
    def _validate_token(token: str) -> None:
        """Validate token format.
        
        Args:
            token: The token to validate.
        
        Raises:
            PIITokenInvalidError: If token is empty, oversized, or contains invalid characters.
        """
        if not token or not _TOKEN_RE.match(token):
            raise PIITokenInvalidError()
    
    @staticmethod
    def _encrypt_with_pek(data: str, pek: Fernet) -> str:
        """Encrypt data using a PEK."""
        try:
            return pek.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error("Encryption failed: %s", e, exc_info=True)
            raise PIIEncryptionError("Encryption operation failed")
    
    @staticmethod
    def _decrypt_with_pek(data: str, pek: Fernet) -> str:
        """Decrypt data using a PEK."""
        try:
            return pek.decrypt(data.encode()).decode()
        except InvalidToken:
            raise PIIDecryptionError("Invalid or tampered encrypted data")
        except Exception as e:
            logger.error("Decryption failed: %s", e, exc_info=True)
            raise PIIDecryptionError("Decryption operation failed")
    
    def _wrap_pek(self, pek_key: bytes) -> str:
        """Wrap a PEK with the primary KEK."""
        try:
            return self._multi_kek.encrypt(pek_key).decode()
        except Exception as e:
            logger.error("PEK wrap failed: %s", e, exc_info=True)
            raise PIIEncryptionError("Key wrapping operation failed")
    
    def _unwrap_pek(self, encrypted_pek: str) -> bytes:
        """Unwrap a PEK using any valid KEK."""
        try:
            return self._multi_kek.decrypt(encrypted_pek.encode())
        except InvalidToken:
            raise PIIDecryptionError("Invalid or tampered encryption key")
        except Exception as e:
            logger.error("PEK unwrap failed: %s", e, exc_info=True)
            raise PIIDecryptionError("Key unwrapping operation failed")
    
    async def tokenize_pii(self, pii_data: Dict[str, str]) -> str:
        """
        Tokenize PII data by encrypting it and storing it in the backend.
        
        Each token gets its own PEK, wrapped by the primary KEK for storage.
        
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
        self._validate_token(token)
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
        self._validate_token(token)
        pek_key = Fernet.generate_key()
        pek = Fernet(pek_key)
        
        encrypted_data = {
            field: self._encrypt_with_pek(value, pek)
            for field, value in pii_data.items()
        }
        encrypted_pek = self._wrap_pek(pek_key)
        
        return await self.storage.update_pii(token, encrypted_pek, encrypted_data)
    
    async def rotate_kek(self, token: str) -> bool:
        """Re-wrap a token's PEK under the current primary KEK.
        
        Call this after adding a new primary KEK to migrate old records.
        
        Args:
            token: The token whose PEK should be re-wrapped.
        
        Returns:
            True if rotated, False if token not found.
        """
        self._validate_token(token)
        result = await self.storage.get_pii(token)
        if result is None:
            return False
        
        encrypted_pek, encrypted_data = result
        rotated_pek = self._multi_kek.rotate(encrypted_pek.encode()).decode()
        return await self.storage.update_pii(token, rotated_pek, encrypted_data)
    
    async def rotate_all_peks(self) -> int:
        """Re-wrap all PEKs under the current primary KEK.
        
        Call this after adding a new primary KEK to migrate all records.
        
        Returns:
            The number of records rotated.
        """
        tokens = await self.storage.list_tokens()
        rotated = 0
        for token in tokens:
            if await self.rotate_kek(token):
                rotated += 1
        return rotated
    
    async def delete_pii(self, token: str) -> bool:
        """
        Delete PII data for a token.
        
        Args:
            token: The token used to store the PII data.
        
        Returns:
            True if the data was deleted, False otherwise.
        """
        self._validate_token(token)
        return await self.storage.delete_pii(token)
