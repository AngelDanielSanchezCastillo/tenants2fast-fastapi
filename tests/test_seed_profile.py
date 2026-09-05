"""
test_seed_profile.py — TDD tests for profile parameterization (R3) and
create_tenant error surfacing (R3 H2).

Tests:
- seed_tenant_rbac with profile=None uses settings.seed_profile
- seed_tenant_rbac with explicit profile uses that value
- create_tenant with seed errors raises HTTPException(500)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Test: seed_tenant_rbac defaults to settings.seed_profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_tenant_rbac_defaults_to_settings_profile():
    """seed_tenant_rbac(tenant_id) must use settings.seed_profile as default."""
    from tenant2fast_fastapi.services.tenant_rbac_seeder import seed_tenant_rbac

    mock_result = {"tenant_id": 1, "tables_seeded": 3, "rows_seeded": 10, "errors": []}

    with patch(
        "tenant2fast_fastapi.services.tenant_rbac_seeder.seed",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_seed, patch(
        "tenant2fast_fastapi.services.tenant_rbac_seeder.settings",
    ) as mock_settings:
        mock_settings.seed_profile = "prod"

        result = await seed_tenant_rbac(1)

        mock_seed.assert_called_once_with("prod", 1)
        assert result == mock_result


# ---------------------------------------------------------------------------
# Test: seed_tenant_rbac with explicit profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_tenant_rbac_explicit_profile():
    """seed_tenant_rbac(tenant_id, 'dev') must use 'dev', ignoring settings."""
    from tenant2fast_fastapi.services.tenant_rbac_seeder import seed_tenant_rbac

    mock_result = {"tenant_id": 1, "tables_seeded": 3, "rows_seeded": 10, "errors": []}

    with patch(
        "tenant2fast_fastapi.services.tenant_rbac_seeder.seed",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_seed, patch(
        "tenant2fast_fastapi.services.tenant_rbac_seeder.settings",
    ) as mock_settings:
        mock_settings.seed_profile = "prod"  # settings says prod

        await seed_tenant_rbac(1, "dev")

        # Must use "dev" (explicit), NOT "prod" (settings)
        mock_seed.assert_called_once_with("dev", 1)


# ---------------------------------------------------------------------------
# Test: create_tenant surfaces seed errors as HTTPException 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_surfaces_seed_errors():
    """create_tenant must raise HTTPException(500) when seed returns errors."""
    from tenant2fast_fastapi.services.tenant_service import create_tenant
    from tenant2fast_fastapi.schemas.tenant_schema import TenantCreate

    seed_error_result = {
        "tenant_id": 99,
        "tables_seeded": 0,
        "rows_seeded": 0,
        "errors": ["Seeding failed: connection refused"],
    }

    mock_tenant = MagicMock()
    mock_tenant.id = 99
    mock_tenant.name = "Test"
    mock_tenant.slug = "test"
    mock_tenant.database_name = "tenant_test"
    mock_tenant.is_active = True
    mock_tenant.contact_email = "test@test.com"
    mock_tenant.max_users = 5
    mock_tenant.created_at.isoformat.return_value = "2026-01-01T00:00:00"
    mock_tenant.updated_at.isoformat.return_value = "2026-01-01T00:00:00"

    mock_session = AsyncMock()
    # exec is async → result is a coroutine returning a mock; one_or_none is async
    mock_exec_result = MagicMock()
    mock_exec_result.one_or_none.return_value = None  # slug unique (sync method)
    mock_session.exec = AsyncMock(return_value=mock_exec_result)
    mock_session.refresh = AsyncMock(side_effect=lambda t: None)
    mock_session.add = MagicMock()  # sync method
    mock_session.commit = AsyncMock()
    # AsyncSession supports async-with via __aenter__/__aexit__
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # get_session is `async def` → an AsyncMock returning the session works
    mock_manager = MagicMock()
    mock_manager.get_session = AsyncMock(return_value=mock_session)

    tenant_data = TenantCreate(
        name="Test",
        slug="test",
        contact_email="test@test.com",
        max_users=5,
    )

    with (
        patch(
            "tenant2fast_fastapi.services.tenant_service.get_manager",
            return_value=mock_manager,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.create_tenant_database",
            new_callable=AsyncMock,
            return_value="tenant_test",
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.initialize_tenant_schema",
            new_callable=AsyncMock,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.seed_tenant_rbac",
            new_callable=AsyncMock,
            return_value=seed_error_result,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.cache_tenant_data",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_tenant(tenant_data, profile="prod")

        assert exc_info.value.status_code == 500
        assert "seeding errors" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test: create_tenant success path unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_success_path():
    """create_tenant with no seed errors must succeed normally."""
    from tenant2fast_fastapi.services.tenant_service import create_tenant
    from tenant2fast_fastapi.schemas.tenant_schema import TenantCreate

    seed_ok_result = {
        "tenant_id": 99,
        "tables_seeded": 3,
        "rows_seeded": 10,
        "errors": [],
    }

    mock_tenant = MagicMock()
    mock_tenant.id = 99
    mock_tenant.name = "Test"
    mock_tenant.slug = "test"
    mock_tenant.database_name = "tenant_test"
    mock_tenant.is_active = True
    mock_tenant.contact_email = "test@test.com"
    mock_tenant.max_users = 5
    mock_tenant.created_at.isoformat.return_value = "2026-01-01T00:00:00"
    mock_tenant.updated_at.isoformat.return_value = "2026-01-01T00:00:00"

    mock_session = AsyncMock()
    mock_exec_result = MagicMock()
    mock_exec_result.one_or_none.return_value = None  # slug unique (sync method)
    mock_session.exec = AsyncMock(return_value=mock_exec_result)
    # refresh assigns the tenant id (id 99)
    def _refresh(instance):
        instance.id = 99
    mock_session.refresh = AsyncMock(side_effect=_refresh)
    mock_session.add = MagicMock()  # sync method
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_manager = MagicMock()
    mock_manager.get_session = AsyncMock(return_value=mock_session)

    tenant_data = TenantCreate(
        name="Test",
        slug="test",
        contact_email="test@test.com",
        max_users=5,
    )

    with (
        patch(
            "tenant2fast_fastapi.services.tenant_service.get_manager",
            return_value=mock_manager,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.create_tenant_database",
            new_callable=AsyncMock,
            return_value="tenant_test",
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.initialize_tenant_schema",
            new_callable=AsyncMock,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.seed_tenant_rbac",
            new_callable=AsyncMock,
            return_value=seed_ok_result,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.cache_tenant_data",
            new_callable=AsyncMock,
        ),
    ):
        result = await create_tenant(tenant_data, profile="dev")

        assert result.id == 99


# ---------------------------------------------------------------------------
# Test: create_tenant forwards profile to seed_tenant_rbac
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_forwards_profile():
    """create_tenant(data, profile='prod') must forward profile to seed_tenant_rbac."""
    from tenant2fast_fastapi.services.tenant_service import create_tenant
    from tenant2fast_fastapi.schemas.tenant_schema import TenantCreate

    seed_ok_result = {
        "tenant_id": 99,
        "tables_seeded": 3,
        "rows_seeded": 10,
        "errors": [],
    }

    mock_tenant = MagicMock()
    mock_tenant.id = 99
    mock_tenant.name = "Test"
    mock_tenant.slug = "test"
    mock_tenant.database_name = "tenant_test"
    mock_tenant.is_active = True
    mock_tenant.contact_email = "test@test.com"
    mock_tenant.max_users = 5
    mock_tenant.created_at.isoformat.return_value = "2026-01-01T00:00:00"
    mock_tenant.updated_at.isoformat.return_value = "2026-01-01T00:00:00"

    mock_session = AsyncMock()
    mock_exec_result = MagicMock()
    mock_exec_result.one_or_none.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_exec_result)
    def _refresh(instance):
        instance.id = 99
    mock_session.refresh = AsyncMock(side_effect=_refresh)
    mock_session.add = MagicMock()  # sync method
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_manager = MagicMock()
    mock_manager.get_session = AsyncMock(return_value=mock_session)

    tenant_data = TenantCreate(
        name="Test",
        slug="test",
        contact_email="test@test.com",
        max_users=5,
    )

    with (
        patch(
            "tenant2fast_fastapi.services.tenant_service.get_manager",
            return_value=mock_manager,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.create_tenant_database",
            new_callable=AsyncMock,
            return_value="tenant_test",
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.initialize_tenant_schema",
            new_callable=AsyncMock,
        ),
        patch(
            "tenant2fast_fastapi.services.tenant_service.seed_tenant_rbac",
            new_callable=AsyncMock,
            return_value=seed_ok_result,
        ) as mock_seed,
        patch(
            "tenant2fast_fastapi.services.tenant_service.cache_tenant_data",
            new_callable=AsyncMock,
        ),
    ):
        await create_tenant(tenant_data, profile="prod")

        mock_seed.assert_called_once_with(99, "prod")
