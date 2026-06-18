"""
Tests for Flask adapter.
"""
import pytest
from flask import Flask

from python_pii.adapters.flask import FlaskAdapter


@pytest.fixture
def app(pii_service):
    """Create a Flask app with the PII blueprint."""
    app = Flask(__name__)
    adapter = FlaskAdapter(service=pii_service)
    blueprint = adapter.get_router()
    app.register_blueprint(blueprint)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


def test_tokenize_endpoint(client):
    """Test the tokenize endpoint."""
    response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com", "ssn": "123-45-6789"}}
    )
    
    assert response.status_code == 201
    data = response.get_json()
    assert "token" in data
    assert len(data["token"]) > 0


def test_retrieve_endpoint(client):
    """Test the retrieve endpoint."""
    # First tokenize
    tokenize_response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.get_json()["token"]
    
    # Then retrieve
    response = client.get(f"/pii/retrieve/{token}")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["data"]["email"] == "test@example.com"


def test_retrieve_nonexistent_token(client):
    """Test retrieving a token that doesn't exist returns 404."""
    response = client.get("/pii/retrieve/nonexistent-token")
    
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "PII_TOKEN_NOT_FOUND"


def test_update_endpoint(client):
    """Test the update endpoint."""
    # First tokenize
    tokenize_response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.get_json()["token"]
    
    # Then update
    response = client.put(
        f"/pii/update/{token}",
        json={"data": {"email": "updated@example.com", "phone": "555-1234"}}
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["token"] == token
    
    # Verify update
    retrieve_response = client.get(f"/pii/retrieve/{token}")
    assert retrieve_response.get_json()["data"]["email"] == "updated@example.com"
    assert retrieve_response.get_json()["data"]["phone"] == "555-1234"


def test_update_nonexistent_token(client):
    """Test updating a token that doesn't exist returns 404."""
    response = client.put(
        "/pii/update/nonexistent-token",
        json={"data": {"email": "test@example.com"}}
    )
    
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "PII_TOKEN_NOT_FOUND"


def test_delete_endpoint(client):
    """Test the delete endpoint."""
    # First tokenize
    tokenize_response = client.post(
        "/pii/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    token = tokenize_response.get_json()["token"]
    
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
    data = response.get_json()
    assert data["error"] == "PII_TOKEN_NOT_FOUND"


def test_custom_prefix(pii_service):
    """Test creating a blueprint with custom prefix."""
    app = Flask(__name__)
    adapter = FlaskAdapter(service=pii_service, prefix="/custom")
    blueprint = adapter.get_router()
    app.register_blueprint(blueprint)
    
    client = app.test_client()
    response = client.post(
        "/custom/tokenize",
        json={"data": {"email": "test@example.com"}}
    )
    
    assert response.status_code == 201


def test_validation_error(client):
    """Test that validation errors return 400."""
    response = client.post(
        "/pii/tokenize",
        json={"data": "not a dict"}
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "VALIDATION_ERROR"
