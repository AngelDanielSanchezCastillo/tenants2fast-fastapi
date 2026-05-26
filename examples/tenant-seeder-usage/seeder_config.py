"""
Example: Tenant Seeder Configuration

This example shows how to inspect the tenant seeder configuration
and integrate with the global seeder orchestrator.
"""

from tenant2fast_fastapi import get_seeder_config
from pgsqlasync2fast_fastapi import get_registered_seeders


def main():
    # Get this package's seeder configuration
    config = get_seeder_config()

    print("Tenant Seeder Configuration:")
    print(f"  Package name: {config.package_name}")
    print(f"  Connection: {config.connection_name}")
    print(f"  Manifest path: {config.manifest_path}")
    print(f"  Is tenant seeder: {config.is_tenant_seeder}")
    print(f"  Priority: {config.priority}")

    print("\n" + "=" * 50)
    print("All Registered Seeders:")
    print("=" * 50)

    seeders = get_registered_seeders()
    for seeder in seeders:
        tenant_marker = " [TENANT]" if seeder.is_tenant_seeder else ""
        print(f"  {seeder.package_name or seeder.connection_name}{tenant_marker}")
        print(f"    Connection: {seeder.connection_name}")
        print(f"    Priority: {seeder.priority}")
        print(f"    Is tenant seeder: {seeder.is_tenant_seeder}")
        print()


if __name__ == "__main__":
    main()