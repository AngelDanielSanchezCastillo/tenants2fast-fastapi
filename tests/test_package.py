"""
test_package.py – smoke tests for tenants2fast-fastapi.

Verifies that the package's public API can be imported and the
version string is set correctly.
"""

import importlib

import pytest


def test_package_version():
    """The package must expose a non-empty __version__ string."""
    import tenant2fast_fastapi as pkg

    assert hasattr(pkg, "__version__")
    assert isinstance(pkg.__version__, str)
    assert len(pkg.__version__) > 0


def test_public_symbols_importable():
    """All symbols declared in __all__ must be importable."""
    import tenant2fast_fastapi as pkg

    expected = [
        "__version__",
        "Tenant2",
        "Tenant2Read",
        "UserTenant2",
        "TenantMiddleware",
        "get_current_tenant",
        "get_current_user",
        "require_permission",
        "create_tenant_database",
        "get_tenant_engine",
        "initialize_tenant_schema",
    ]

    for name in expected:
        assert hasattr(pkg, name), f"Missing public symbol: {name}"


def test_tenant_model_table_name():
    """Tenant2 model must be bound to the 'tenants2' table."""
    from tenant2fast_fastapi.models.tenant_model import Tenant2

    assert Tenant2.__tablename__ == "tenants2"


def test_user_tenant_model_table_name():
    """UserTenant2 model must be bound to the 'user_tenants2' table."""
    from tenant2fast_fastapi.models.user_tenant_model import UserTenant2

    assert UserTenant2.__tablename__ == "user_tenants2"


def test_settings_loads():
    """TenantSettings must load without errors (reads .env)."""
    from tenant2fast_fastapi.settings import settings

    assert settings.db_prefix is not None
    assert isinstance(settings.max_tenant_connections, int)
