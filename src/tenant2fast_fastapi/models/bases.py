from datetime import datetime
from sqlalchemy import MetaData
from sqlalchemy.orm import registry
from sqlmodel import Field, SQLModel
from tools2fast_fastapi import IdMixin, TimestampMixin

# MetaData exclusive for tenant-specific tables.
tenant_metadata = MetaData()
tenant_registry = registry(metadata=tenant_metadata)

class BasicModel(SQLModel, registry=tenant_registry):
    __abstract__ = True

class BasicTenantModel(TimestampMixin, BasicModel):
    """Base model without predefined primary key, but with timestamps."""

    __abstract__ = True

class IdTenantModel(IdMixin, BasicModel):
    """Base model with BigInteger primary key."""
    
    __abstract__ = True

class TenantBaseModel(TimestampMixin, IdTenantModel):
    """
    Base model for all tenant-specific tables.
    
    Models that inherit from this class will be created in tenant databases.
    Each tenant gets their own isolated database with these tables.
    """

    __abstract__ = True

