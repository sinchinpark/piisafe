"""
Minimal Flask app using piisafe for PII tokenization.

Run:
    export FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    export API_KEY=your-secret-api-key
    flask --app docs.examples.flask.main run
"""
import asyncio
import os
from functools import wraps

from flask import Flask, jsonify, request

from piisafe import (
    InMemoryBackend,
    PIITokenizationService,
)

app = Flask(__name__)
storage = InMemoryBackend()
service = PIITokenizationService(storage=storage)


# --- Auth ---

def require_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        expected = os.environ.get("API_KEY")
        api_key = request.headers.get("X-API-Key")
        if not expected or api_key != expected:
            return jsonify({"error": "UNAUTHORIZED", "message": "Invalid API key"}), 401
        return f(*args, **kwargs)
    return wrapper


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Endpoints ---

@app.route("/pii/tokenize", methods=["POST"])
@require_api_key
def tokenize_pii():
    data = request.get_json()
    token = run_async(service.tokenize_pii(data["data"]))
    return jsonify({"token": token}), 201


@app.route("/pii/retrieve", methods=["POST"])
@require_api_key
def retrieve_pii():
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if not token:
        return jsonify({"error": "BAD_REQUEST", "message": "token required"}), 400
    pii_data = run_async(service.retrieve_pii(token))
    if pii_data is None:
        return jsonify({"error": "NOT_FOUND", "message": "Token not found"}), 404
    response = jsonify({"data": pii_data})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/pii/update/<token>", methods=["PUT"])
@require_api_key
def update_pii(token):
    data = request.get_json()
    success = run_async(service.update_pii(token, data["data"]))
    if not success:
        return jsonify({"error": "NOT_FOUND", "message": "Token not found"}), 404
    return jsonify({"token": token})


@app.route("/pii/delete/<token>", methods=["DELETE"])
@require_api_key
def delete_pii(token):
    success = run_async(service.delete_pii(token))
    if not success:
        return jsonify({"error": "NOT_FOUND", "message": "Token not found"}), 404
    return "", 204
