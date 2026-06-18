"""
Tests for PIITokenizationService.
"""
import logging
import os

import pytest
from cryptography.fernet import Fernet

from python_pii import PIIDecryptionError, PIIEncryptionError, PIITokenizationService
from tests.conftest import InMemoryPIIBackend


@pytest.mark.asyncio
async def test_tokenize_and_retrieve(pii_service):
    """Test tokenizing and retrieving PII data."""
    pii_data = {"email": "test@example.com", "ssn": "123-45-6789"}
    
    # Tokenize
    token = await pii_service.tokenize_pii(pii_data)
    assert token is not None
    assert len(token) > 0
    
    # Retrieve
    retrieved_data = await pii_service.retrieve_pii(token)
    assert retrieved_data == pii_data


@pytest.mark.asyncio
async def test_retrieve_nonexistent_token(pii_service):
    """Test retrieving a token that doesn't exist."""
    result = await pii_service.retrieve_pii("nonexistent-token")
    assert result is None


@pytest.mark.asyncio
async def test_update_pii(pii_service):
    """Test updating PII data."""
    pii_data = {"email": "test@example.com"}
    
    # Tokenize
    token = await pii_service.tokenize_pii(pii_data)
    
    # Update
    updated_data = {"email": "updated@example.com", "phone": "555-1234"}
    success = await pii_service.update_pii(token, updated_data)
    assert success is True
    
    # Verify update
    retrieved_data = await pii_service.retrieve_pii(token)
    assert retrieved_data == updated_data


@pytest.mark.asyncio
async def test_update_nonexistent_token(pii_service):
    """Test updating a token that doesn't exist."""
    success = await pii_service.update_pii("nonexistent-token", {"email": "test@example.com"})
    assert success is False


@pytest.mark.asyncio
async def test_delete_pii(pii_service):
    """Test deleting PII data."""
    pii_data = {"email": "test@example.com"}
    
    # Tokenize
    token = await pii_service.tokenize_pii(pii_data)
    
    # Delete
    success = await pii_service.delete_pii(token)
    assert success is True
    
    # Verify deletion
    retrieved_data = await pii_service.retrieve_pii(token)
    assert retrieved_data is None


@pytest.mark.asyncio
async def test_delete_nonexistent_token(pii_service):
    """Test deleting a token that doesn't exist."""
    success = await pii_service.delete_pii("nonexistent-token")
    assert success is False


@pytest.mark.asyncio
async def test_decrypt_tampered_data(storage_backend, fernet_key):
    """Test that decrypting tampered data raises PIIDecryptionError."""
    service = PIITokenizationService(storage=storage_backend, fernet_key=fernet_key)
    
    # Store valid encrypted data
    token = "test-token"
    await storage_backend.store_pii(token, {"field": "tampered-invalid-data"})
    
    # Attempt to retrieve should raise PIIDecryptionError
    with pytest.raises(PIIDecryptionError):
        await service.retrieve_pii(token)


def test_key_from_environment(storage_backend, monkeypatch):
    """Test that the service reads the key from FERNET_KEY environment variable."""
    test_key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", test_key.decode())
    
    service = PIITokenizationService(storage=storage_backend)
    
    # Verify the key was loaded correctly by encrypting and decrypting
    encrypted = service.encrypt_pii("test")
    decrypted = service.decrypt_pii(encrypted)
    assert decrypted == "test"


def test_key_auto_generated_warning(storage_backend, monkeypatch, caplog):
    """Test that a warning is logged when no key is provided."""
    # Remove FERNET_KEY from environment
    monkeypatch.delenv("FERNET_KEY", raising=False)
    
    with caplog.at_level(logging.WARNING):
        service = PIITokenizationService(storage=storage_backend)
    
    # Check that a warning was logged
    assert any("No Fernet key provided" in record.message for record in caplog.records)


def test_generate_token():
    """Test token generation."""
    token1 = PIITokenizationService.generate_token()
    token2 = PIITokenizationService.generate_token()
    
    # Tokens should be unique
    assert token1 != token2
    
    # Tokens should be URL-safe
    assert all(c.isalnum() or c in "-_" for c in token1)
    assert all(c.isalnum() or c in "-_" for c in token2)


def test_encrypt_decrypt_roundtrip(pii_service):
    """Test that encryption and decryption are reversible."""
    original = "sensitive data"
    encrypted = pii_service.encrypt_pii(original)
    decrypted = pii_service.decrypt_pii(encrypted)
    
    assert encrypted != original
    assert decrypted == original
