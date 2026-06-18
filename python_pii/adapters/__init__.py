"""
Framework adapters for python-pii.

Lazy imports to avoid requiring all frameworks.
"""


def get_fastapi_adapter():
    """Get FastAPI adapter (requires fastapi extra)."""
    try:
        from python_pii.adapters.fastapi import FastAPIAdapter
        return FastAPIAdapter
    except ImportError as e:
        raise ImportError(
            "FastAPI adapter requires the 'fastapi' extra. "
            "Install with: pip install python-pii[fastapi]"
        ) from e


def get_flask_adapter():
    """Get Flask adapter (requires flask extra)."""
    try:
        from python_pii.adapters.flask import FlaskAdapter
        return FlaskAdapter
    except ImportError as e:
        raise ImportError(
            "Flask adapter requires the 'flask' extra. "
            "Install with: pip install python-pii[flask]"
        ) from e


def get_sanic_adapter():
    """Get Sanic adapter (requires sanic extra)."""
    try:
        from python_pii.adapters.sanic import SanicAdapter
        return SanicAdapter
    except ImportError as e:
        raise ImportError(
            "Sanic adapter requires the 'sanic' extra. "
            "Install with: pip install python-pii[sanic]"
        ) from e


__all__ = [
    "get_fastapi_adapter",
    "get_flask_adapter",
    "get_sanic_adapter",
]
