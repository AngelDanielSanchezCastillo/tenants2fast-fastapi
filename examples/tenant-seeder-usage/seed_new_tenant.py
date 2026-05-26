"""
Example: Seeding a New Tenant

This example demonstrates how to seed RBAC data when creating a new tenant.
"""

import asyncio
from tenant2fast_fastapi import (
    seed,
    create_tenant_database,
    initialize_tenant_schema,
)


async def main():
    tenant_id = 1

    # Step 1: Create tenant database and schema
    # (In real code, tenant would already exist in auth DB)
    await create_tenant_database(tenant_id)
    await initialize_tenant_schema(tenant_id)

    # Step 2: Seed RBAC data for this tenant
    result = await seed("dev", tenant_id=tenant_id)

    print(f"Seeded tenant {tenant_id}:")
    print(f"  Tables: {result['tables_seeded']}")
    print(f"  Rows: {result['rows_seeded']}")
    print(f"  Errors: {result['errors']}")

    return result


if __name__ == "__main__":
    asyncio.run(main())