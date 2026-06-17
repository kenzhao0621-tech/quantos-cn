"""RBAC and authentication for Gateway API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Role(str, Enum):
    ADMIN = "admin"
    INVESTOR = "investor"
    RESEARCHER = "researcher"
    VIEWER = "viewer"
    SERVICE_RESEARCH = "service_research"
    SERVICE_RISK = "service_risk"


_BEGINNER_PERMS = {
    "agents:invoke", "tasks:create", "tasks:read", "market:read",
    "research:run", "research:read", "risk:read", "paper:read", "paper:trade",
    "audit:read", "obs:read", "mode:promote", "broker:connect", "broker:assist",
}

PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "agents:invoke", "tasks:create", "tasks:read", "market:read",
        "research:run", "research:read", "risk:read", "risk:halt",
        "risk:reset_request", "risk:reset_confirm", "paper:read", "paper:trade", "audit:read", "obs:read",
        "mode:promote", "portal:admin", "broker:connect", "broker:assist",
    },
    Role.INVESTOR: set(_BEGINNER_PERMS),
    Role.RESEARCHER: set(_BEGINNER_PERMS),
    Role.VIEWER: {
        "market:read", "research:read", "risk:read", "paper:read", "audit:read",
    },
    Role.SERVICE_RESEARCH: {
        "agents:invoke", "tasks:create", "tasks:read", "market:read",
        "research:run", "research:read", "paper:read", "paper:trade",
    },
    Role.SERVICE_RISK: {
        "risk:read", "risk:halt", "risk:reset_request", "risk:reset_confirm",
        "audit:read", "market:read",
    },
}


@dataclass
class Principal:
    user_id: str
    role: Role
    project_id: str
    is_service_account: bool = False

    def has_permission(self, permission: str) -> bool:
        return permission in PERMISSIONS.get(self.role, set())


# Dev portal keys (must match apps/portal-web/api-client.js when config omits service_accounts)
_DEV_API_KEYS: dict[str, Role] = {
    "dev-investor-key": Role.INVESTOR,
    "dev-researcher-key": Role.RESEARCHER,
    "dev-service-risk-key": Role.SERVICE_RISK,
    "svc-quant-pipeline": Role.SERVICE_RESEARCH,
    "svc-portal-read": Role.VIEWER,
}


def authenticate(api_key: str, demo_key: str, service_accounts: list[dict[str, str]]) -> Optional[Principal]:
    if api_key == demo_key:
        return Principal(user_id="demo-admin", role=Role.ADMIN, project_id="netlify-demo-china-ashare")
    for sa in service_accounts:
        if sa.get("id") == api_key:
            role_name = sa.get("role", "viewer")
            try:
                role = Role(role_name)
            except ValueError:
                role = Role.VIEWER
            return Principal(
                user_id=sa["id"], role=role,
                project_id="netlify-demo-china-ashare", is_service_account=True,
            )
    dev_role = _DEV_API_KEYS.get(api_key)
    if dev_role:
        return Principal(
            user_id=api_key, role=dev_role,
            project_id="netlify-demo-china-ashare", is_service_account=False,
        )
    return None


def require_permission(principal: Principal | None, permission: str) -> tuple[bool, str]:
    if principal is None:
        return False, "unauthenticated"
    if not principal.has_permission(permission):
        return False, f"forbidden: missing {permission}"
    return True, "ok"
