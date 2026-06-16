"""Gateway auth package."""

from gateway.auth.rbac import (
    PERMISSIONS,
    Principal,
    Role,
    authenticate,
    require_permission,
)

__all__ = [
    "PERMISSIONS",
    "Principal",
    "Role",
    "authenticate",
    "require_permission",
]
