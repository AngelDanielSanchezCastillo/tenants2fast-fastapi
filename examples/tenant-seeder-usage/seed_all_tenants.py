"""
Example: Re-Seeding All Tenants

This example demonstrates how to re-seed RBAC data for all existing tenants.
Useful when:
- Updating seed data and need to propagate to all tenants
- Recovery from corrupted seed data
- Initial deployment across multiple tenants
"""

import asyncio
from tenant2fast_fastapi import seed_all_tenants


async def main():
    # Re-seed all tenants with production profile
    summary = await seed_all_tenants("prod")

    print(f"Seed All Tenants Summary:")
    print(f"  Profile: {summary['profile']}")
    print(f"  Total tenants: {summary['total_tenants']}")
    print(f"  Succeeded: {summary['succeeded']}")
    print(f"  Failed: {summary['failed']}")

    print("\nDetailed Results:")
    for result in summary["results"]:
        status = "✅" if result["status"] == "succeeded" else "❌"
        tenant_id = result["tenant_id"]

        if result["status"] == "succeeded":
            print(f"  {status} Tenant {tenant_id}: {result['rows_seeded']} rows seeded")
        else:
            error = result.get("error") or result.get("errors", ["Unknown"])[0]
            print(f"  {status} Tenant {tenant_id}: {error}")

    return summary


if __name__ == "__main__":
    asyncio.run(main())