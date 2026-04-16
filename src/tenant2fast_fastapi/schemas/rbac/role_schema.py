from pydantic import ConfigDict
from rbac2fast_core.schemas import RoleBase, RoleCreate, RoleRead, RoleUpdate


class TenantRoleCreate(RoleCreate):
    """Schema to create a tenant role."""
    pass


class TenantRoleRead(RoleRead):
    """Schema to read a tenant role."""
    pass

    model_config = ConfigDict(from_attributes=True)


class TenantRoleUpdate(RoleUpdate):
    """Schema to update a tenant role."""
    pass
