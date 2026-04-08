from datetime import datetime
from sqlalchemy import MetaData
from sqlalchemy.orm import registry
from sqlmodel import Field, SQLModel

# MetaData exclusive for tenant-specific tables.
tenant_metadata = MetaData()
tenant_registry = registry(metadata=tenant_metadata)


class TenantBaseModel(SQLModel, registry=tenant_registry):
    """
    Base model for all tenant-specific tables.
    
    Models that inherit from this class will be created in tenant databases.
    Each tenant gets their own isolated database with these tables.
    """
    
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        """SQLModel configuration"""
        from_attributes = True
