"""
Shared test fixtures for fastapi-pii tests.
"""
import pytest
from cryptography.fernet import Fernet

from python_pii import PIITokenizationService
from python_pii.backends import InMemoryBackend

InMemoryPIIBackend = InMemoryBackend


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
    return PIITokenizationService(storage=storage_backend, kek_keys=fernet_key)
