"""
Risk arbitration: Map impact + uncertainty to decision/approval type.

Deterministic matrix (no LLM):
- LOW impact + LOW uncertainty → AUTO (proceed without approval)
- HIGH impact + HIGH uncertainty → ESCALATE (to executive)
- etc.
"""

from enum import Enum
from typing import Dict, Tuple
from dataclasses import dataclass


class ImpactLevel(str, Enum):
    """Impact of a decision/change."""
    LOW = "low"                 # Minimal business impact
    MEDIUM = "medium"           # Moderate impact
    HIGH = "high"               # Major impact (budget, timeline, scope)
    CRITICAL = "critical"       # Enterprise-wide impact


class UncertaintyLevel(str, Enum):
    """Uncertainty/risk in the decision."""
    LOW = "low"                 # Well-understood, precedent exists
    MEDIUM = "medium"           # Some unknowns
    HIGH = "high"               # Many unknowns, novel situation
    CRITICAL = "critical"       # Highly unpredictable


class DecisionType(str, Enum):
    """How to handle a decision."""
    AUTO = "auto"               # Proceed automatically (no approval needed)
    CONFIRM = "confirm"         # Notify, but no approval needed
    APPROVAL_REQUIRED = "approval_required"  # Requires role-based approval
    EXECUTIVE_APPROVAL = "executive_approval"  # Escalate to leadership
    ESCALATE = "escalate"       # Escalate for expert review


@dataclass
class RiskArbitration:
    """Deterministic risk mapping."""
    impact: ImpactLevel
    uncertainty: UncertaintyLevel
    decision_type: DecisionType
    description: str
    notification_required: bool = False


class RiskMatrix:
    """
    Deterministic 4×4 risk matrix (no LLM involved).
    
    Maps (impact, uncertainty) → decision type
    """
    
    # Define all 16 cells of the risk matrix
    MATRIX: Dict[Tuple[ImpactLevel, UncertaintyLevel], RiskArbitration] = {
        # Low impact, Low uncertainty → AUTO
        (ImpactLevel.LOW, UncertaintyLevel.LOW): RiskArbitration(
            impact=ImpactLevel.LOW, uncertainty=UncertaintyLevel.LOW,
            decision_type=DecisionType.AUTO,
            description="Low impact, well-understood → proceed automatically",
        ),
        
        # Low impact, Medium uncertainty → AUTO
        (ImpactLevel.LOW, UncertaintyLevel.MEDIUM): RiskArbitration(
            impact=ImpactLevel.LOW, uncertainty=UncertaintyLevel.MEDIUM,
            decision_type=DecisionType.AUTO,
            description="Low impact, some unknowns → proceed with monitoring",
        ),
        
        # Low impact, High uncertainty → CONFIRM
        (ImpactLevel.LOW, UncertaintyLevel.HIGH): RiskArbitration(
            impact=ImpactLevel.LOW, uncertainty=UncertaintyLevel.HIGH,
            decision_type=DecisionType.CONFIRM,
            description="Low impact, high uncertainty → confirm but don't block",
            notification_required=True,
        ),
        
        # Low impact, Critical uncertainty → APPROVAL_REQUIRED
        (ImpactLevel.LOW, UncertaintyLevel.CRITICAL): RiskArbitration(
            impact=ImpactLevel.LOW, uncertainty=UncertaintyLevel.CRITICAL,
            decision_type=DecisionType.APPROVAL_REQUIRED,
            description="Low impact, highly unpredictable → require approval",
        ),
        
        # Medium impact, Low uncertainty → AUTO
        (ImpactLevel.MEDIUM, UncertaintyLevel.LOW): RiskArbitration(
            impact=ImpactLevel.MEDIUM, uncertainty=UncertaintyLevel.LOW,
            decision_type=DecisionType.AUTO,
            description="Moderate impact, well-understood → proceed",
        ),
        
        # Medium impact, Medium uncertainty → CONFIRM
        (ImpactLevel.MEDIUM, UncertaintyLevel.MEDIUM): RiskArbitration(
            impact=ImpactLevel.MEDIUM, uncertainty=UncertaintyLevel.MEDIUM,
            decision_type=DecisionType.CONFIRM,
            description="Moderate impact/uncertainty → confirm with stakeholders",
            notification_required=True,
        ),
        
        # Medium impact, High uncertainty → APPROVAL_REQUIRED
        (ImpactLevel.MEDIUM, UncertaintyLevel.HIGH): RiskArbitration(
            impact=ImpactLevel.MEDIUM, uncertainty=UncertaintyLevel.HIGH,
            decision_type=DecisionType.APPROVAL_REQUIRED,
            description="Moderate impact, high uncertainty → require formal approval",
        ),
        
        # Medium impact, Critical uncertainty → EXECUTIVE_APPROVAL
        (ImpactLevel.MEDIUM, UncertaintyLevel.CRITICAL): RiskArbitration(
            impact=ImpactLevel.MEDIUM, uncertainty=UncertaintyLevel.CRITICAL,
            decision_type=DecisionType.EXECUTIVE_APPROVAL,
            description="Moderate impact, critical uncertainty → escalate to leadership",
        ),
        
        # High impact, Low uncertainty → APPROVAL_REQUIRED
        (ImpactLevel.HIGH, UncertaintyLevel.LOW): RiskArbitration(
            impact=ImpactLevel.HIGH, uncertainty=UncertaintyLevel.LOW,
            decision_type=DecisionType.APPROVAL_REQUIRED,
            description="High impact, well-understood → require approval",
        ),
        
        # High impact, Medium uncertainty → APPROVAL_REQUIRED
        (ImpactLevel.HIGH, UncertaintyLevel.MEDIUM): RiskArbitration(
            impact=ImpactLevel.HIGH, uncertainty=UncertaintyLevel.MEDIUM,
            decision_type=DecisionType.APPROVAL_REQUIRED,
            description="High impact, moderate uncertainty → require approval",
        ),
        
        # High impact, High uncertainty → EXECUTIVE_APPROVAL
        (ImpactLevel.HIGH, UncertaintyLevel.HIGH): RiskArbitration(
            impact=ImpactLevel.HIGH, uncertainty=UncertaintyLevel.HIGH,
            decision_type=DecisionType.EXECUTIVE_APPROVAL,
            description="High impact, high uncertainty → escalate to leadership",
        ),
        
        # High impact, Critical uncertainty → ESCALATE
        (ImpactLevel.HIGH, UncertaintyLevel.CRITICAL): RiskArbitration(
            impact=ImpactLevel.HIGH, uncertainty=UncertaintyLevel.CRITICAL,
            decision_type=DecisionType.ESCALATE,
            description="High impact, critical uncertainty → escalate for expert review",
        ),
        
        # Critical impact, Low uncertainty → EXECUTIVE_APPROVAL
        (ImpactLevel.CRITICAL, UncertaintyLevel.LOW): RiskArbitration(
            impact=ImpactLevel.CRITICAL, uncertainty=UncertaintyLevel.LOW,
            decision_type=DecisionType.EXECUTIVE_APPROVAL,
            description="Critical impact, well-understood → escalate to top leadership",
        ),
        
        # Critical impact, Medium uncertainty → EXECUTIVE_APPROVAL
        (ImpactLevel.CRITICAL, UncertaintyLevel.MEDIUM): RiskArbitration(
            impact=ImpactLevel.CRITICAL, uncertainty=UncertaintyLevel.MEDIUM,
            decision_type=DecisionType.EXECUTIVE_APPROVAL,
            description="Critical impact, moderate uncertainty → escalate to top leadership",
        ),
        
        # Critical impact, High uncertainty → ESCALATE
        (ImpactLevel.CRITICAL, UncertaintyLevel.HIGH): RiskArbitration(
            impact=ImpactLevel.CRITICAL, uncertainty=UncertaintyLevel.HIGH,
            decision_type=DecisionType.ESCALATE,
            description="Critical impact, high uncertainty → escalate for expert judgment",
        ),
        
        # Critical impact, Critical uncertainty → ESCALATE
        (ImpactLevel.CRITICAL, UncertaintyLevel.CRITICAL): RiskArbitration(
            impact=ImpactLevel.CRITICAL, uncertainty=UncertaintyLevel.CRITICAL,
            decision_type=DecisionType.ESCALATE,
            description="Critical impact, critical uncertainty → escalate immediately",
        ),
    }
    
    @classmethod
    def get_decision(
        cls,
        impact: ImpactLevel | str,
        uncertainty: UncertaintyLevel | str,
    ) -> RiskArbitration | None:
        """
        Get decision type for impact + uncertainty combination.
        
        Args:
            impact: ImpactLevel enum or string
            uncertainty: UncertaintyLevel enum or string
        
        Returns:
            RiskArbitration with decision type and description
        """
        # Convert strings to enums if needed
        if isinstance(impact, str):
            impact = ImpactLevel(impact)
        if isinstance(uncertainty, str):
            uncertainty = UncertaintyLevel(uncertainty)
        
        return cls.MATRIX.get((impact, uncertainty))
    
    @classmethod
    def requires_approval(cls, impact: ImpactLevel | str, uncertainty: UncertaintyLevel | str) -> bool:
        """Check if decision requires any form of approval."""
        arb = cls.get_decision(impact, uncertainty)
        if not arb:
            return True  # Unknown = require approval
        
        return arb.decision_type in {
            DecisionType.APPROVAL_REQUIRED,
            DecisionType.EXECUTIVE_APPROVAL,
            DecisionType.ESCALATE,
        }
    
    @classmethod
    def requires_escalation(cls, impact: ImpactLevel | str, uncertainty: UncertaintyLevel | str) -> bool:
        """Check if decision requires escalation to leadership."""
        arb = cls.get_decision(impact, uncertainty)
        if not arb:
            return True  # Unknown = escalate
        
        return arb.decision_type in {
            DecisionType.EXECUTIVE_APPROVAL,
            DecisionType.ESCALATE,
        }
