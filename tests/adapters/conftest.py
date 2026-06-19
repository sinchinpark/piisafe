"""
Shared fixtures for adapter tests.
"""
import pytest
from cryptography.fernet import Fernet

from python_pii import PIITokenizationService
from tests.conftest import InMemoryPIIBackend


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
    return PIITokenizationService(storage=storage_backend, kek_key=fernet_key)
