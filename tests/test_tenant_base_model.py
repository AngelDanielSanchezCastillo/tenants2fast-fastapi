"""
test_tenant_base_model.py – tests for custom models and tenant-specific tables.
"""

import pytest
from sqlalchemy import inspect
from sqlmodel import Field, select
from tenant2fast_fastapi.models.bases import TenantBaseModel
from tenant2fast_fastapi.databases.tenant_db_factory import (
    initialize_tenant_schema,
    get_tenant_session,
    tenant_metadata,
)
from oauth2fast_fastapi import AuthModel


# Define a test-specific model inheriting from TenantBaseModel
class Product(TenantBaseModel, table=True):
    __tablename__ = "test_products"
    name: str = Field(index=True)
    price: float


@pytest.mark.asyncio
async def test_custom_model_registration():
    """Verify custom model is registered in tenant_metadata and not in AuthModel."""
    # Register check
    assert "test_products" in tenant_metadata.tables
    assert "test_products" not in AuthModel.metadata.tables


@pytest.mark.asyncio
async def test_custom_model_schema_creation(test_tenant):
    """Verify custom model table is created in the tenant's isolated DB."""
    # We use get_tenant_session and check the database
    session = await get_tenant_session(test_tenant.id)
    
    async with session:
        # Check if table exists
        def check_table_exists(conn):
            # In run_sync, conn is the underlying sync Session
            inspector = inspect(conn.bind)
            return inspector.has_table("test_products")

        exists = await session.run_sync(check_table_exists)
        assert exists, "Custom table 'test_products' should exist in the tenant DB"


@pytest.mark.asyncio
async def test_custom_model_crud(test_tenant):
    """Verify CRUD operations on custom model in tenant DB."""
    session = await get_tenant_session(test_tenant.id)
    
    async with session:
        # Create
        product = Product(name="Tenant Laptop", price=1200.0)
        session.add(product)
        await session.commit()
        await session.refresh(product)
        assert product.id is not None

        # Read using SQLModel standard async API
        result = await session.exec(select(Product).where(Product.id == product.id))
        fetched_product = result.one_or_none()
        assert fetched_product is not None
        assert fetched_product.name == "Tenant Laptop"
