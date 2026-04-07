# tenants2fast-fastapi

🏢 **Multi-tenancy management for FastAPI** — tenant isolation, JWT-aware middleware, and permission-gated endpoints, all wired up in minutes.

Part of the **\*2fast-fastapi** ecosystem: [oauth2fast-fastapi](https://github.com/AngelDanielSanchezCastillo/oauth2fast-fastapi) → [permissions2fast-fastapi](https://github.com/AngelDanielSanchezCastillo/permissions2fast-fastapi) → **tenants2fast-fastapi**.

---

## Features

- 🔐 **JWT-aware `TenantMiddleware`** — extracts user from Bearer token and sets tenant context automatically on every request
- 🏗️ **Isolated tenant databases** — each tenant gets its own PostgreSQL database, created and initialized at runtime
- 🗂️ **`Tenant` and `UserTenant` SQLModel models** — ready-to-use ORM models with audit timestamps
- ⚡ **Redis caching** — tenant data and user permissions are cached via `permissions2fast-fastapi`
- 🔒 **`require_permission` dependency** — guard any route with a single line using the RBAC system from `permissions2fast-fastapi`

---

## Installation

```bash
pip install tenants2fast-fastapi
```

Or with `uv`:

```bash
uv add tenants2fast-fastapi
```

---

## Quick Start

```python
from fastapi import Depends, FastAPI
from tenant2fast_fastapi import (
    TenantMiddleware,
    get_current_tenant,
    get_current_user,
    require_permission,
)

app = FastAPI()

# 1. Register the middleware
app.add_middleware(TenantMiddleware)

# 2. Use dependencies in your endpoints
@app.get("/me/tenant")
async def my_tenant(tenant=Depends(get_current_tenant)):
    return {"name": tenant.name, "slug": tenant.slug}

@app.get("/reports", dependencies=[Depends(require_permission("/reports", "GET"))])
async def reports(user=Depends(get_current_user)):
    return {"user": user.email}
```

See [`examples/basic_usage.py`](examples/basic_usage.py) for a more complete example.

---

## Configuration

All settings use the `TENANT_` prefix and can be provided via environment variables or a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `TENANT_DB_PREFIX` | `tenant_` | Prefix for per-tenant database names |
| `TENANT_SUPERUSER_DB__HOSTNAME` | `localhost` | PG host for superuser operations |
| `TENANT_SUPERUSER_DB__PORT` | `5432` | PG port |
| `TENANT_SUPERUSER_DB__USERNAME` | `postgres` | PG superuser username |
| `TENANT_SUPERUSER_DB__PASSWORD` | `postgres` | PG superuser password |
| `TENANT_SUPERUSER_DB__NAME` | `postgres` | Default DB for superuser connection |
| `TENANT_MAX_TENANT_CONNECTIONS` | `5` | Connection pool size per tenant |

In addition, all variables required by `oauth2fast-fastapi` (JWT, DB connections, mail) and `permissions2fast-fastapi` (Redis) must be set — see their respective READMEs.

---

## Public API

```python
from tenant2fast_fastapi import (
    Tenant,                   # SQLModel ORM model (table: tenants)
    UserTenant,               # Many-to-many User ↔ Tenant (table: user_tenants)
    TenantMiddleware,         # Starlette BaseHTTPMiddleware
    get_current_tenant,       # FastAPI dependency → Tenant
    get_current_user,         # FastAPI dependency → User (from oauth2fast-fastapi)
    require_permission,       # Dependency factory → checks RBAC + cache
    create_tenant_database,   # async — creates a PG database for a tenant
    get_tenant_engine,        # returns (cached) AsyncEngine for a tenant DB
    initialize_tenant_schema, # async — runs SQLModel.metadata.create_all on tenant DB
)
```

---

## Development

```bash
# Clone and install in editable mode with dev + test dependencies
git clone https://github.com/AngelDanielSanchezCastillo/tenants2fast-fastapi
cd tenants2fast-fastapi
uv sync --group dev --group test

# Copy .env and adjust to your local setup
cp .env .env.local   # or just edit .env directly

# Run tests (requires PostgreSQL + Redis)
uv run pytest tests/ -v

# Build distribution
uv build
```

---

## Related Packages

| Package | PyPI | Purpose |
|---|---|---|
| `log2fast-fastapi` | [![PyPI](https://img.shields.io/pypi/v/log2fast-fastapi)](https://pypi.org/project/log2fast-fastapi/) | Structured logging |
| `pgsqlasync2fast-fastapi` | [![PyPI](https://img.shields.io/pypi/v/pgsqlasync2fast-fastapi)](https://pypi.org/project/pgsqlasync2fast-fastapi/) | Async PostgreSQL connection manager |
| `mailing2fast-fastapi` | [![PyPI](https://img.shields.io/pypi/v/mailing2fast-fastapi)](https://pypi.org/project/mailing2fast-fastapi/) | SMTP email sender |
| `oauth2fast-fastapi` | [![PyPI](https://img.shields.io/pypi/v/oauth2fast-fastapi)](https://pypi.org/project/oauth2fast-fastapi/) | JWT Auth + User management |
| `permissions2fast-fastapi` | [![PyPI](https://img.shields.io/pypi/v/permissions2fast-fastapi)](https://pypi.org/project/permissions2fast-fastapi/) | RBAC + Redis permission cache |

---

## License

MIT © [Angel Daniel Sanchez Castillo](https://github.com/AngelDanielSanchezCastillo)
