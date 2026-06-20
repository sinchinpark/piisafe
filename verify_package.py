#!/usr/bin/env python3
"""
Quick verification script to ensure the package is properly structured.
"""
import sys
from pathlib import Path


def verify_package():
    """Verify package structure and imports."""
    package_root = Path(__file__).parent
    errors = []

    # Check required files exist
    required_files = [
        "pyproject.toml",
        "README.md",
        "piisafe/__init__.py",
        "piisafe/protocols.py",
        "piisafe/exceptions.py",
        "piisafe/service.py",
        "piisafe/models.py",
        "piisafe/backends/__init__.py",
        "piisafe/backends/inmemory.py",
        "tests/conftest.py",
        "tests/test_service.py",
        "tests/test_models.py",
        "tests/test_backends.py",
    ]

    for file_path in required_files:
        full_path = package_root / file_path
        if not full_path.exists():
            errors.append(f"Missing file: {file_path}")

    # Try importing the package
    try:
        sys.path.insert(0, str(package_root))
        from piisafe import (
            PIITokenizationService,
            PIIStorageBackend,
            PIIData,
            TokenResponse,
            PIIError,
            PIITokenNotFoundError,
            PIITokenInvalidError,
            PIIEncryptionError,
            PIIDecryptionError,
            PIIKeyError,
            InMemoryBackend,
        )
        print("✓ All core imports successful")
    except ImportError as e:
        errors.append(f"Core import error: {e}")

    # Report results
    if errors:
        print("\n❌ Verification failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✅ Package structure verified successfully!")
        print("\nPublic API:")
        print("  - PIITokenizationService")
        print("  - PIIStorageBackend (Protocol)")
        print("  - InMemoryBackend")
        print("  - PIIData (dataclass)")
        print("  - TokenResponse (dataclass)")
        print("  - PIIError (+ 5 subclasses)")
        return True


if __name__ == "__main__":
    success = verify_package()
    sys.exit(0 if success else 1)
