"""
Tests for Sanic adapter.
"""
import pytest
from sanic import Sanic
from sanic_testing import TestManager

from piisafe.adapters.sanic import SanicAdapter


@pytest.fixture
def app(pii_service):
    """Create a Sanic app with the PII blueprint."""
    app = Sanic("test_app")
    adapter = SanicAdapter(service=pii_service)
    blueprint = adapter.get_router()
    app.blueprint(blueprint)
    TestManager(app)
    return app


def test_tokenize_endpoint(app):
    """Test the tokenize endpoint."""
    _, response = app.test_client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com", "ssn": "123-45-6789"}}
    )
    
    assert response.status == 201
    assert "token" in response.json
    assert len(response.json["token"]) > 0


def test_retrieve_endpoint(app):
    """Test the retrieve endpoint."""
    # First tokenize
    _, tokenize_response = app.test_client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.json["token"]
    
    # Then retrieve
    _, response = app.test_client.get(f"/pii/retrieve/{token}")
    
    assert response.status == 200
    assert response.json["data"]["email"] == "test@example.com"


def test_retrieve_nonexistent_token(app):
    """Test retrieving a token that doesn't exist returns 404."""
    _, response = app.test_client.get("/pii/retrieve/nonexistent-token")
    
    assert response.status == 404
    assert response.json["error"] == "PII_TOKEN_NOT_FOUND"


def test_update_endpoint(app):
    """Test the update endpoint."""
    # First tokenize
    _, tokenize_response = app.test_client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.json["token"]
    
    # Then update
    _, response = app.test_client.put(
        f"/pii/update/{token}",
        json={"data": {"email": "updated@example.com", "phone": "555-1234"}}
    )
    
    assert response.status == 200
    assert response.json["token"] == token
    
    # Verify update
    _, retrieve_response = app.test_client.get(f"/pii/retrieve/{token}")
    assert retrieve_response.json["data"]["email"] == "updated@example.com"
    assert retrieve_response.json["data"]["phone"] == "555-1234"


def test_update_nonexistent_token(app):
    """Test updating a token that doesn't exist returns 404."""
    _, response = app.test_client.put(
        "/pii/update/nonexistent-token",
        json={"data": {"email": "test@example.com"}}
    )
    
    assert response.status == 404
    assert response.json["error"] == "PII_TOKEN_NOT_FOUND"


def test_delete_endpoint(app):
    """Test the delete endpoint."""
    # First tokenize
    _, tokenize_response = app.test_client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.json["token"]
    
    # Then delete
    _, response = app.test_client.delete(f"/pii/delete/{token}")
    
    assert response.status == 204
    
    # Verify deletion
    _, retrieve_response = app.test_client.get(f"/pii/retrieve/{token}")
    assert retrieve_response.status == 404


def test_delete_nonexistent_token(app):
    """Test deleting a token that doesn't exist returns 404."""
    _, response = app.test_client.delete("/pii/delete/nonexistent-token")
    
    assert response.status == 404
    assert response.json["error"] == "PII_TOKEN_NOT_FOUND"


def test_custom_prefix(pii_service):
    """Test creating a blueprint with custom prefix."""
    app = Sanic("test_app")
    adapter = SanicAdapter(service=pii_service, prefix="/custom")
    blueprint = adapter.get_router()
    app.blueprint(blueprint)
    TestManager(app)
    
    _, response = app.test_client.post(
        "/custom/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    
    assert response.status == 201


def test_validation_error(app):
    """Test that validation errors return 400."""
    _, response = app.test_client.post(
        "/pii/tokenize",
        json={"data": "not a dict"}
    )
    
    assert response.status == 400
    assert response.json["error"] == "VALIDATION_ERROR"
