# piisafe

**⚠️ This package is not ready for production yet and is under heavy development.**

A framework-agnostic PII (Personally Identifiable Information) tokenization service for Python. Provides `PIITokenizationService` for encrypting, storing, and retrieving PII data — use it inside any web framework's endpoints.

## Features

- **Framework-agnostic**: No web framework dependencies — use with FastAPI, Sanic, Flask, Django, or anything else
- **Database-agnostic**: Implement the `PIIStorageBackend` protocol for any storage system
- **Encryption**: Fernet symmetric encryption with PEK/KEK key hierarchy
- **Token generation**: Secure URL-safe tokens via `secrets.token_urlsafe(16)`
- **Type-safe**: Full typing support with protocols and dataclasses
- **Async-first**: Service is fully async

## Installation

```bash
pip install piisafe
```

## Quick Start

```python
from cryptography.fernet import Fernet
from piisafe import PIITokenizationService, InMemoryBackend

storage = InMemoryBackend()
service = PIITokenizationService(storage=storage, kek_keys=Fernet.generate_key())

token = await service.tokenize_pii({"email": "alice@example.com"})
data = await service.retrieve_pii(token)
# data == {"email": "alice@example.com"}
```

## Service API

```python
# Tokenize PII data — returns a token
token = await service.tokenize_pii({"email": "user@example.com", "ssn": "123-45-6789"})

# Retrieve decrypted PII data
data = await service.retrieve_pii(token)

# Update PII data for an existing token
await service.update_pii(token, {"email": "new@example.com"})

# Delete PII data
await service.delete_pii(token)
```

## Framework Examples

Runnable example apps showing how to integrate piisafe into web frameworks with authentication:

- [`docs/examples/fastapi/`](docs/examples/fastapi/) — FastAPI with API key auth
- [`docs/examples/sanic/`](docs/examples/sanic/) — Sanic with API key auth
- [`docs/examples/flask/`](docs/examples/flask/) — Flask with API key auth

Each example includes `main.py` and `requirements.txt`.

## Configuration

### Encryption Key (KEK)

The `FERNET_KEY` environment variable or `kek_keys` parameter provides the Key Encryption Key (KEK).

```bash
# Generate a key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set it
export FERNET_KEY="your-generated-key-here"
```

Or pass it directly:

```python
from cryptography.fernet import Fernet

key = Fernet.generate_key()
pii_service = PIITokenizationService(storage=storage, kek_keys=key)
```

## Custom Storage Backend

`InMemoryBackend` is included for testing and development. For production, implement the `PIIStorageBackend` protocol with your database:

```python
from typing import Dict, Optional, Tuple
from piisafe import PIIStorageBackend

class PIIStorageBackend(Protocol):
    async def store_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> None: ...
    async def get_pii(self, token: str) -> Optional[Tuple[str, Dict[str, str]]]: ...
    async def update_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> bool: ...
    async def delete_pii(self, token: str) -> bool: ...
```

The `encrypted_pek` is the PEK wrapped by the KEK. Store it alongside the encrypted data.

### MariaDB/MySQL Example

```python
import json
from typing import Dict, Optional, Tuple
import aiomysql

class MariaDBPIIBackend:
    def __init__(self, db_pool: aiomysql.Pool, table_name: str = "pii_records"):
        self.pool = db_pool
        # SECURITY: table_name must be a trusted constant, never user input
        self.table_name = table_name
    
    async def store_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> None:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"INSERT INTO {self.table_name} (token, encrypted_pek, encrypted_data) VALUES (%s, %s, %s)",
                    (token, encrypted_pek, json.dumps(encrypted_data))
                )
                await conn.commit()
    
    async def get_pii(self, token: str) -> Optional[Tuple[str, Dict[str, str]]]:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"SELECT encrypted_pek, encrypted_data FROM {self.table_name} WHERE token = %s",
                    (token,)
                )
                result = await cursor.fetchone()
                return (result[0], json.loads(result[1])) if result else None
    
    async def update_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"UPDATE {self.table_name} SET encrypted_pek = %s, encrypted_data = %s WHERE token = %s",
                    (encrypted_pek, json.dumps(encrypted_data), token)
                )
                await conn.commit()
                return cursor.rowcount > 0
    
    async def delete_pii(self, token: str) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"DELETE FROM {self.table_name} WHERE token = %s",
                    (token,)
                )
                await conn.commit()
                return cursor.rowcount > 0
    
    async def list_tokens(self) -> list[str]:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"SELECT token FROM {self.table_name}")
                results = await cursor.fetchall()
                return [row[0] for row in results]
```

## Exception Handling

The package provides these exceptions:

- `PIIError` - Base exception (status_code, code, message attributes)
- `PIITokenNotFoundError` - 404: Token not found
- `PIITokenInvalidError` - 400: Invalid token format
- `PIIEncryptionError` - 500: Encryption failed
- `PIIDecryptionError` - 500: Decryption failed (invalid/tampered data)
- `PIIKeyError` - 500: Encryption key not configured

Catch `PIIError` in your framework's exception handler to convert these into appropriate HTTP responses. See the example apps for FastAPI and Sanic implementations.

## Data Models

The package uses standard library dataclasses:

```python
from piisafe import PIIData, TokenResponse

# PIIData - validates that data is Dict[str, str]
pii_data = PIIData(data={"email": "test@example.com"})

# TokenResponse - validates that token is non-empty string
response = TokenResponse(token="abc123")
```

## Testing

```bash
uv run pytest
```

## Architecture

```
piisafe/
├── piisafe/
│   ├── __init__.py          # Core exports
│   ├── protocols.py         # PIIStorageBackend Protocol
│   ├── exceptions.py        # Exception hierarchy
│   ├── service.py           # PIITokenizationService
│   ├── models.py            # Dataclass models
│   └── backends/
│       ├── __init__.py
│       └── inmemory.py      # InMemoryBackend
├── docs/examples/
│   ├── fastapi/             # FastAPI example app
│   ├── sanic/               # Sanic example app
│   └── flask/               # Flask example app
└── tests/
    ├── test_service.py      # Core service tests
    ├── test_models.py       # Model validation tests
    └── test_backends.py     # Backend tests
```

## Requirements

- Python >= 3.11
- cryptography >= 42

## License

MIT

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass: `uv run pytest`
2. Code follows existing style
3. New features include tests
4. Documentation is updated

## Security

**IMPORTANT: This library does not provide HTTP endpoints or authentication.** You are responsible for adding authentication and authorization in your own endpoints. See the example apps for patterns.

### Key Management

This package uses a **PEK/KEK key hierarchy**:

- **KEK (Key Encryption Key)**: Master key that wraps/unwraps PEKs. Set via `FERNET_KEY` env var or `kek_keys` parameter.
- **PEK (Presentation Encryption Key)**: Per-record key that encrypts/decrypts PII data. Generated automatically for each token.

This design limits blast radius — a compromised PEK exposes only one record.

```bash
# Generate a key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set it
export FERNET_KEY="your-generated-key-here"
```

### Best Practices

- Always use a secure `FERNET_KEY` in production
- Store the key securely (environment variables, secrets manager)
- Never commit keys to version control
- Use HTTPS in production to protect tokens in transit

## Roadmap

- [x] Key rotation support
- [ ] Additional storage backends (Redis, PostgreSQL)
- [ ] Token expiration/TTL
- [ ] Audit logging
- [ ] Batch operations
