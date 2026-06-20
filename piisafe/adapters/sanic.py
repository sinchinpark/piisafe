"""
Sanic adapter for PII tokenization service.
"""
from sanic import Blueprint, Request, json
from sanic.exceptions import SanicException

from piisafe.adapters.base import BaseAdapter
from piisafe.exceptions import PIIError, PIITokenNotFoundError
from piisafe.models import PIIData, TokenResponse
from piisafe.service import PIITokenizationService


class PIISanicException(SanicException):
    """Custom Sanic exception for PII errors."""
    pass


class SanicAdapter(BaseAdapter):
    """Sanic adapter for PII tokenization service."""
    
    def __init__(self, service: PIITokenizationService, prefix: str = "/pii"):
        """
        Initialize the Sanic adapter.
        
        Args:
            service: The PIITokenizationService instance to use.
            prefix: URL prefix for all routes (default: "/pii").
        """
        super().__init__(service, prefix)
    
    def get_router(self) -> Blueprint:
        """Create and return a Sanic Blueprint with PII endpoints."""
        bp = Blueprint('pii', url_prefix=self.prefix)
        
        # Exception handler
        @bp.exception(PIIError)
        async def handle_pii_error(request: Request, exception: PIIError):
            return self._handle_exception(exception)
        
        # Endpoints
        @bp.post('/tokenize')
        async def tokenize_pii(request: Request):
            """Tokenize PII data."""
            try:
                data = request.json
                pii_data = PIIData(**data)
                token = await self.service.tokenize_pii(pii_data.data)
                response = TokenResponse(token=token)
                return json({"token": response.token}, status=201)
            except (TypeError, ValueError) as e:
                return json({"error": "VALIDATION_ERROR", "message": str(e)}, status=400)
        
        @bp.post('/retrieve')
        async def retrieve_pii(request: Request):
            """Retrieve PII data using a token from body or header."""
            data = request.json or {}
            token = data.get("token") or request.headers.get("X-PII-Token")
            if not token:
                raise PIITokenNotFoundError("Token required in body or X-PII-Token header")
            pii_data = await self.service.retrieve_pii(token)
            if pii_data is None:
                raise PIITokenNotFoundError("PII data not found for the provided token")
            response = json({"data": pii_data}, status=200)
            response.headers["Cache-Control"] = "no-store"
            return response
        
        @bp.put('/update/<token>')
        async def update_pii(request: Request, token: str):
            """Update PII data for an existing token."""
            try:
                data = request.json
                pii_data = PIIData(**data)
                success = await self.service.update_pii(token, pii_data.data)
                if not success:
                    raise PIITokenNotFoundError("PII data not found for the provided token")
                return json({"token": token}, status=200)
            except (TypeError, ValueError) as e:
                return json({"error": "VALIDATION_ERROR", "message": str(e)}, status=400)
        
        @bp.delete('/delete/<token>')
        async def delete_pii(request: Request, token: str):
            """Delete PII data for a token."""
            success = await self.service.delete_pii(token)
            if not success:
                raise PIITokenNotFoundError("PII data not found for the provided token")
            return json({}, status=204)
        
        return bp
    
    def _handle_exception(self, exc: PIIError):
        """Convert PIIError to Sanic JSON response."""
        return json(
            {"error": exc.code, "message": exc.message},
            status=exc.status_code
        )
