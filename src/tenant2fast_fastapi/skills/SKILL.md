---
name: tenants2fast-fastapi
description: >
  Package-specific skill for tenants2fast-fastapi (multi-tenancy for FastAPI:
  per-tenant isolated databases, JWT tenant resolution, tenant-scoped RBAC).
  Prevails over the 2fast-handbook base skill for anything specific to this
  package. Trigger: working on or with tenants2fast-fastapi.
metadata:
  author: AngelDanielSanchezCastillo
  version: "2.0"
  allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Task
---

## Purpose

Multi-tenancy layer: each tenant gets an **isolated PostgreSQL database**;
JWT-aware middleware resolves the tenant; tenant-scoped RBAC gates routers.
Bases on `pgsqlasync2fast-fastapi` (connections) and `rbac2fast_core`
(service protocols).

## Import name (quirk)

- Dist: `tenants2fast-fastapi`; import: **`tenant2fast_fastapi`** (SINGULAR).
- Never write `tenants2fast_fastapi` in imports.

## Public API (core)

- Routers: `get_tenant_routers()` — combined tenants/users/roles/permissions.
- Deps: `get_current_tenant`, `get_current_user`, `get_current_tenant_user`,
  `get_tenant_db_session` (AsyncSession for the tenant engine),
  `has_tenant_permission(route, method)`, `has_tenant_role(name)`.
- DB: `create_tenant_database`, `get_tenant_engine`, `initialize_tenant_schema`,
  `load_tenant_by_id`.
- Seeders: `get_seeder_config`, `seed(profile, tenant_id)`, `seed_all_tenants(profile)`.

## Architecture

- **Two registries**: auth-DB models (`Tenant`, `TenantUser`) extend `AuthModel`
  (from `oauth2fast_fastapi.models.bases`); tenant-DB models (`User`, `Role`,
  `Category`, `Permission`, `Route`, joins) extend `TenantBaseModel` and
  register on the exclusive **`tenant_metadata`** registry.
- **New app models MUST inherit `TenantBaseModel`** to be created per-tenant;
  auth models inherit `AuthModel`.
- Per-tenant engines register in the pgsqlasync2fast manager under
  `tenant_{tenant_id}`; services implement `rbac2fast_core` protocols as
  singletons (`tenant_access_service`, `tenant_role_service`,
  `tenant_permission_service`).

## Wiring

```python
app.add_middleware(TenantMiddleware)
app.include_router(get_tenant_routers())
```

Tenant resolution: reset contextvars → verify Bearer JWT (`sub` = email) →
load `AuthUser` from auth engine → resolve tenant via `TenantUser` mapping
(`X-Tenant-Id` header, else first link, else cache `user:{id}:tenant_id`) →
validate `is_active` → `set_tenant_context(tenant)` + register engine.

## RBAC

- `has_tenant_permission("/users", "POST")` factory; path omitted →
  auto-detect via `request.scope["route"].path`.
- **Deny by default**. Resolution: `PermissionUser` overrides first (deny wins)
  → role permissions → `evaluate_route_access` regex-matches `{param}`.
- Redis cache `tenant:{id}:user:{id}:permissions`, TTL 300.
- `has_tenant_role(name)` checks tenant-local role assignment.
- `require_tenant_owner()` factory resolves the tenant-local **OWNER** role via
  `tenant_role_service.list_user_roles` and returns the tenant `User`; raises
  403 when the caller lacks OWNER. The binary `is_admin` flag is **ignored**
  — it never bypasses the OWNER requirement. Use it in place of `has_tenant_role("OWNER")`
  when you need the owner identity back from the dependency.

## Migrations & seeders

- **No Alembic**: `run_tenant_migrations(tenant_id)` = `import_tenant_models()`
  then `tenant_metadata.create_all` on the tenant engine;
  `run_all_tenant_migrations()` iterates active tenants from the auth DB.
- Seeders: `SeederConfig(is_tenant_seeder=True, priority=70)`; manifest
  `load_order` categories → roles → permissions; idempotent by row `id`.
- `seed_tenant_rbac(tenant_id, profile=None)` is **profile-aware** — it forwards
  `profile or settings.seed_profile` to `seed(profile, tenant_id)` (no hardcoded
  "dev"). `create_tenant(tenant_data, profile=None)` has the same profile param
  and raises `HTTPException(500)` when seeding returns non-empty `errors`
  instead of silently succeeding.
- The orchestrator `seed_all()` does **not** run tenant seeders — run them
  explicitly.

## Settings

`TenantSettings`, prefix `TENANT_`, nested `__`: `URL_PREFIX` (default
"tenants"), `BASE_DB_CONNECTION` (default "tenant"), `MAX_TENANT_CONNECTIONS`
(5), `REDIS_URL`, `REDIS_TTL` (300), `SUPERUSER_DB__*`, `DB_PREFIX` (README).

## Conventions specific

- Router prefix from `TENANT_URL_PREFIX`; RBAC-gated with explicit pattern
  strings.
- Naming: singular PascalCase models, plural snake_case tables, alphabetical
  join names (`role_users`, `permission_roles`, ...).
- Response messages in **Spanish**.

## Stale docs to avoid

- `require_permission` → use `has_tenant_permission`.
- `Tenant2Read` → `TenantRead`.
- Seeder module is `services.tenant_rbac_seeder`, not `tenant2fast_fastapi.seeder`.

## Golden rule (inherited)

Follow the 2fast-handbook base skill for layout/versioning/naming/pyproject/
release conventions. MAY modify locally; NEVER publish/bump/release on your
own — prepare the exact command and hand it to the developer.