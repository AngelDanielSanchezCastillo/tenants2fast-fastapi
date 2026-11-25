"""CI gate: tenants2fast seeders must be valid and use explicit uuid7 literals."""

from __future__ import annotations

import json
import os
from uuid import UUID

import pytest

from tenant2fast_fastapi.seeders import (
    TENANT_RBAC_MANIFEST_PATH,
    TENANT_RBAC_MODEL_REGISTRY,
    get_seeder_config,
)


@pytest.mark.parametrize("profile", ["dev", "prod"])
def test_package_seeders_are_valid(profile: str) -> None:
    from pgsqlasync2fast_fastapi import validate_seeders_report

    config = get_seeder_config()
    report = validate_seeders_report(
        config.manifest_path,
        config.model_registry,
        profile=profile,
    )
    assert report.errors == [], f"Invalid seeders for '{profile}': {report.errors}"
    assert report.warnings == [], (
        f"2fast packages must use explicit UUID ids; warnings for '{profile}': "
        f"{report.warnings}"
    )


@pytest.mark.parametrize("table", ["categories", "roles", "permissions"])
def test_seed_literals_are_uuid7(table: str) -> None:
    seed_dir = os.path.join(os.path.dirname(TENANT_RBAC_MANIFEST_PATH), "boot")
    rows = json.load(open(os.path.join(seed_dir, f"{table}.json")))
    for row in rows:
        assert UUID(row["id"]).version == 7, f"{table}: {row['id']} is not uuid7"


def test_orchestrator_and_filter_exports() -> None:
    from tenant2fast_fastapi import (
        TenantFilter,
        TenantSeederOrchestrator,
        adopt_explicit_seed_ids,
    )

    assert TenantFilter is not None
    assert TenantSeederOrchestrator is not None
    assert adopt_explicit_seed_ids is not None
    assert set(TENANT_RBAC_MODEL_REGISTRY) == {"categories", "roles", "permissions"}
