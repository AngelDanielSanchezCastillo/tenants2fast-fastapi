from datetime import datetime
from sqlmodel import Field, SQLModel
from ..databases.tenant_db_factory import tenant_metadata


class TenantBaseModel(SQLModel):
    metadata = tenant_metadata
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
