"""
test_tenant_owner_dep.py — TDD tests for require_tenant_owner dependency (R5).

Monkeypatching tenant_role_service to verify:
- OWNER role → 200
- Non-OWNER role → 403
- is_admin=true but no OWNER → 403
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers — minimal stubs so tests don't need a real database
# ---------------------------------------------------------------------------

def _make_role(name: str) -> MagicMock:
    role = MagicMock()
    role.name = name
    return role


def _make_user(auth_user_id: int = 1) -> MagicMock:
    user = MagicMock()
    user.id = 42
    user.auth_user_id = auth_user_id
    return user


# ---------------------------------------------------------------------------
# Test: OWNER holder → 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_holder_allowed():
    """A user with the OWNER role must pass require_tenant_owner."""
    from tenant2fast_fastapi.dependencies.tenant_rbac import require_tenant_owner

    owner_dep = require_tenant_owner()

    mock_tenant_user = _make_user()
    mock_roles = [_make_role("Admin"), _make_role("OWNER")]

    with (
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_user_by_auth_id",
            new_callable=AsyncMock,
            return_value=mock_tenant_user,
        ),
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.tenant_role_service.list_user_roles",
            new_callable=AsyncMock,
            return_value=mock_roles,
        ),
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_session",
        ) as mock_session_ctx,
    ):
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        # Build a fake Request-like object with scope
        result = await owner_dep(
            tenant=MagicMock(id=1),
            user=MagicMock(id=1),
        )

        assert result == mock_tenant_user


# ---------------------------------------------------------------------------
# Test: Non-OWNER role → 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_owner_denied():
    """A user without the OWNER role must be denied (403)."""
    from fastapi import HTTPException
    from tenant2fast_fastapi.dependencies.tenant_rbac import require_tenant_owner

    owner_dep = require_tenant_owner()

    mock_tenant_user = _make_user()
    mock_roles = [_make_role("Admin"), _make_role("Member")]

    with (
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_user_by_auth_id",
            new_callable=AsyncMock,
            return_value=mock_tenant_user,
        ),
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.tenant_role_service.list_user_roles",
            new_callable=AsyncMock,
            return_value=mock_roles,
        ),
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_session",
        ) as mock_session_ctx,
    ):
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await owner_dep(
                tenant=MagicMock(id=1),
                user=MagicMock(id=1),
            )

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test: is_admin=true but no OWNER → 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_admin_only_denied():
    """is_admin=true must NOT bypass the OWNER requirement (R5 H2)."""
    from fastapi import HTTPException
    from tenant2fast_fastapi.dependencies.tenant_rbac import require_tenant_owner

    owner_dep = require_tenant_owner()

    mock_tenant_user = _make_user()
    mock_tenant_user.is_admin = True  # has is_admin but no OWNER role
    mock_roles = [_make_role("Admin")]

    with (
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_user_by_auth_id",
            new_callable=AsyncMock,
            return_value=mock_tenant_user,
        ),
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.tenant_role_service.list_user_roles",
            new_callable=AsyncMock,
            return_value=mock_roles,
        ),
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_session",
        ) as mock_session_ctx,
    ):
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await owner_dep(
                tenant=MagicMock(id=1),
                user=MagicMock(id=1),
            )

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test: User not in tenant → 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_not_in_tenant_denied():
    """User not registered in tenant must be denied."""
    from fastapi import HTTPException
    from tenant2fast_fastapi.dependencies.tenant_rbac import require_tenant_owner

    owner_dep = require_tenant_owner()

    with (
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_user_by_auth_id",
            new_callable=AsyncMock,
            return_value=None,  # not found
        ),
        patch(
            "tenant2fast_fastapi.dependencies.tenant_rbac.get_tenant_session",
        ) as mock_session_ctx,
    ):
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await owner_dep(
                tenant=MagicMock(id=1),
                user=MagicMock(id=1),
            )

        assert exc_info.value.status_code == 403
