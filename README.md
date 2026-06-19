# python-pii

A framework-agnostic PII (Personally Identifiable Information) tokenization service for Python web applications. Supports FastAPI, Flask, and Sanic through adapter classes.

## Features

- **Framework-agnostic core**: Zero dependencies on web frameworks
- **Multiple framework support**: Adapters for FastAPI, Flask, and Sanic
- **Database-agnostic**: Implement the `PIIStorageBackend` protocol for any storage system
- **Encryption**: Uses Fernet symmetric encryption (cryptography library)
- **Token generation**: Secure URL-safe tokens via `secrets.token_urlsafe(16)`
- **Type-safe**: Full typing support with protocols and dataclasses
- **Async-first**: Service is async-only; Flask adapter handles sync/async bridging

## Installation

### Core package only
```bash
pip install python-pii
```

### With framework support
```bash
# FastAPI
pip install python-pii[fastapi]

# Flask
pip install python-pii[flask]

# Sanic
pip install python-pii[sanic]

# All frameworks
pip install python-pii[all]
```

### With uv
```bash
uv add python-pii[fastapi]
```

## Quick Start

```python
from python_pii import PIITokenizationService, InMemoryBackend

storage = InMemoryBackend()
service = PIITokenizationService(storage=storage, kek_key=Fernet.generate_key())

token = await service.tokenize_pii({"email": "alice@example.com"})
data = await service.retrieve_pii(token)
# data == {"email": "alice@example.com"}
```

### Framework Examples

<details>
<summary>FastAPI</summary>

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from python_pii import PIITokenizationService, InMemoryBackend, PIIError
from python_pii.adapters.fastapi import FastAPIAdapter

app = FastAPI()
storage = InMemoryBackend()
service = PIITokenizationService(storage=storage)

@app.exception_handler(PIIError)
async def pii_error_handler(request: Request, exc: PIIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message}
    )

adapter = FastAPIAdapter(service=service, prefix="/pii", tags=["PII"])
app.include_router(adapter.get_router())
```
</details>

<details>
<summary>Flask</summary>

```python
from flask import Flask
from python_pii import PIITokenizationService, InMemoryBackend
from python_pii.adapters.flask import FlaskAdapter

app = Flask(__name__)
storage = InMemoryBackend()
service = PIITokenizationService(storage=storage)

adapter = FlaskAdapter(service=service, prefix="/pii")
app.register_blueprint(adapter.get_router())
```
</details>

<details>
<summary>Sanic</summary>

```python
from sanic import Sanic
from python_pii import PIITokenizationService, InMemoryBackend
from python_pii.adapters.sanic import SanicAdapter

app = Sanic("MyApp")
storage = InMemoryBackend()
service = PIITokenizationService(storage=storage)

adapter = SanicAdapter(service=service, prefix="/pii")
app.blueprint(adapter.get_router())
```
</details>

## API Endpoints

All adapters provide the same four endpoints:

### POST `/pii/tokenize`
Tokenize PII data.

**Request:**
```json
{
  "data": {
    "email": "user@example.com",
    "ssn": "123-45-6789"
  }
}
```

**Response (201):**
```json
{
  "token": "abc123xyz..."
}
```

### GET `/pii/retrieve/{token}`
Retrieve PII data using a token.

**Response (200):**
```json
{
  "data": {
    "email": "user@example.com",
    "ssn": "123-45-6789"
  }
}
```

### PUT `/pii/update/{token}`
Update PII data for an existing token.

**Request:**
```json
{
  "data": {
    "email": "newemail@example.com"
  }
}
```

**Response (200):**
```json
{
  "token": "abc123xyz..."
}
```

### DELETE `/pii/delete/{token}`
Delete PII data for a token.

**Response (204):** No content

## Configuration

### Encryption Key (KEK)

The `FERNET_KEY` environment variable or `kek_key` parameter provides the Key Encryption Key (KEK).

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
pii_service = PIITokenizationService(storage=storage, kek_key=key)
```

## Custom Storage Backend

`InMemoryBackend` is included for testing and development. For production, implement the `PIIStorageBackend` protocol with your database:

```python
from typing import Dict, Optional, Tuple
from python_pii import PIIStorageBackend

class PIIStorageBackend(Protocol):
    async def store_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> None: ...
    async def get_pii(self, token: str) -> Optional[Tuple[str, Dict[str, str]]]: ...
    async def update_pii(self, token: str, encrypted_pek: str, encrypted_data: Dict[str, str]) -> bool: ...
    async def delete_pii(self, token: str) -> bool: ...
```

The `encrypted_pek` is the PEK wrapped by the KEK. Store it alongside the encrypted data.

## Exception Handling

The package provides these exceptions:

- `PIIError` - Base exception (status_code, code, message attributes)
- `PIITokenNotFoundError` - 404: Token not found
- `PIITokenInvalidError` - 400: Invalid token format
- `PIIEncryptionError` - 500: Encryption failed
- `PIIDecryptionError` - 500: Decryption failed (invalid/tampered data)
- `PIIKeyError` - 500: Encryption key not configured

### FastAPI Exception Handling

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from python_pii import PIIError

@app.exception_handler(PIIError)
async def pii_error_handler(request: Request, exc: PIIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message}
    )
```

### Flask Exception Handling

Exception handling is built into the Flask adapter via `@bp.errorhandler(PIIError)`.

### Sanic Exception Handling

Exception handling is built into the Sanic adapter via `@bp.exception(PIIError)`.

## Example: MariaDB/MySQL Backend

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
```

## Data Models

The package uses standard library dataclasses:

```python
from python_pii import PIIData, TokenResponse

# PIIData - validates that data is Dict[str, str]
pii_data = PIIData(data={"email": "test@example.com"})

# TokenResponse - validates that token is non-empty string
response = TokenResponse(token="abc123")
```

## Testing

Run tests:

```bash
cd packages/python-pii
uv run pytest
```

Run tests for specific adapter:

```bash
uv run pytest tests/adapters/test_fastapi_adapter.py -v
```

## Architecture

```
python-pii/
├── python_pii/
│   ├── __init__.py          # Core exports
│   ├── protocols.py         # PIIStorageBackend Protocol
│   ├── exceptions.py        # Exception hierarchy
│   ├── service.py           # PIITokenizationService
│   ├── models.py            # Dataclass models
│   ├── backends/            # Built-in storage backends
│   │   ├── __init__.py
│   │   └── inmemory.py      # InMemoryBackend
│   └── adapters/
│       ├── base.py          # BaseAdapter ABC
│       ├── fastapi.py       # FastAPIAdapter
│       ├── flask.py         # FlaskAdapter
│       └── sanic.py         # SanicAdapter
└── tests/
    ├── test_service.py      # Core service tests
    ├── test_models.py       # Model validation tests
    ├── test_backends.py     # Backend tests
    └── adapters/
        ├── test_fastapi_adapter.py
        ├── test_flask_adapter.py
        └── test_sanic_adapter.py
```

## Migration from fastapi-pii

If you're migrating from the old `fastapi-pii` package:

**Before:**
```python
from fastapi_pii import create_pii_router
router = create_pii_router(service=pii_service)
```

**After:**
```python
from python_pii.adapters.fastapi import FastAPIAdapter
adapter = FastAPIAdapter(service=pii_service)
router = adapter.get_router()

# Don't forget to add exception handler at app level!
```

## Requirements

- Python >= 3.11
- cryptography >= 42

### Optional Framework Dependencies

- FastAPI >= 0.115 + pydantic >= 2.0
- Flask >= 2.3
- Sanic >= 23.0

## License

MIT

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass: `uv run pytest`
2. Code follows existing style
3. New features include tests
4. Documentation is updated

## Security

**IMPORTANT: The adapters expose unauthenticated endpoints.** You MUST add your own authentication/authorization layer before deploying in production:

- **FastAPI**: Use `Depends()` with OAuth2 or API key validation
- **Flask**: Use `@login_required` or similar middleware
- **Sanic**: Use Sanic's built-in middleware or authentication decorators

### Key Management

This package uses a **PEK/KEK key hierarchy**:

- **KEK (Key Encryption Key)**: Master key that wraps/unwraps PEKs. Set via `FERNET_KEY` env var or `kek_key` parameter.
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

- [ ] Key rotation support
- [ ] Additional storage backends (Redis, PostgreSQL)
- [ ] Token expiration/TTL
- [ ] Audit logging
- [ ] Batch operations
- [ ] Django adapter
