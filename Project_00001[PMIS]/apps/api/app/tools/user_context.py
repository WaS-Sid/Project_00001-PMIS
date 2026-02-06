from typing import Set
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    OPERATOR = "operator"
    VIEWER = "viewer"


class UserContext:
    """Simple RBAC context for tool operations."""
    
    def __init__(self, user_id: str, name: str, roles: Set[Role] | list[str]):
        self.user_id = user_id
        self.name = name
        self.roles = set(roles) if isinstance(roles, list) else roles
    
    def has_role(self, role: Role | str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles
    
    def has_any_role(self, *roles: Role | str) -> bool:
        """Check if user has any of the given roles."""
        return any(r in self.roles for r in roles)
    
    def has_all_roles(self, *roles: Role | str) -> bool:
        """Check if user has all given roles."""
        return all(r in self.roles for r in roles)
    
    def require_role(self, role: Role | str) -> None:
        """Raise PermissionError if user doesn't have role."""
        if not self.has_role(role):
            raise PermissionError(f"User {self.user_id} requires {role} role")
    
    def __repr__(self) -> str:
        return f"UserContext(user_id={self.user_id}, name={self.name}, roles={self.roles})"
