# Tenant Seeder Usage

The `tenants2fast-fastapi` package includes a tenant-aware seeder that seeds RBAC data (roles, categories, permissions) into each tenant's isolated database.

## Key Difference from Other Packages

Most packages seed their data into a **single database**. The tenant seeder seeds into **EACH tenant database** individually. This is the **tenant special case** in the seeder standard.

| Aspect | Regular Packages | tenants2fast-fastapi |
|--------|-----------------|---------------------|
| `is_tenant_seeder` | `False` | `True` |
| Seeding scope | Single database | Every tenant database |
| Primary function | `seed(profile)` | `seed(profile, tenant_id)` |
| Multi-tenant function | N/A | `seed_all_tenants(profile)` |

## How to Use

### Seeding a New Tenant

When you create a new tenant, call `seed()` to initialize its RBAC data:

```python
from tenant2fast_fastapi import seed, create_tenant_database

async def create_new_tenant(name: str, database_name: str):
    # 1. Create the tenant (tenant record + database)
    tenant = await create_tenant(name, database_name)
    
    # 2. Create tenant database and schema
    await create_tenant_database(tenant.id)
    await initialize_tenant_schema(tenant.id)
    
    # 3. Seed RBAC data for this tenant
    result = await seed("dev", tenant_id=tenant.id)
    
    print(f"Seeded {result['rows_seeded']} rows in {result['tables_seeded']} tables")
    return result
```

### Re-Seeding All Tenants

To re-seed all existing tenants (e.g., after updating seed data):

```python
from tenant2fast_fastapi import seed_all_tenants

async def reseed_all_tenants():
    summary = await seed_all_tenants("prod")
    
    print(f"Total tenants: {summary['total_tenants']}")
    print(f"Succeeded: {summary['succeeded']}")
    print(f"Failed: {summary['failed']}")
    
    for result in summary["results"]:
        status = "✅" if result["status"] == "succeeded" else "❌"
        print(f"  {status} Tenant {result['tenant_id']}: {result['status']}")
```

### Legacy Compatibility

The original `seed_tenant_rbac(tenant_id)` function is still available:

```python
from tenant2fast_fastapi import seed_tenant_rbac

# Legacy usage (still works)
await seed_tenant_rbac(tenant_id=1)
```

## Seeder Configuration

```python
from tenant2fast_fastapi import get_seeder_config

config = get_seeder_config()
print(f"Package: {config.package_name}")
print(f"Is tenant seeder: {config.is_tenant_seeder}")
print(f"Priority: {config.priority}")
```

Output:
```
Package: tenants2fast-fastapi
Is tenant seeder: True
Priority: 70
```

## Seed Data Structure

The seeder uses the standard multi-package format:

```
src/tenant2fast_fastapi/seeders/
├── manifest.json          # Table definitions and load order
├── dev/
│   ├── roles.json        # 3 roles (Owner, Admin, Member)
│   ├── categories.json   # 2 categories (System, Users)
│   └── permissions.json  # 6 permissions with FK to categories
└── prod/
    ├── roles.json        # 2 roles (Owner, Admin)
    ├── categories.json   # 2 categories (System, Users)
    └── permissions.json  # 5 permissions (reduced for prod)
```

### Dev Profile Data

**roles.json:**
- Owner (id=1): Full control
- Admin (id=2): Administrative access
- Member (id=3): Standard access

**categories.json:**
- System (id=1): view_tenant_info, edit_tenant_info
- Users (id=2): list_users, add_users, remove_users, manage_roles

**permissions.json:**
- Permissions link to categories via `category_id` FK

### Prod Profile Data

Production has fewer roles (Owner, Admin only) and fewer permissions for security.

## Integration with Seeder Orchestrator

The tenant seeder registers with the global seeder orchestrator from `pgsqlasync2fast-fastapi`:

```python
from pgsqlasync2fast_fastapi import get_registered_seeders

seeders = get_registered_seeders()
tenant_seeders = [s for s in seeders if s.is_tenant_seeder]

for seeder in tenant_seeders:
    print(f"Tenant seeder: {seeder.package_name}")
```

**Note:** Tenant seeders are NOT executed by `seed_all()` from the orchestrator. They must be called directly via `seed()` or `seed_all_tenants()` because the orchestrator doesn't iterate tenant databases.