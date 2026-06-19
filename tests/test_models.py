"""
Tests for data models.
"""
import pytest

from piisafe.models import PIIData, TokenResponse


def test_pii_data_valid():
    """Test PIIData with valid data."""
    pii_data = PIIData(data={"email": "test@example.com", "ssn": "123-45-6789"})
    assert pii_data.data == {"email": "test@example.com", "ssn": "123-45-6789"}


def test_pii_data_empty():
    """Test PIIData with empty dict."""
    pii_data = PIIData(data={})
    assert pii_data.data == {}


def test_pii_data_default():
    """Test PIIData with default factory."""
    pii_data = PIIData()
    assert pii_data.data == {}


def test_pii_data_invalid_type():
    """Test PIIData with invalid type raises TypeError."""
    with pytest.raises(TypeError, match="data must be a dictionary"):
        PIIData(data="not a dict")


def test_pii_data_invalid_key_type():
    """Test PIIData with non-string keys raises TypeError."""
    with pytest.raises(TypeError, match="all keys and values must be strings"):
        PIIData(data={1: "value"})


def test_pii_data_invalid_value_type():
    """Test PIIData with non-string values raises TypeError."""
    with pytest.raises(TypeError, match="all keys and values must be strings"):
        PIIData(data={"key": 123})


def test_token_response_valid():
    """Test TokenResponse with valid token."""
    response = TokenResponse(token="abc123xyz")
    assert response.token == "abc123xyz"


def test_token_response_empty_string():
    """Test TokenResponse with empty string raises ValueError."""
    with pytest.raises(ValueError, match="token must be a non-empty string"):
        TokenResponse(token="")


def test_token_response_non_string():
    """Test TokenResponse with non-string raises ValueError."""
    with pytest.raises(ValueError, match="token must be a non-empty string"):
        TokenResponse(token=None)


def test_pii_data_too_many_fields():
    """Test PIIData with too many fields raises ValueError."""
    data = {f"field{i}": f"value{i}" for i in range(51)}
    with pytest.raises(ValueError, match="exceeds maximum of 50 fields"):
        PIIData(data=data)


def test_pii_data_key_too_long():
    """Test PIIData with key exceeding max length raises ValueError."""
    with pytest.raises(ValueError, match="key exceeds maximum length"):
        PIIData(data={"a" * 257: "value"})


def test_pii_data_value_too_long():
    """Test PIIData with value exceeding max length raises ValueError."""
    with pytest.raises(ValueError, match="value exceeds maximum length"):
        PIIData(data={"key": "a" * 10001})
