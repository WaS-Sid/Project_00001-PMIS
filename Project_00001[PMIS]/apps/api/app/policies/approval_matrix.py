"""
Approval matrix: Maps actions to required roles for authorization.

Example: "package.status = AWARDED" requires PM or ADMIN
"""

from typing import Set, Dict, List
from enum import Enum
from dataclasses import dataclass
from app.tools.user_context import Role


@dataclass
class ApprovalRule:
    """A governance rule mapping action to required roles."""
    action: str
    required_roles: Set[Role]
    description: str
    min_roles_satisfied: int = 1  # How many required roles must be satisfied


class ApprovalMatrix:
    """
    Deterministic approval matrix without LLM.
    Maps actions (entity + state transition) to required roles.
    """
    
    # Package status change requirements
    RULES: List[ApprovalRule] = [
        # ===== Package Submission =====
        ApprovalRule(
            action="package.status:submitted",
            required_roles={Role.ANALYST, Role.ADMIN},
            description="Submit package for review (analyst or admin)",
        ),
        
        # ===== Package Review & Approval =====
        ApprovalRule(
            action="package.status:in_review",
            required_roles={Role.ADMIN},
            description="Initiate formal review (admin only)",
        ),
        ApprovalRule(
            action="package.status:approved",
            required_roles={Role.ADMIN},
            description="Approve package after review (admin only)",
        ),
        
        # ===== Package Award (HIGH GOVERNANCE) =====
        ApprovalRule(
            action="package.status:awarded",
            required_roles={Role.ADMIN},  # Could optionally add PM
            description="Award package/contract (admin approval required)",
        ),
        
        # ===== Package Activation =====
        ApprovalRule(
            action="package.status:active",
            required_roles={Role.ADMIN, Role.OPERATOR},
            description="Activate package execution (admin or operator)",
        ),
        
        # ===== Package Cancellation (risky) =====
        ApprovalRule(
            action="package.status:cancelled",
            required_roles={Role.ADMIN},
            description="Cancel package (admin approval required, especially if active)",
        ),
        
        # ===== Task Status Changes =====
        ApprovalRule(
            action="task.status:review_needed",
            required_roles={Role.ANALYST, Role.OPERATOR, Role.ADMIN},
            description="Submit task for review",
        ),
        ApprovalRule(
            action="task.status:completed",
            required_roles={Role.ANALYST, Role.OPERATOR, Role.ADMIN},
            description="Mark task complete",
        ),
        ApprovalRule(
            action="task.status:cancelled",
            required_roles={Role.OPERATOR, Role.ADMIN},
            description="Cancel task (operator or admin)",
        ),
        
        # ===== Package Metadata Changes =====
        ApprovalRule(
            action="package.metadata.update",
            required_roles={Role.ANALYST, Role.ADMIN},
            description="Update package metadata",
        ),
        
        # ===== High-Risk Edits =====
        ApprovalRule(
            action="package.budget.change",
            required_roles={Role.ADMIN},
            description="Change package budget (admin only)",
        ),
        ApprovalRule(
            action="package.scope.change",
            required_roles={Role.ADMIN},
            description="Change package scope (admin only)",
        ),
    ]
    
    # Build lookup: action → ApprovalRule
    _MATRIX: Dict[str, ApprovalRule] = {}
    
    @classmethod
    def _build_matrix(cls):
        """Build action → rule lookup."""
        if cls._MATRIX:
            return
        
        for rule in cls.RULES:
            cls._MATRIX[rule.action] = rule
    
    @classmethod
    def get_required_roles(cls, action: str) -> Set[Role] | None:
        """Get required roles for action."""
        cls._build_matrix()
        rule = cls._MATRIX.get(action)
        return rule.required_roles if rule else None
    
    @classmethod
    def get_rule(cls, action: str) -> ApprovalRule | None:
        """Get full approval rule."""
        cls._build_matrix()
        return cls._MATRIX.get(action)
    
    @classmethod
    def is_action_approved(cls, action: str, user_roles: Set[Role]) -> tuple[bool, str]:
        """
        Check if user has required roles for action.
        
        Returns: (is_approved, reason)
        """
        cls._build_matrix()
        rule = cls._MATRIX.get(action)
        
        if not rule:
            # No rule = no approval needed (open action)
            return True, f"No approval required for {action}"
        
        # Check if user has any of the required roles
        has_role = bool(user_roles & rule.required_roles)
        
        if has_role:
            return True, f"User has required role for {action}"
        
        required_role_names = ", ".join(r.value for r in rule.required_roles)
        return False, f"Action '{action}' requires one of: {required_role_names}"
    
    @classmethod
    def list_rules(cls) -> List[ApprovalRule]:
        """List all approval rules."""
        return cls.RULES
