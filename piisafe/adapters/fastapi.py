"""
FastAPI adapter for PII tokenization service.
"""
from typing import Dict, Optional

from fastapi import APIRouter, Header, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from piisafe.adapters.base import BaseAdapter
from piisafe.exceptions import PIIError, PIITokenNotFoundError
from piisafe.service import PIITokenizationService


# Pydantic models for FastAPI validation
class PIIDataRequest(BaseModel):
    """Pydantic model for PII data requests."""
    data: Dict[str, str]


class RetrieveRequest(BaseModel):
    """Pydantic model for PII retrieve requests."""
    token: str


class TokenResponseModel(BaseModel):
    """Pydantic model for token responses."""
    token: str


class FastAPIAdapter(BaseAdapter):
    """FastAPI adapter for PII tokenization service."""
    
    def __init__(
        self, 
        service: PIITokenizationService, 
        prefix: str = "/pii",
        tags: list[str] | None = None
    ):
        """
        Initialize the FastAPI adapter.
        
        Args:
            service: The PIITokenizationService instance to use.
            prefix: URL prefix for all routes (default: "/pii").
            tags: OpenAPI tags for the routes (default: ["PII"]).
        """
        super().__init__(service, prefix)
        self.tags = tags or ["PII"]
    
    def get_router(self) -> APIRouter:
        """Create and return a FastAPI router with PII endpoints."""
        router = APIRouter(prefix=self.prefix, tags=self.tags)
        
        # Endpoints
        @router.post("/tokenize", response_model=TokenResponseModel, status_code=status.HTTP_201_CREATED)
        async def tokenize_pii(pii_data: PIIDataRequest) -> TokenResponseModel:
            """Tokenize PII data."""
            token = await self.service.tokenize_pii(pii_data.data)
            return TokenResponseModel(token=token)
        
        @router.post("/retrieve", response_model=PIIDataRequest)
        async def retrieve_pii(
            body: Optional[RetrieveRequest] = None,
            x_pii_token: Optional[str] = Header(default=None, alias="X-PII-Token"),
        ) -> PIIDataRequest:
            """Retrieve PII data using a token from body or header."""
            token = (body.token if body else None) or x_pii_token
            if not token:
                raise PIITokenNotFoundError("Token required in body or X-PII-Token header")
            pii_data = await self.service.retrieve_pii(token)
            if pii_data is None:
                raise PIITokenNotFoundError("PII data not found for the provided token")
            response = JSONResponse(content={"data": pii_data})
            response.headers["Cache-Control"] = "no-store"
            return response
        
        @router.put("/update/{token}", response_model=TokenResponseModel)
        async def update_pii(token: str, pii_data: PIIDataRequest) -> TokenResponseModel:
            """Update PII data for an existing token."""
            success = await self.service.update_pii(token, pii_data.data)
            if not success:
                raise PIITokenNotFoundError("PII data not found for the provided token")
            return TokenResponseModel(token=token)
        
        @router.delete("/delete/{token}", status_code=status.HTTP_204_NO_CONTENT)
        async def delete_pii(token: str) -> None:
            """Delete PII data for a token."""
            success = await self.service.delete_pii(token)
            if not success:
                raise PIITokenNotFoundError("PII data not found for the provided token")
        
        return router
    
    def _handle_exception(self, exc: PIIError) -> dict:
        """Convert PIIError to error dict (for app-level exception handler)."""
        return {
            "status_code": exc.status_code,
            "content": {"error": exc.code, "message": exc.message}
        }
