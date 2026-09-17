"""
test_initialize_tenant_schema.py – TENANT-lane upgrade contract (work unit
1.6, alembic-2fast change).

Pure unit tests (no PostgreSQL): the public signature is unchanged and the
internals now delegate to ``run_migrations`` over ``get_lane_chains("tenant")``
instead of emitting DDL from the metadata argument.

Run with: uv run --all-groups pytest tests/test_initialize_tenant_schema.py -v
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
# Mirror the .env contract for the settings import chain (see conftest).
os.environ.setdefault("DB_CONNECTIONS__AUTH__HOST", "localhost")
os.environ.setdefault("DB_CONNECTIONS__AUTH__USERNAME", "test")
os.environ.setdefault("DB_CONNECTIONS__AUTH__PASSWORD", "test")
os.environ.setdefault("DB_CONNECTIONS__AUTH__DATABASE", "test")

from pgsqlasync2fast_fastapi import get_lane_chains

from tenant2fast_fastapi.databases import tenant_db_factory
from tenant2fast_fastapi.databases.tenant_db_factory import initialize_tenant_schema
from tenant2fast_fastapi.models.bases import tenant_metadata


def test_initialize_tenant_schema_signature_kept():
    """The public signature (tenant_id, metadata) is unchanged."""
    sig = inspect.signature(initialize_tenant_schema)
    assert list(sig.parameters) == ["tenant_id", "metadata"]
    assert sig.parameters["metadata"].default is tenant_metadata


@pytest.mark.asyncio
async def test_initialize_tenant_schema_delegates_to_tenant_lane_runner(
    monkeypatch,
):
    """Upgrade-to-head of the TENANT lane, not create_all (schema-bootstrap
    spec scenario: create_tenant via upgrade-to-head)."""
    fake_runner = AsyncMock()
    monkeypatch.setattr(tenant_db_factory, "run_migrations", fake_runner)
    monkeypatch.setattr(
        tenant_db_factory, "get_tenant_engine", lambda tenant_id: object()
    )

    await initialize_tenant_schema(42)

    fake_runner.assert_awaited_once_with("tenant_42", get_lane_chains("tenant"))


@pytest.mark.asyncio
async def test_initialize_tenant_schema_still_requires_registered_engine(
    monkeypatch,
):
    """The pre-change contract (ValueError for an unregistered tenant) holds."""
    fake_runner = AsyncMock()
    monkeypatch.setattr(tenant_db_factory, "run_migrations", fake_runner)

    def _missing(tenant_id):
        raise ValueError(
            f"Engine for tenant {tenant_id} not initialized. "
            "Use register_tenant_engine first."
        )

    monkeypatch.setattr(tenant_db_factory, "get_tenant_engine", _missing)

    with pytest.raises(ValueError, match="not initialized"):
        await initialize_tenant_schema(7)
    fake_runner.assert_not_awaited()


def test_initialize_tenant_schema_no_ddl_from_metadata():
    """The module must no longer emit DDL directly (no create_all anywhere)."""
    source = Path(tenant_db_factory.__file__).read_text()
    assert "create_all" not in source