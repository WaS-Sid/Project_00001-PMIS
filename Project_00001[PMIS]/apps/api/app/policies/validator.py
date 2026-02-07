"""
Patch validator: Determines if a state change/edit is allowed.

References:
- Status transitions (deterministic state machine)
- Approval matrix (required roles)
- Risk arbitration (impact × uncertainty → decision)
"""

from typing import Dict, Any, Tuple
from dataclasses import dataclass

from app.tools.user_context import UserContext
from app.tools.models import Package, Task
from .status_transitions import PackageTransitions, TaskTransitions, PackageStatus, TaskStatus
from .approval_matrix import ApprovalMatrix
from .risk_arbitration import RiskMatrix, ImpactLevel, UncertaintyLevel


@dataclass
class ValidationResult:
    """Result of patch validation."""
    is_allowed: bool             # True if patch is allowed
    requires_approval: bool      # True if approval workflow needed
    requires_escalation: bool    # True if escalate to leadership
    decision_type: str | None    # From RiskMatrix (auto, confirm, approval_required, escalate)
    reasons: list[str]           # List of validation reasons/errors
    warnings: list[str]          # Warnings (not blocking)


def validate_patch(
    entity_type: str,
    entity: Package | Task | Dict[str, Any],
    patch: Dict[str, Any],
    user: UserContext,
    impact: ImpactLevel | str = ImpactLevel.MEDIUM,
    uncertainty: UncertaintyLevel | str = UncertaintyLevel.LOW,
) -> ValidationResult:
    """
    Validate if a patch (state change or edit) is allowed.
    
    Checks:
    1. Status transition is valid (deterministic state machine)
    2. User has required roles (approval matrix)
    3. Risk level determines approval needed (risk matrix)
    
    Args:
        entity_type: 'package' or 'task'
        entity: Entity object or dict with current state
        patch: Proposed changes (e.g., {'status': 'active', 'metadata': {...}})
        user: UserContext with roles
        impact: Business impact level
        uncertainty: Uncertainty/risk level
    
    Returns:
        ValidationResult with is_allowed, requires_approval, reasons, warnings
    """
    
    reasons = []
    warnings = []
    requires_approval = False
    requires_escalation = False
    decision_type = "auto"
    
    # Extract current status if present
    current_status = None
    if isinstance(entity, dict):
        current_status = entity.get("status")
    else:
        current_status = getattr(entity, "status", None)
    
    # ===== Check 1: Status Transitions =====
    new_status = patch.get("status")
    
    if new_status and current_status:
        if entity_type == "package":
            if not PackageTransitions.is_valid(current_status, new_status):
                reasons.append(
                    f"Invalid status transition: {current_status} → {new_status}. "
                    f"Valid next statuses: {PackageTransitions.get_valid_next_statuses(current_status)}"
                )
                
                return ValidationResult(
                    is_allowed=False,
                    requires_approval=False,
                    requires_escalation=False,
                    decision_type=None,
                    reasons=reasons,
                    warnings=[],
                )
            
            # Check if transition requires approval
            rule = PackageTransitions.get_rule(current_status, new_status)
            if rule and rule.requires_approval:
                requires_approval = True
                reasons.append(f"Transition {current_status} → {new_status} requires approval")
        
        elif entity_type == "task":
            if not TaskTransitions.is_valid(current_status, new_status):
                reasons.append(
                    f"Invalid status transition: {current_status} → {new_status}. "
                    f"Valid next statuses: {TaskTransitions.get_valid_next_statuses(current_status)}"
                )
                
                return ValidationResult(
                    is_allowed=False,
                    requires_approval=False,
                    requires_escalation=False,
                    decision_type=None,
                    reasons=reasons,
                    warnings=[],
                )
    
    # ===== Check 2: Approval Matrix (Required Roles) =====
    action = None
    
    if new_status:
        action = f"{entity_type}.status:{new_status}"
    elif "metadata" in patch:
        action = f"{entity_type}.metadata.update"
    elif "budget" in patch:
        action = f"{entity_type}.budget.change"
    elif "scope" in patch:
        action = f"{entity_type}.scope.change"
    
    if action:
        is_approved, approval_reason = ApprovalMatrix.is_action_approved(
            action, user.roles
        )
        
        if not is_approved:
            reasons.append(approval_reason)
            requires_approval = True
    
    # ===== Check 3: Risk Arbitration =====
    risk_decision = RiskMatrix.get_decision(impact, uncertainty)
    
    if risk_decision:
        decision_type = risk_decision.decision_type.value
        
        if risk_decision.decision_type.value != "auto":
            reasons.append(
                f"Risk assessment ({impact}/{uncertainty}): {risk_decision.description}"
            )
        
        if RiskMatrix.requires_approval(impact, uncertainty):
            requires_approval = True
        
        if RiskMatrix.requires_escalation(impact, uncertainty):
            requires_escalation = True
        
        if risk_decision.notification_required:
            warnings.append("Notification required for stakeholders")
    
    # Determine final is_allowed
    is_allowed = len([r for r in reasons if "Invalid" in r or "requires roles" in r]) == 0
    
    return ValidationResult(
        is_allowed=is_allowed,
        requires_approval=requires_approval,
        requires_escalation=requires_escalation,
        decision_type=decision_type,
        reasons=reasons,
        warnings=warnings,
    )


def validate_package_status_change(
    package: Package,
    new_status: str,
    user: UserContext,
    impact: ImpactLevel | str = ImpactLevel.MEDIUM,
    uncertainty: UncertaintyLevel | str = UncertaintyLevel.MEDIUM,
) -> ValidationResult:
    """Convenience function for package status changes."""
    patch = {"status": new_status}
    return validate_patch("package", package, patch, user, impact, uncertainty)


def validate_task_status_change(
    task: Task,
    new_status: str,
    user: UserContext,
    impact: ImpactLevel | str = ImpactLevel.LOW,
    uncertainty: UncertaintyLevel | str = UncertaintyLevel.LOW,
) -> ValidationResult:
    """Convenience function for task status changes."""
    patch = {"status": new_status}
    return validate_patch("task", task, patch, user, impact, uncertainty)
