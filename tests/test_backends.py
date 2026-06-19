"""
Tests for built-in storage backends.
"""
import pytest

from piisafe import PIITokenizationService
from piisafe.backends import InMemoryBackend


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def service(backend):
    key = b"test-kek-key-for-backend-tests-32b!"
    # Pad to valid Fernet key length
    from cryptography.fernet import Fernet
    return PIITokenizationService(storage=backend, kek_keys=Fernet.generate_key())


class TestInMemoryBackend:
    @pytest.mark.anyio
    async def test_store_and_get(self, backend):
        await backend.store_pii("tok1", "wrapped-pek", {"email": "encrypted"})
        result = await backend.get_pii("tok1")
        assert result == ("wrapped-pek", {"email": "encrypted"})

    @pytest.mark.anyio
    async def test_get_nonexistent(self, backend):
        result = await backend.get_pii("missing")
        assert result is None

    @pytest.mark.anyio
    async def test_update_existing(self, backend):
        await backend.store_pii("tok1", "old-pek", {"email": "old"})
        success = await backend.update_pii("tok1", "new-pek", {"email": "new"})
        assert success is True
        result = await backend.get_pii("tok1")
        assert result == ("new-pek", {"email": "new"})

    @pytest.mark.anyio
    async def test_update_nonexistent(self, backend):
        success = await backend.update_pii("missing", "pek", {"data": "x"})
        assert success is False

    @pytest.mark.anyio
    async def test_delete_existing(self, backend):
        await backend.store_pii("tok1", "pek", {"data": "x"})
        success = await backend.delete_pii("tok1")
        assert success is True
        assert await backend.get_pii("tok1") is None

    @pytest.mark.anyio
    async def test_delete_nonexistent(self, backend):
        success = await backend.delete_pii("missing")
        assert success is False

    def test_count(self, backend):
        assert backend.count() == 0

    @pytest.mark.anyio
    async def test_count_after_store(self, backend):
        await backend.store_pii("a", "pek", {})
        await backend.store_pii("b", "pek", {})
        assert backend.count() == 2

    @pytest.mark.anyio
    async def test_clear(self, backend):
        await backend.store_pii("a", "pek", {})
        await backend.store_pii("b", "pek", {})
        backend.clear()
        assert backend.count() == 0

    @pytest.mark.anyio
    async def test_roundtrip_with_service(self, service, backend):
        pii = {"email": "test@example.com", "ssn": "123-45-6789"}
        token = await service.tokenize_pii(pii)
        assert backend.count() == 1
        retrieved = await service.retrieve_pii(token)
        assert retrieved == pii

    @pytest.mark.anyio
    async def test_list_tokens(self, backend):
        await backend.store_pii("a", "pek", {})
        await backend.store_pii("b", "pek", {})
        await backend.store_pii("c", "pek", {})
        tokens = await backend.list_tokens()
        assert sorted(tokens) == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_list_tokens_empty(self, backend):
        tokens = await backend.list_tokens()
        assert tokens == []
