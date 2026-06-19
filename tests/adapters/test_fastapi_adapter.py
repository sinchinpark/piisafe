"""
Tests for FastAPI adapter.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from piisafe.adapters.fastapi import FastAPIAdapter
from piisafe.exceptions import PIIError


@pytest.fixture
def app(pii_service):
    """Create a FastAPI app with the PII router."""
    app = FastAPI()
    
    # Add exception handler at app level
    @app.exception_handler(PIIError)
    async def pii_error_handler(request: Request, exc: PIIError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message}
        )
    
    adapter = FastAPIAdapter(service=pii_service)
    router = adapter.get_router()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


def test_tokenize_endpoint(client):
    """Test the tokenize endpoint."""
    response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com", "ssn": "123-45-6789"}}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert len(data["token"]) > 0


def test_retrieve_endpoint(client):
    """Test the retrieve endpoint."""
    # First tokenize
    tokenize_response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.json()["token"]
    
    # Then retrieve
    response = client.get(f"/pii/retrieve/{token}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["email"] == "test@example.com"


def test_retrieve_nonexistent_token(client):
    """Test retrieving a token that doesn't exist returns 404."""
    response = client.get("/pii/retrieve/nonexistent-token")
    
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "PII_TOKEN_NOT_FOUND"


def test_update_endpoint(client):
    """Test the update endpoint."""
    # First tokenize
    tokenize_response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.json()["token"]
    
    # Then update
    response = client.put(
        f"/pii/update/{token}",
        json={"data": {"email": "updated@example.com", "phone": "555-1234"}}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == token
    
    # Verify update
    retrieve_response = client.get(f"/pii/retrieve/{token}")
    assert retrieve_response.json()["data"]["email"] == "updated@example.com"
    assert retrieve_response.json()["data"]["phone"] == "555-1234"


def test_update_nonexistent_token(client):
    """Test updating a token that doesn't exist returns 404."""
    response = client.put(
        "/pii/update/nonexistent-token",
        json={"data": {"email": "test@example.com"}}
    )
    
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "PII_TOKEN_NOT_FOUND"


def test_delete_endpoint(client):
    """Test the delete endpoint."""
    # First tokenize
    tokenize_response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.json()["token"]
    
    # Then delete
    response = client.delete(f"/pii/delete/{token}")
    
    assert response.status_code == 204
    
    # Verify deletion
    retrieve_response = client.get(f"/pii/retrieve/{token}")
    assert retrieve_response.status_code == 404


def test_delete_nonexistent_token(client):
    """Test deleting a token that doesn't exist returns 404."""
    response = client.delete("/pii/delete/nonexistent-token")
    
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "PII_TOKEN_NOT_FOUND"


def test_custom_prefix_and_tags(pii_service):
    """Test creating a router with custom prefix and tags."""
    app = FastAPI()
    
    # Add exception handler
    @app.exception_handler(PIIError)
    async def pii_error_handler(request: Request, exc: PIIError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message}
        )
    
    adapter = FastAPIAdapter(service=pii_service, prefix="/custom", tags=["Custom"])
    router = adapter.get_router()
    app.include_router(router)
    
    client = TestClient(app)
    response = client.post(
        "/custom/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    
    assert response.status_code == 201
