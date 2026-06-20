"""
Minimal FastAPI app using piisafe for PII tokenization.

Run:
    export FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    export API_KEY=your-secret-api-key
    uvicorn docs.examples.fastapi.main:app --reload
"""
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from piisafe import (
    InMemoryBackend,
    PIIError,
    PIITokenizationService,
)

app = FastAPI()
storage = InMemoryBackend()
service = PIITokenizationService(storage=storage)


# --- Auth ---

def verify_api_key(x_api_key: str = Header(alias="X-API-Key")):
    expected = os.environ.get("API_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


# --- Exception handler ---

@app.exception_handler(PIIError)
async def pii_error_handler(request, exc: PIIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message},
    )


# --- Request/response models ---

class PIIDataRequest(BaseModel):
    data: dict[str, str]


class TokenRequest(BaseModel):
    token: str


# --- Endpoints ---

@app.post("/pii/tokenize", status_code=201)
async def tokenize_pii(body: PIIDataRequest, _: None = Depends(verify_api_key)):
    token = await service.tokenize_pii(body.data)
    return {"token": token}


@app.post("/pii/retrieve")
async def retrieve_pii(body: TokenRequest, _: None = Depends(verify_api_key)):
    pii_data = await service.retrieve_pii(body.token)
    if pii_data is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return JSONResponse(
        content={"data": pii_data},
        headers={"Cache-Control": "no-store"},
    )


@app.put("/pii/update/{token}")
async def update_pii(token: str, body: PIIDataRequest, _: None = Depends(verify_api_key)):
    success = await service.update_pii(token, body.data)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"token": token}


@app.delete("/pii/delete/{token}", status_code=204)
async def delete_pii(token: str, _: None = Depends(verify_api_key)):
    success = await service.delete_pii(token)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
