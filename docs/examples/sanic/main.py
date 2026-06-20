"""
Minimal Sanic app using piisafe for PII tokenization.

Run:
    export FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    export API_KEY=your-secret-api-key
    python docs/examples/sanic/main.py
"""
import os

from sanic import Sanic, json
from sanic.request import Request

from piisafe import (
    InMemoryBackend,
    PIITokenizationService,
)

app = Sanic("pii-example")
storage = InMemoryBackend()
service = PIITokenizationService(storage=storage)


# --- Auth ---

def require_api_key(request: Request):
    expected = os.environ.get("API_KEY")
    api_key = request.headers.get("X-API-Key")
    if not expected or api_key != expected:
        return json({"error": "UNAUTHORIZED", "message": "Invalid API key"}, status=401)
    return None


# --- Endpoints ---

@app.post("/pii/tokenize")
async def tokenize_pii(request: Request):
    auth_err = require_api_key(request)
    if auth_err:
        return auth_err
    data = request.json
    token = await service.tokenize_pii(data["data"])
    return json({"token": token}, status=201)


@app.post("/pii/retrieve")
async def retrieve_pii(request: Request):
    auth_err = require_api_key(request)
    if auth_err:
        return auth_err
    token = (request.json or {}).get("token")
    if not token:
        return json({"error": "BAD_REQUEST", "message": "token required"}, status=400)
    pii_data = await service.retrieve_pii(token)
    if pii_data is None:
        return json({"error": "NOT_FOUND", "message": "Token not found"}, status=404)
    resp = json({"data": pii_data}, status=200)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.put("/pii/update/<token>")
async def update_pii(request: Request, token: str):
    auth_err = require_api_key(request)
    if auth_err:
        return auth_err
    data = request.json
    success = await service.update_pii(token, data["data"])
    if not success:
        return json({"error": "NOT_FOUND", "message": "Token not found"}, status=404)
    return json({"token": token})


@app.delete("/pii/delete/<token>")
async def delete_pii(request: Request, token: str):
    auth_err = require_api_key(request)
    if auth_err:
        return auth_err
    success = await service.delete_pii(token)
    if not success:
        return json({"error": "NOT_FOUND", "message": "Token not found"}, status=404)
    return json({}, status=204)


if __name__ == "__main__":
    app.run(port=8000)
