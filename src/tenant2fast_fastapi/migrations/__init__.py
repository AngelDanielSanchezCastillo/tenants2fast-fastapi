"""
tenant2fast_fastapi.migrations - package-owned Alembic chains (alembic-2fast).

The ``auth`` lane ends with the ``tenant2fast-auth`` chain: after oauth and
permissions-global have run, the auth database can receive ``tenants`` and the
``tenant_users`` mapping (FK-proven order, design D6 of the Metal ERP change
``alembic-2fast``). The ``tenant`` lane carries ``tenant2fast-rbac``, which
owns the complete exclusive ``tenant_metadata`` partition (design D9): the
per-tenant RBAC tables, upgraded per tenant database by the app's bootstrap.

Both chains' models inherit ``oauth2fast_fastapi.models.AuthModel``
(``tenants``, ``tenant_users``) or ``TenantBaseModel`` (the nine
``tenant_metadata`` tables), so the ``tenant2fast-auth`` ChainSpec passes the
shared oauth2fast ``MetaData`` with an ownership filter (design D9); the
``tenant2fast-rbac`` ChainSpec passes the exclusive ``tenant_metadata``.

Registration mirrors the ``register_seeder`` idiom: importing this module
(which the top-level ``tenant2fast_fastapi/__init__.py`` does) registers both
chain specs at import time. The chain directories
``migrations/tenant2fast-auth/`` and ``migrations/tenant2fast-rbac/`` ship
inside the wheel via ``[tool.setuptools.package-data] migrations/**/*.py``
and are resolved from the INSTALLED release via alembic-native ``pkg:path``
resource strings.
"""

from oauth2fast_fastapi.models.bases import metadata
from pgsqlasync2fast_fastapi import ChainSpec, register_chain

from tenant2fast_fastapi.models import (  # noqa: F401  (registration side effect)
    Category,
    Permission,
    PermissionRole,
    PermissionRoute,
    PermissionUser,
    Role,
    RoleUser,
    Route,
    Tenant,
    TenantUser,
    User,
)
from tenant2fast_fastapi.models.bases import tenant_metadata

#: Tables the tenant2fast-auth chain owns (design D9 ownership filter):
#: exactly the auth-lane tables of this package.
TENANT2FAST_AUTH_OWNED_TABLES = frozenset({"tenants", "tenant_users"})

tenant_auth_chain = ChainSpec(
    package="tenant2fast_fastapi",
    script_path="migrations/tenant2fast-auth",
    version_table="alembic_version_tenant_auth",
    target_metadata=metadata,
    owned_tables=TENANT2FAST_AUTH_OWNED_TABLES,
)

# Last in the auth lane (FK-proven order, design D6): the oauth and
# permissions2fast chains register before this module is imported, so this
# chain appends after them.
register_chain("auth", tenant_auth_chain)

#: Tables the tenant2fast-rbac chain owns: the complete exclusive
#: ``tenant_metadata`` partition (design D9).
TENANT2FAST_RBAC_OWNED_TABLES = frozenset(tenant_metadata.tables.keys())

tenant_rbac_chain = ChainSpec(
    package="tenant2fast_fastapi",
    script_path="migrations/tenant2fast-rbac",
    version_table="alembic_version_tenant_rbac",
    target_metadata=tenant_metadata,
    owned_tables=TENANT2FAST_RBAC_OWNED_TABLES,
)

register_chain("tenant", tenant_rbac_chain)

__all__ = [
    "TENANT2FAST_AUTH_OWNED_TABLES",
    "TENANT2FAST_RBAC_OWNED_TABLES",
    "tenant_auth_chain",
    "tenant_rbac_chain",
]