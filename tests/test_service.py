"""
Tests for PIITokenizationService.
"""

import pytest
from cryptography.fernet import Fernet

from piisafe import PIIDecryptionError, PIIKeyError, PIITokenizationService, PIITokenInvalidError


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
    service = PIITokenizationService(storage=storage_backend, kek_keys=fernet_key)
    
    # Create a valid wrapped PEK
    kek = Fernet(fernet_key)
    pek_key = Fernet.generate_key()
    encrypted_pek = kek.encrypt(pek_key).decode()
    
    # Store with tampered encrypted data
    token = "test-token-format-ok"
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


def test_invalid_kek_raises_key_error(storage_backend, monkeypatch):
    """Test that PIIKeyError is raised when an invalid KEK is provided."""
    monkeypatch.delenv("FERNET_KEY", raising=False)
    monkeypatch.delenv("FERNET_KEYS", raising=False)

    with pytest.raises(PIIKeyError, match="Invalid KEK"):
        PIITokenizationService(storage=storage_backend, kek_keys=b"not-a-valid-fernet-key")


def test_invalid_kek_in_list_raises_key_error(storage_backend, monkeypatch):
    """Test that PIIKeyError is raised when any KEK in the list is invalid."""
    monkeypatch.delenv("FERNET_KEY", raising=False)
    monkeypatch.delenv("FERNET_KEYS", raising=False)

    valid_key = Fernet.generate_key()
    with pytest.raises(PIIKeyError, match="Invalid KEK"):
        PIITokenizationService(
            storage=storage_backend,
            kek_keys=[valid_key, b"not-a-valid-fernet-key"],
        )


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
    service1 = PIITokenizationService(storage=storage_backend, kek_keys=fernet_key)
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
    service2 = PIITokenizationService(storage=storage_backend, kek_keys=new_kek_key)
    retrieved = await service2.retrieve_pii(token)
    assert retrieved == pii_data


# --- MultiFernet / Key Rotation Tests ---


@pytest.mark.anyio
async def test_multi_key_decrypt(storage_backend):
    """Test that PEKs wrapped with old key can be decrypted with multi-key service."""
    old_key = Fernet.generate_key()
    new_key = Fernet.generate_key()
    
    # Create service with old key, encrypt real data
    service_old = PIITokenizationService(storage=storage_backend, kek_keys=old_key)
    pii_data = {"email": "test@example.com"}
    token = await service_old.tokenize_pii(pii_data)
    
    # Verify old key works
    assert await service_old.retrieve_pii(token) == pii_data
    
    # Service with [new, old] — should still decrypt old PEK
    service_multi = PIITokenizationService(
        storage=storage_backend,
        kek_keys=[new_key, old_key],
    )
    result = await service_multi.retrieve_pii(token)
    assert result == pii_data


@pytest.mark.anyio
async def test_multi_key_encrypt_uses_primary(storage_backend):
    """Test that new PEKs are wrapped with the primary (first) key."""
    key1 = Fernet.generate_key()
    key2 = Fernet.generate_key()
    
    service = PIITokenizationService(
        storage=storage_backend,
        kek_keys=[key1, key2],
    )
    
    pii_data = {"email": "test@example.com"}
    token = await service.tokenize_pii(pii_data)
    
    encrypted_pek, _ = await storage_backend.get_pii(token)
    
    # Verify PEK was encrypted with key1 (primary), not key2
    kek1 = Fernet(key1)
    # Should not raise — key1 can decrypt
    kek1.decrypt(encrypted_pek.encode())
    
    kek2 = Fernet(key2)
    # key2 should NOT be able to decrypt (it was encrypted with key1)
    with pytest.raises(InvalidToken):
        kek2.decrypt(encrypted_pek.encode())


@pytest.mark.anyio
async def test_rotate_kek(storage_backend):
    """Test rotating PEKs from old key to new key."""
    old_key = Fernet.generate_key()
    new_key = Fernet.generate_key()
    
    # Create token with old key
    service_old = PIITokenizationService(storage=storage_backend, kek_keys=old_key)
    pii_data = {"email": "test@example.com"}
    token = await service_old.tokenize_pii(pii_data)
    
    # Verify we can read it
    assert await service_old.retrieve_pii(token) == pii_data
    
    # Create service with new key as primary, old as fallback
    service_new = PIITokenizationService(
        storage=storage_backend,
        kek_keys=[new_key, old_key],
    )
    
    # Rotate the PEK to new key
    success = await service_new.rotate_kek(token)
    assert success is True
    
    # Verify data is still accessible
    assert await service_new.retrieve_pii(token) == pii_data
    
    # Verify the PEK is now wrapped with new_key
    encrypted_pek, _ = await storage_backend.get_pii(token)
    kek_new = Fernet(new_key)
    kek_new.decrypt(encrypted_pek.encode())  # Should succeed
    
    kek_old = Fernet(old_key)
    with pytest.raises(InvalidToken):
        kek_old.decrypt(encrypted_pek.encode())  # Should fail


@pytest.mark.anyio
async def test_rotate_kek_nonexistent(storage_backend):
    """Test rotate_kek returns False for nonexistent token."""
    key = Fernet.generate_key()
    service = PIITokenizationService(storage=storage_backend, kek_keys=key)
    
    success = await service.rotate_kek("nonexistent-token-ok")
    assert success is False


@pytest.mark.anyio
async def test_fernet_keys_env_var(storage_backend, monkeypatch):
    """Test loading multiple keys from FERNET_KEYS env var."""
    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEYS", f"{key1},{key2}")
    monkeypatch.delenv("FERNET_KEY", raising=False)
    
    service = PIITokenizationService(storage=storage_backend)
    
    pii_data = {"field": "test"}
    token = await service.tokenize_pii(pii_data)
    retrieved = await service.retrieve_pii(token)
    assert retrieved == pii_data


from cryptography.fernet import InvalidToken


@pytest.mark.anyio
async def test_rotate_all_peks(storage_backend):
    """Test rotating all PEKs from old key to new key."""
    old_key = Fernet.generate_key()
    new_key = Fernet.generate_key()
    
    # Create multiple tokens with old key
    service_old = PIITokenizationService(storage=storage_backend, kek_keys=old_key)
    pii1 = {"email": "alice@example.com"}
    pii2 = {"email": "bob@example.com"}
    token1 = await service_old.tokenize_pii(pii1)
    token2 = await service_old.tokenize_pii(pii2)
    
    # Create service with new key as primary, old as fallback
    service_new = PIITokenizationService(
        storage=storage_backend,
        kek_keys=[new_key, old_key],
    )
    
    # Rotate all PEKs
    result = await service_new.rotate_all_peks()
    assert result.total == 2
    assert result.rotated == 2
    assert result.is_complete is True
    assert len(result.failed) == 0
    
    # Verify data is still accessible
    assert await service_new.retrieve_pii(token1) == pii1
    assert await service_new.retrieve_pii(token2) == pii2
    
    # Verify PEKs are now wrapped with new_key
    for token in [token1, token2]:
        encrypted_pek, _ = await storage_backend.get_pii(token)
        Fernet(new_key).decrypt(encrypted_pek.encode())  # Should succeed
        with pytest.raises(InvalidToken):
            Fernet(old_key).decrypt(encrypted_pek.encode())  # Should fail


@pytest.mark.anyio
async def test_rotate_all_peks_empty(storage_backend):
    """Test rotate_all_peks returns empty result on empty storage."""
    key = Fernet.generate_key()
    service = PIITokenizationService(storage=storage_backend, kek_keys=key)
    
    result = await service.rotate_all_peks()
    assert result.total == 0
    assert result.rotated == 0
    assert result.is_complete is True
    assert result.failed == []


# --- Token Validation Tests ---


@pytest.mark.anyio
async def test_retrieve_pii_empty_token_raises(pii_service):
    """Test empty token raises PIITokenInvalidError."""
    with pytest.raises(PIITokenInvalidError):
        await pii_service.retrieve_pii("")


@pytest.mark.anyio
async def test_retrieve_pii_oversized_token_raises(pii_service):
    """Test that oversized token raises PIITokenInvalidError."""
    oversized = "a" * 100
    with pytest.raises(PIITokenInvalidError):
        await pii_service.retrieve_pii(oversized)


@pytest.mark.anyio
async def test_retrieve_pii_invalid_chars_token_raises(pii_service):
    """Test that token with invalid characters raises PIITokenInvalidError."""
    with pytest.raises(PIITokenInvalidError):
        await pii_service.retrieve_pii("../../../etc/passwd")


@pytest.mark.anyio
async def test_update_pii_invalid_token_raises(pii_service):
    """Test that update_pii raises PIITokenInvalidError for invalid token."""
    with pytest.raises(PIITokenInvalidError):
        await pii_service.update_pii("", {"email": "test@example.com"})


@pytest.mark.anyio
async def test_delete_pii_invalid_token_raises(pii_service):
    """Test that delete_pii raises PIITokenInvalidError for invalid token."""
    with pytest.raises(PIITokenInvalidError):
        await pii_service.delete_pii("bad!")


@pytest.mark.anyio
async def test_rotate_kek_invalid_token_raises(pii_service):
    """Test that rotate_kek raises PIITokenInvalidError for invalid token."""
    with pytest.raises(PIITokenInvalidError):
        await pii_service.rotate_kek("short")


# --- rotate_all_peks Failure Handling ---


@pytest.mark.anyio
async def test_rotate_all_peks_partial_failure(storage_backend):
    """Test that rotate_all_peks continues past a failed token."""
    old_key = Fernet.generate_key()
    new_key = Fernet.generate_key()

    service_old = PIITokenizationService(storage=storage_backend, kek_keys=old_key)
    token_ok = await service_old.tokenize_pii({"email": "ok@example.com"})
    token_bad = await service_old.tokenize_pii({"email": "bad@example.com"})
    token_ok2 = await service_old.tokenize_pii({"email": "ok2@example.com"})

    # Corrupt the PEK for token_bad so rotation fails with PIIDecryptionError
    encrypted_pek, encrypted_data = await storage_backend.get_pii(token_bad)
    corrupted_pek = "not-a-valid-fernet-token"
    await storage_backend.update_pii(token_bad, corrupted_pek, encrypted_data)

    service_new = PIITokenizationService(
        storage=storage_backend,
        kek_keys=[new_key, old_key],
    )

    result = await service_new.rotate_all_peks()

    assert result.total == 3
    assert result.rotated == 2
    assert result.is_complete is False
    assert len(result.failed) == 1
    assert result.failed[0].token == token_bad
    assert result.failed[0].error_type == "InvalidToken"

    # The two good tokens should still be accessible and rotated
    assert await service_new.retrieve_pii(token_ok) == {"email": "ok@example.com"}
    assert await service_new.retrieve_pii(token_ok2) == {"email": "ok2@example.com"}


@pytest.mark.anyio
async def test_rotate_all_peks_all_fail(storage_backend):
    """Test rotate_all_peks when every token is corrupted."""
    key = Fernet.generate_key()
    service = PIITokenizationService(storage=storage_backend, kek_keys=key)

    token1 = await service.tokenize_pii({"email": "a@example.com"})
    token2 = await service.tokenize_pii({"email": "b@example.com"})

    # Corrupt both PEKs
    for tok in [token1, token2]:
        pek, data = await storage_backend.get_pii(tok)
        await storage_backend.update_pii(tok, "corrupted-pek", data)

    result = await service.rotate_all_peks()

    assert result.total == 2
    assert result.rotated == 0
    assert result.is_complete is False
    assert len(result.failed) == 2
    assert {f.token for f in result.failed} == {token1, token2}
