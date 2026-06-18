"""
Flask adapter for PII tokenization service.
"""
import asyncio
from functools import wraps
from typing import Callable, Dict, Tuple

from flask import Blueprint, jsonify, request

from python_pii.adapters.base import BaseAdapter
from python_pii.exceptions import PIIError, PIITokenNotFoundError
from python_pii.models import PIIData, TokenResponse
from python_pii.service import PIITokenizationService


def async_route(f: Callable) -> Callable:
    """Decorator to run async functions in Flask routes."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


class FlaskAdapter(BaseAdapter):
    """Flask adapter for PII tokenization service."""
    
    def __init__(self, service: PIITokenizationService, prefix: str = "/pii"):
        """
        Initialize the Flask adapter.
        
        Args:
            service: The PIITokenizationService instance to use.
            prefix: URL prefix for all routes (default: "/pii").
        """
        super().__init__(service, prefix)
        self.blueprint = None
    
    def get_router(self) -> Blueprint:
        """Create and return a Flask Blueprint with PII endpoints."""
        bp = Blueprint('pii', __name__, url_prefix=self.prefix)
        
        # Error handler
        @bp.errorhandler(PIIError)
        def handle_pii_error(error: PIIError):
            return self._handle_exception(error)
        
        # Endpoints
        @bp.route('/tokenize', methods=['POST'])
        @async_route
        async def tokenize_pii():
            """Tokenize PII data."""
            try:
                data = request.get_json()
                pii_data = PIIData(**data)
                token = await self.service.tokenize_pii(pii_data.data)
                response = TokenResponse(token=token)
                return jsonify({"token": response.token}), 201
            except (TypeError, ValueError) as e:
                return jsonify({"error": "VALIDATION_ERROR", "message": str(e)}), 400
        
        @bp.route('/retrieve/<token>', methods=['GET'])
        @async_route
        async def retrieve_pii(token: str):
            """Retrieve PII data using a token."""
            pii_data = await self.service.retrieve_pii(token)
            if pii_data is None:
                raise PIITokenNotFoundError(f"PII data not found for token: {token}")
            return jsonify({"data": pii_data}), 200
        
        @bp.route('/update/<token>', methods=['PUT'])
        @async_route
        async def update_pii(token: str):
            """Update PII data for an existing token."""
            try:
                data = request.get_json()
                pii_data = PIIData(**data)
                success = await self.service.update_pii(token, pii_data.data)
                if not success:
                    raise PIITokenNotFoundError(f"PII data not found for token: {token}")
                return jsonify({"token": token}), 200
            except (TypeError, ValueError) as e:
                return jsonify({"error": "VALIDATION_ERROR", "message": str(e)}), 400
        
        @bp.route('/delete/<token>', methods=['DELETE'])
        @async_route
        async def delete_pii(token: str):
            """Delete PII data for a token."""
            success = await self.service.delete_pii(token)
            if not success:
                raise PIITokenNotFoundError(f"PII data not found for token: {token}")
            return '', 204
        
        self.blueprint = bp
        return bp
    
    def _handle_exception(self, exc: PIIError) -> Tuple[Dict, int]:
        """Convert PIIError to Flask JSON response tuple."""
        return jsonify({"error": exc.code, "message": exc.message}), exc.status_code
