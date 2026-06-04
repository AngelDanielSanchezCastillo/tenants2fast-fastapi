from datetime import datetime
from sqlalchemy import MetaData
from sqlalchemy.orm import registry
from sqlmodel import Field, SQLModel
from tools2fast_fastapi import IdMixin, AuditTimestampMixin

# MetaData exclusive for tenant-specific tables.
tenant_metadata = MetaData()
tenant_registry = registry(metadata=tenant_metadata)

class BasicModel(SQLModel, registry=tenant_registry):
    __abstract__ = True

class BasicTenantModel(AuditTimestampMixin, BasicModel):
    """Base model without predefined primary key, but with audit + timestamps."""

    __abstract__ = True

class IdTenantModel(IdMixin, BasicModel):
    """Base model with BigInteger primary key."""
    
    __abstract__ = True

class TenantAuditBaseModel(AuditTimestampMixin, IdTenantModel):
    """
    Base model for all tenant-specific tables with audit fields.
    
    Models that inherit from this class will be created in tenant databases.
    Each tenant gets their own isolated database with these tables.
    
    Includes:
    - created_at, updated_at (from AuditTimestampMixin)
    - created_by, updated_by (from AuditTimestampMixin, auto-populated via events)
    """

    __abstract__ = True

# Alias for backward compatibility
TenantBaseModel = TenantAuditBaseModel

