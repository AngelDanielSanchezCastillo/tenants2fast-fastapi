from datetime import datetime
from uuid import UUID

from sqlalchemy import MetaData
from sqlalchemy.orm import registry
from sqlmodel import Field, SQLModel
from tools2fast_fastapi import (
    AuditTimestampMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDIdMixin,
)

# MetaData exclusive for tenant-specific tables.
tenant_metadata = MetaData()
tenant_registry = registry(metadata=tenant_metadata)


class BasicModel(SQLModel, registry=tenant_registry):
    __abstract__ = True


class BasicTenantModel(TimestampMixin, BasicModel):
    """Base model without predefined primary key, but with timestamps."""

    __abstract__ = True


class IdTenantModel(UUIDIdMixin, BasicModel):
    """Base model with UUID v7 primary key."""

    __abstract__ = True


class TenantAuditBaseModel(AuditTimestampMixin, IdTenantModel):
    """
    Base model for all tenant-specific tables with audit fields.

    Models that inherit from this class will be created in tenant databases.
    Each tenant gets their own isolated database with these tables.

    Includes:
    - id (UUID v7, from UUIDIdMixin)
    - created_at, updated_at (from TimestampMixin via AuditTimestampMixin)
    - created_by, updated_by (from AuditMixin via AuditTimestampMixin, auto-populated via events)
    """

    __abstract__ = True


class TenantSoftDeleteModel(SoftDeleteMixin, TenantAuditBaseModel):
    """
    Base model for tenant tables with soft-delete support.

    Includes everything from TenantAuditBaseModel plus:
    - deleted_at (datetime | None, from SoftDeleteMixin)
    - deleted_by (UUID | None, from SoftDeleteMixin)
    """

    __abstract__ = True


# Alias for backward compatibility — most tenant models want soft-delete.
TenantBaseModel = TenantSoftDeleteModel
