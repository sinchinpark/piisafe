"""
Tests for PIITokenizationService.
"""

import pytest
from cryptography.fernet import Fernet

from python_pii import PIIDecryptionError, PIIKeyError, PIITokenizationService


@pytest.mark.anyio
async def test_tokenize_and_retrieve(pii_service):
    """Test tokenizing and retrieving PII data."""
    pii_data = {"email": "test@example.com", "ssn": "123-45-6789"}
    
    token = await pii_service.tokenize_pii(pii_data)
    assert token is not None
    assert len(token) > 0
    
    retrieved_data = await pii_service.retrieve_pii(token)
    assert retrieved_data == pii_data


@pytest.mark.anyio
async def test_retrieve_nonexistent_token(pii_service):
    """Test retrieving a token that doesn't exist."""
    result = await pii_service.retrieve_pii("nonexistent-token")
    assert result is None


@pytest.mark.anyio
async def test_update_pii(pii_service):
    """Test updating PII data."""
    pii_data = {"email": "test@example.com"}
    
    token = await pii_service.tokenize_pii(pii_data)
    
    updated_data = {"email": "updated@example.com", "phone": "555-1234"}
    success = await pii_service.update_pii(token, updated_data)
    assert success is True
    
    retrieved_data = await pii_service.retrieve_pii(token)
    assert retrieved_data == updated_data


@pytest.mark.anyio
async def test_update_nonexistent_token(pii_service):
    """Test updating a token that doesn't exist."""
    success = await pii_service.update_pii("nonexistent-token", {"email": "test@example.com"})
    assert success is False


@pytest.mark.anyio
async def test_delete_pii(pii_service):
    """Test deleting PII data."""
    pii_data = {"email": "test@example.com"}
    
    token = await pii_service.tokenize_pii(pii_data)
    
    success = await pii_service.delete_pii(token)
    assert success is True
    
    retrieved_data = await pii_service.retrieve_pii(token)
    assert retrieved_data is None


@pytest.mark.anyio
async def test_delete_nonexistent_token(pii_service):
    """Test deleting a token that doesn't exist."""
    success = await pii_service.delete_pii("nonexistent-token")
    assert success is False


@pytest.mark.anyio
async def test_decrypt_tampered_data(storage_backend, fernet_key):
    """Test that decrypting tampered data raises PIIDecryptionError."""
    service = PIITokenizationService(storage=storage_backend, kek_key=fernet_key)
    
    # Create a valid wrapped PEK
    kek = Fernet(fernet_key)
    pek_key = Fernet.generate_key()
    encrypted_pek = kek.encrypt(pek_key).decode()
    
    # Store with tampered encrypted data
    token = "test-token"
    await storage_backend.store_pii(token, encrypted_pek, {"field": "tampered-invalid-data"})
    
    with pytest.raises(PIIDecryptionError):
        await service.retrieve_pii(token)


@pytest.mark.anyio
async def test_key_from_environment(storage_backend, monkeypatch):
    """Test that the service reads the key from FERNET_KEY environment variable."""
    test_key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", test_key.decode())
    
    service = PIITokenizationService(storage=storage_backend)
    
    # Verify the key was loaded by doing a round-trip
    pii_data = {"field": "test"}
    token = await service.tokenize_pii(pii_data)
    retrieved = await service.retrieve_pii(token)
    assert retrieved == pii_data


def test_key_missing_raises_error(storage_backend, monkeypatch):
    """Test that PIIKeyError is raised when no key is provided."""
    monkeypatch.delenv("FERNET_KEY", raising=False)
    
    with pytest.raises(PIIKeyError, match="No encryption key provided"):
        PIITokenizationService(storage=storage_backend)


def test_generate_token():
    """Test token generation."""
    token1 = PIITokenizationService.generate_token()
    token2 = PIITokenizationService.generate_token()
    
    assert token1 != token2
    assert all(c.isalnum() or c in "-_" for c in token1)
    assert all(c.isalnum() or c in "-_" for c in token2)


@pytest.mark.anyio
async def test_unique_pek_per_token(pii_service, storage_backend):
    """Test that each token uses a unique PEK."""
    pii_data = {"email": "test@example.com"}
    
    token1 = await pii_service.tokenize_pii(pii_data)
    token2 = await pii_service.tokenize_pii(pii_data)
    
    result1 = await storage_backend.get_pii(token1)
    result2 = await storage_backend.get_pii(token2)
    
    encrypted_pek1, _ = result1
    encrypted_pek2, _ = result2
    
    assert encrypted_pek1 != encrypted_pek2


@pytest.mark.anyio
async def test_kek_can_re_wrap_pek(storage_backend, fernet_key):
    """Test that rotating the KEK only requires re-wrapping PEKs, not re-encrypting data."""
    kek1 = Fernet(fernet_key)
    
    # Encrypt data with first KEK
    service1 = PIITokenizationService(storage=storage_backend, kek_key=fernet_key)
    pii_data = {"email": "test@example.com"}
    token = await service1.tokenize_pii(pii_data)
    
    # Get the encrypted PEK and data
    encrypted_pek, encrypted_data = await storage_backend.get_pii(token)
    
    # Unwrap PEK with old KEK, re-wrap with new KEK
    new_kek_key = Fernet.generate_key()
    kek2 = Fernet(new_kek_key)
    
    pek_key = kek1.decrypt(encrypted_pek.encode())
    new_encrypted_pek = kek2.encrypt(pek_key).decode()
    
    # Update storage with re-wrapped PEK (same encrypted data)
    await storage_backend.update_pii(token, new_encrypted_pek, encrypted_data)
    
    # Verify data is still accessible with new KEK
    service2 = PIITokenizationService(storage=storage_backend, kek_key=new_kek_key)
    retrieved = await service2.retrieve_pii(token)
    assert retrieved == pii_data
