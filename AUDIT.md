# python-pii Security, DX & Architecture Audit

> **Scope:** `python-pii` v0.1.0 — framework-agnostic PII tokenization for SMEs, sole-founders, and startups.  
> **Date:** 2026-06-19  
> **Auditor:** Security-focused architectural review (automated + manual).  
> **Audience:** Package maintainers. Not a compliance certification.

---

## Executive Summary

The core cryptographic design (PEK/KEK hierarchy with Fernet) is sound and appropriate for the target audience. The package ships with no authentication layer, leaks internal error details in some paths, has an inconsistent exception-handling story across adapters, and is missing several DX affordances that would make it production-ready for its stated audience. None of the issues are catastrophic given the non-enterprise scope, but several should be addressed before a 1.0 release.

---

## 1. Security Issues

### 1.1 [HIGH] No Authentication or Authorization on Any Endpoint

**Files:** `adapters/fastapi.py`, `adapters/flask.py`, `adapters/sanic.py`

All three adapters expose `/tokenize`, `/retrieve/<token>`, `/update/<token>`, and `/delete/<token>` with zero access control. Any caller who can reach the service can read, write, or delete any PII record by guessing or replaying a token.

**Impact:** Complete PII exfiltration if the service is reachable from an untrusted network.

**Recommendation:**
- Add an optional `auth_dependency` / middleware hook to `BaseAdapter.__init__` so integrators can inject their own API-key, JWT, or session check without forking the adapter.
- Document clearly in the README that the endpoints **must** sit behind authentication and must not be exposed to the public internet without it.
- Consider shipping a simple built-in API-key middleware as a reference implementation.

```python
# Example hook in BaseAdapter
def __init__(self, service, prefix="/pii", auth_middleware=None):
    self.auth_middleware = auth_middleware  # callable or None
```

---

### 1.2 [HIGH] Internal Exception Details Leaked to Callers

**File:** `service.py`, lines ~65 and ~75

```python
raise PIIEncryptionError(f"Failed to encrypt PII data: {str(e)}")
raise PIIDecryptionError(f"Failed to decrypt PII data: {str(e)}")
```

The raw `str(e)` from the underlying `cryptography` library is forwarded into the exception message, which is then serialised directly into HTTP responses by all three adapters. This can expose internal library paths, key material hints, or stack-frame information to an attacker.

**Recommendation:** Log the original exception internally (to stderr or a logger) and raise a generic, fixed message to the caller.

```python
import logging
log = logging.getLogger(__name__)

except Exception as e:
    log.exception("Encryption failure")
    raise PIIEncryptionError("Failed to encrypt PII data")
```

---

### 1.3 [MEDIUM] Token Enumeration / Timing Oracle

**File:** `service.py` — `retrieve_pii`, `update_pii`, `delete_pii`

All three operations return `None` / `False` for a missing token, which the adapters translate to a `404`. This is correct behaviour, but the response time for a valid-but-deleted token vs. a never-existing token may differ depending on the storage backend, enabling timing-based enumeration.

**Recommendation:** Document that storage backends should use constant-time lookups where possible. Consider adding `hmac.compare_digest` token validation before hitting storage.

---

### 1.4 [MEDIUM] No Token Format Validation Before Storage Lookup

**Files:** `adapters/fastapi.py`, `adapters/flask.py`, `adapters/sanic.py`

The `token` path parameter is passed directly to `storage.get_pii(token)` / `storage.delete_pii(token)` without any format check. A malformed or oversized token (e.g., 10 KB string, SQL injection attempt, path traversal) reaches the storage backend unfiltered.

`PIITokenInvalidError` exists in `exceptions.py` but is never raised by any adapter.

**Recommendation:** Validate the token format (e.g., regex against `[A-Za-z0-9_-]{16,32}`) in the adapters or in `PIITokenizationService` before delegating to storage, and raise `PIITokenInvalidError` on mismatch.

```python
import re
TOKEN_RE = re.compile(r'^[A-Za-z0-9_\-]{16,43}$')

def _validate_token(token: str) -> None:
    if not TOKEN_RE.match(token):
        raise PIITokenInvalidError()
```

---

### 1.5 [MEDIUM] KEK Stored as Plain Instance Attribute

**File:** `service.py`

```python
self.kek = Fernet(kek_key)
```

The `Fernet` object (which holds the raw key bytes) is stored as a public instance attribute. Any code with a reference to the service object can read `service.kek._signing_key` or `service.kek._encryption_key` directly.

**Recommendation:** Name it `_kek` (private by convention) and add a note in the docstring that the attribute must not be serialised or logged.

---

### 1.6 [LOW] `FERNET_KEY` Environment Variable Name Is Too Generic

**File:** `service.py`

`FERNET_KEY` is a very common name that could collide with other libraries or be accidentally overridden. It also gives no hint that it is a PII master key.

**Recommendation:** Rename to `PII_KEK` or `PYTHON_PII_KEK` and update the README accordingly.

---

### 1.7 [LOW] No Key Validation on Startup

**File:** `service.py`

`Fernet(kek_key)` will raise a `ValueError` if the key is not a valid 32-byte URL-safe base64 string, but the error message is not caught and will surface as an unhandled exception at service construction time with no helpful context.

**Recommendation:** Wrap the `Fernet(kek_key)` call and re-raise as `PIIKeyError` with a clear message.

```python
try:
    self._kek = Fernet(kek_key)
except (ValueError, Exception) as e:
    raise PIIKeyError(f"Invalid KEK: {e}") from e
```

---

### 1.8 [LOW] No Rate Limiting

All adapters expose write and read endpoints with no rate limiting. For a service holding PII, this enables brute-force token guessing and denial-of-service via large payloads (within the `MAX_VALUE_LENGTH` limit).

**Recommendation:** Document that a reverse proxy (nginx, Caddy) or framework middleware should enforce rate limits. Consider adding a note in the README with a concrete example.

---

## 2. Architectural Issues

### 2.1 [HIGH] FastAPI Adapter Does Not Wire Exception Handlers

**File:** `adapters/fastapi.py`

The Flask and Sanic adapters register `PIIError` exception handlers on their blueprints. The FastAPI adapter does **not**. `PIIError` subclasses raised inside route handlers will propagate as unhandled exceptions and return a generic `500 Internal Server Error` instead of the intended status code (e.g., `404` for `PIITokenNotFoundError`).

`_handle_exception` returns a plain `dict` but is never called from within the router.

**Recommendation:** Register an exception handler on the `APIRouter` or document that the integrator must add one to the `FastAPI` app:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

# In get_router() or as a helper method:
async def pii_exception_handler(request: Request, exc: PIIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message}
    )

# Integrators must register:
app.add_exception_handler(PIIError, pii_exception_handler)
```

Expose `pii_exception_handler` as a public attribute of `FastAPIAdapter` so integrators don't have to write it themselves.

---

### 2.2 [MEDIUM] Flask Adapter Creates a New Event Loop Per Request

**File:** `adapters/flask.py`

```python
def async_route(f):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
```

Creating and destroying an event loop on every HTTP request is expensive and prevents sharing async resources (e.g., an async DB connection pool) across requests. It also sets the global event loop, which is not thread-safe.

**Recommendation:**
- For Flask ≥ 2.0 with async support enabled (`flask[async]`), use Flask's native async route support instead.
- If the shim must be kept, use `asyncio.run()` (Python 3.11+) which is safer, or document the limitation clearly.

---

### 2.3 [MEDIUM] `update_pii` Replaces All Fields — No Partial Update

**File:** `service.py` — `update_pii`

The update operation re-encrypts and replaces the entire record. There is no way to update a single field without re-supplying all fields. This is a footgun: a caller who only wants to update `email` must also pass `ssn`, `dob`, etc., or those fields will be silently dropped.

**Recommendation:**
- Add a `patch_pii(token, partial_data)` method that merges with the existing record.
- Or document the replace-all semantics prominently in the docstring and README.

---

### 2.4 [MEDIUM] No Audit / Access Log

There is no logging of who accessed, created, updated, or deleted a PII record. For any regulated context (GDPR Art. 30, CCPA) an access log is a baseline requirement.

**Recommendation:** Add optional structured logging (Python `logging` module) to `PIITokenizationService` for each operation: `tokenize`, `retrieve`, `update`, `delete`. Log the token (not the PII), a timestamp, and optionally a caller-supplied `request_id`.

---

### 2.5 [LOW] No Token Expiry / TTL Support

Tokens are permanent. A token issued for a one-time KYC flow remains valid indefinitely, increasing the attack surface over time.

**Recommendation:** Add an optional `ttl_seconds` parameter to `tokenize_pii` and `store_pii` in the protocol. Storage backends that support TTL (Redis, DynamoDB) can implement it natively; others can store an `expires_at` field and check it on retrieval.

---

### 2.6 [LOW] No Key Rotation Support

If the KEK is compromised, there is no mechanism to re-wrap all PEKs with a new KEK without re-implementing the entire key hierarchy from scratch.

**Recommendation:** Add a `rotate_kek(new_kek_key)` method to `PIITokenizationService` and a corresponding `list_tokens()` method to `PIIStorageBackend`. Document this as a planned feature (it is already on the roadmap).

---

### 2.7 [LOW] `PIIStorageBackend` Protocol Is Not Enforced at Runtime

**File:** `protocols.py`

`@runtime_checkable` allows `isinstance(obj, PIIStorageBackend)` checks, but Python's structural subtyping only checks for method *existence*, not signatures. A backend that implements `store_pii` with the wrong signature will pass the check silently.

**Recommendation:** Add a `validate_backend(storage)` helper that calls `isinstance` and optionally runs a smoke-test against an in-memory fixture. Document this in the "Writing a Custom Backend" section of the README.

---

## 3. Developer Experience (DX) Issues

### 3.1 [HIGH] No Built-in Storage Backend Provided

The package ships zero concrete storage backends. Every integrator must implement `PIIStorageBackend` from scratch before they can run a single line of working code. For the target audience (sole-founders, startups), this is a significant barrier.

**Recommendation:** Ship at minimum:
- `InMemoryBackend` — for testing and local development (already implied by tests but not exported).
- `SQLiteBackend` — zero-dependency, file-based, suitable for small deployments.

Document these in the README with copy-paste quickstart examples.

---

### 3.2 [HIGH] README Quickstart Requires Too Many Steps Before "Hello World"

The README asks the reader to implement a storage backend before showing any working output. For the target audience this is a conversion killer.

**Recommendation:** Lead with a 10-line end-to-end example using a built-in `InMemoryBackend`, then explain the protocol for custom backends.

---

### 3.3 [MEDIUM] Inconsistent Request/Response Models Across Adapters

- **FastAPI:** Uses Pydantic `PIIDataRequest` / `TokenResponseModel` (defined locally in the adapter).
- **Flask / Sanic:** Use `PIIData` / `TokenResponse` dataclasses from `models.py`.

The Pydantic models duplicate the validation logic already in `PIIData.__post_init__`. The `MAX_FIELDS`, `MAX_KEY_LENGTH`, `MAX_VALUE_LENGTH` limits are enforced in `models.py` but **not** in the Pydantic models, so the FastAPI adapter silently accepts oversized payloads that would be rejected by the Flask/Sanic adapters.

**Recommendation:** Define a single canonical Pydantic v2 model (or keep the dataclass and add a `from_dict` classmethod) and reuse it across all adapters. Apply the same validation constraints everywhere.

---

### 3.4 [MEDIUM] `PIITokenInvalidError` Is Defined But Never Used

**File:** `exceptions.py`, `adapters/*`

`PIITokenInvalidError` is exported in `__init__.py` but no adapter or service method ever raises it. This creates a false expectation for integrators who write `except PIITokenInvalidError` handlers that will never fire.

**Recommendation:** Either raise it on token format validation (see §1.4) or remove it from the public API until it is used.

---

### 3.5 [MEDIUM] No `generate_kek()` Helper

Integrators must know to call `Fernet.generate_key()` from the `cryptography` library to bootstrap the service. This leaks an implementation detail and requires an extra dependency import.

**Recommendation:** Export a `generate_kek() -> bytes` helper from `python_pii`:

```python
# python_pii/__init__.py
from python_pii.service import PIITokenizationService

def generate_kek() -> bytes:
    """Generate a new Key Encryption Key suitable for PIITokenizationService."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key()
```

---

### 3.6 [LOW] `TokenResponse` Dataclass Adds No Value

**File:** `models.py`

`TokenResponse` is a dataclass wrapping a single `str`. It is used in Flask/Sanic adapters only to be immediately unpacked (`response.token`). It adds boilerplate without benefit.

**Recommendation:** Remove it and return the token string directly, or keep it only if a richer response (e.g., `expires_at`) is planned.

---

### 3.7 [LOW] `verify_package.py` Is Committed to the Repository Root

**File:** `verify_package.py`

This appears to be a development/smoke-test script. Committing ad-hoc scripts to the repo root creates confusion about what is canonical.

**Recommendation:** Move it to `scripts/` or `examples/`, or convert it to a proper pytest test.

---

### 3.8 [LOW] No `py.typed` Marker

The package has no `py.typed` marker file, so type checkers (mypy, pyright) will ignore its type annotations when used as a dependency.

**Recommendation:** Add an empty `python_pii/py.typed` file and declare it in `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["python_pii"]
artifacts = ["python_pii/py.typed"]
```

---

### 3.9 [LOW] `session-ses_1260.md` Committed to Repository Root

This appears to be an IDE/AI session artifact. It should not be in version control.

**Recommendation:** Add `session-*.md` to `.gitignore`.

---

## 4. Summary Table

| # | Severity | Category | Title |
|---|----------|----------|-------|
| 1.1 | 🔴 HIGH | Security | No authentication on any endpoint |
| 1.2 | 🔴 HIGH | Security | Internal exception details leaked to callers |
| 1.3 | 🟠 MEDIUM | Security | Token enumeration / timing oracle |
| 1.4 | 🟠 MEDIUM | Security | No token format validation before storage lookup |
| 1.5 | 🟠 MEDIUM | Security | KEK stored as public instance attribute |
| 1.6 | 🟡 LOW | Security | `FERNET_KEY` env var name too generic |
| 1.7 | 🟡 LOW | Security | No key validation on startup |
| 1.8 | 🟡 LOW | Security | No rate limiting guidance |
| 2.1 | 🔴 HIGH | Architecture | FastAPI adapter does not wire exception handlers |
| 2.2 | 🟠 MEDIUM | Architecture | Flask adapter creates new event loop per request |
| 2.3 | 🟠 MEDIUM | Architecture | `update_pii` silently drops unspecified fields |
| 2.4 | 🟠 MEDIUM | Architecture | No audit / access log |
| 2.5 | 🟡 LOW | Architecture | No token expiry / TTL support |
| 2.6 | 🟡 LOW | Architecture | No key rotation support |
| 2.7 | 🟡 LOW | Architecture | Protocol not enforced at runtime |
| 3.1 | 🔴 HIGH | DX | No built-in storage backend |
| 3.2 | 🔴 HIGH | DX | README quickstart requires too many steps |
| 3.3 | 🟠 MEDIUM | DX | Inconsistent models / validation across adapters |
| 3.4 | 🟠 MEDIUM | DX | `PIITokenInvalidError` defined but never raised |
| 3.5 | 🟠 MEDIUM | DX | No `generate_kek()` helper exported |
| 3.6 | 🟡 LOW | DX | `TokenResponse` dataclass adds no value |
| 3.7 | 🟡 LOW | DX | `verify_package.py` in repo root |
| 3.8 | 🟡 LOW | DX | No `py.typed` marker |
| 3.9 | 🟡 LOW | DX | Session artifact committed to repo |

---

## 5. Recommended Fix Priority

**Before any public release (must-fix):**
1. §1.1 — Add auth hook to `BaseAdapter`
2. §1.2 — Stop leaking `str(e)` into HTTP responses
3. §2.1 — Wire FastAPI exception handler
4. §3.1 — Ship `InMemoryBackend` and `SQLiteBackend`
5. §3.2 — Rewrite README quickstart

**Before v1.0 (should-fix):**
6. §1.4 — Token format validation + use `PIITokenInvalidError`
7. §1.5 — Make `kek` private (`_kek`)
8. §2.2 — Fix Flask async event loop handling
9. §2.3 — Document or fix replace-all update semantics
10. §2.4 — Add optional structured logging
11. §3.3 — Unify validation models across adapters
12. §3.5 — Export `generate_kek()` helper

**Nice to have (post-v1.0):**
- §1.6, §1.7, §1.8, §2.5, §2.6, §2.7, §3.4, §3.6–3.9
