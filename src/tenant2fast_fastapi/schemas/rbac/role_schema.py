from pydantic import ConfigDict
from rbac2fast_core.schemas import RoleBase, RoleCreate, RoleRead, RoleUpdate


class RoleCreate(RoleCreate):
    """Schema to create a role."""
    pass


class RoleRead(RoleRead):
    """Schema to read a role."""
    pass

    model_config = ConfigDict(from_attributes=True)


class RoleUpdate(RoleUpdate):
    """Schema to update a role."""
    pass
