"""
test_package.py – smoke tests for tenant2fast-fastapi.

Verifies that the package's public API can be imported and the
version string is set correctly.
"""

import tenant2fast_fastapi as pkg
from tenant2fast_fastapi.models.tenant_model import Tenant
from tenant2fast_fastapi.models.user_tenant_model import UserTenant
from tenant2fast_fastapi.settings import settings


def test_package_version():
    """The package must expose a non-empty __version__ string."""
    assert hasattr(pkg, "__version__")
    assert isinstance(pkg.__version__, str)
    assert len(pkg.__version__) > 0


def test_public_symbols_importable():
    """All symbols declared in __all__ must be importable."""
    expected = [
        "__version__",
        "Tenant",
        "TenantRead",
        "TenantMiddleware",
        "get_current_tenant",
        "get_current_user",
        "has_tenant_permission",
        "has_tenant_role",
        "get_current_tenant_user",
        "load_tenant_by_id",
        "create_tenant_database",
        "get_tenant_engine",
        "initialize_tenant_schema",
    ]

    for name in expected:
        assert hasattr(pkg, name), f"Missing public symbol: {name}"


def test_tenant_model_table_name():
    """Tenant model must be bound to the 'tenants' table."""
    assert Tenant.__tablename__ == "tenants"


def test_user_tenant_model_table_name():
    """UserTenant model must be bound to the 'user_tenants' table."""
    assert UserTenant.__tablename__ == "user_tenants"


def test_settings_loads():
    """TenantSettings must load without errors (reads .env)."""
    assert settings.db_prefix is not None
    assert isinstance(settings.max_tenant_connections, int)
