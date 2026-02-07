import pytest
from app.policies.risk_arbitration import (
    ImpactLevel, UncertaintyLevel, DecisionType, RiskMatrix
)


class TestRiskMatrixDiagonals:
    """Test risk matrix for symmetric impact/uncertainty combinations."""
    
    def test_low_low_is_auto(self):
        """Low impact + Low uncertainty = AUTO decision."""
        risk = RiskMatrix.get_decision(ImpactLevel.LOW, UncertaintyLevel.LOW)
        assert risk is not None
        assert risk.decision_type == DecisionType.AUTO
        assert not risk.requires_approval()
        assert not risk.requires_escalation()
    
    def test_medium_medium_requires_confirmation(self):
        """Medium impact + Medium uncertainty = CONFIRM decision."""
        risk = RiskMatrix.get_decision(ImpactLevel.MEDIUM, UncertaintyLevel.MEDIUM)
        assert risk is not None
        assert risk.decision_type == DecisionType.CONFIRM
        assert not risk.requires_approval()
        assert not risk.requires_escalation()
    
    def test_high_high_requires_executive_approval(self):
        """High impact + High uncertainty = EXECUTIVE_APPROVAL."""
        risk = RiskMatrix.get_decision(ImpactLevel.HIGH, UncertaintyLevel.HIGH)
        assert risk is not None
        assert risk.decision_type == DecisionType.EXECUTIVE_APPROVAL
        assert risk.requires_approval()
        assert not risk.requires_escalation()
    
    def test_critical_critical_escalate(self):
        """Critical impact + Critical uncertainty = ESCALATE."""
        risk = RiskMatrix.get_decision(ImpactLevel.CRITICAL, UncertaintyLevel.CRITICAL)
        assert risk is not None
        assert risk.decision_type == DecisionType.ESCALATE
        assert risk.requires_approval()
        assert risk.requires_escalation()


class TestRiskMatrixAsymmetric:
    """Test risk matrix for asymmetric combinations (impact ≠ uncertainty)."""
    
    def test_high_impact_low_uncertainty_approval(self):
        """High impact + Low uncertainty (clear risk) = APPROVAL_REQUIRED."""
        risk = RiskMatrix.get_decision(ImpactLevel.HIGH, UncertaintyLevel.LOW)
        assert risk is not None
        assert risk.decision_type == DecisionType.APPROVAL_REQUIRED
        assert risk.requires_approval()
    
    def test_low_impact_high_uncertainty_approval(self):
        """Low impact + High uncertainty (unclear but low damage) = APPROVAL_REQUIRED."""
        risk = RiskMatrix.get_decision(ImpactLevel.LOW, UncertaintyLevel.HIGH)
        assert risk is not None
        assert risk.decision_type == DecisionType.APPROVAL_REQUIRED
        assert risk.requires_approval()
    
    def test_critical_impact_low_uncertainty_executive_approval(self):
        """Critical impact + Low uncertainty (definite major consequence) = EXECUTIVE_APPROVAL."""
        risk = RiskMatrix.get_decision(ImpactLevel.CRITICAL, UncertaintyLevel.LOW)
        assert risk is not None
        assert risk.decision_type == DecisionType.EXECUTIVE_APPROVAL
        assert risk.requires_approval()
    
    def test_low_impact_critical_uncertainty_confirm(self):
        """Low impact + Critical uncertainty (high doubt, low damage) = CONFIRM."""
        risk = RiskMatrix.get_decision(ImpactLevel.LOW, UncertaintyLevel.CRITICAL)
        assert risk is not None
        assert risk.decision_type == DecisionType.CONFIRM


class TestRiskMatrixDecisionTypes:
    """Test all decision types are reachable."""
    
    def test_auto_decision_exists(self):
        """DecisionType.AUTO is reachable."""
        risk = RiskMatrix.get_decision(ImpactLevel.LOW, UncertaintyLevel.LOW)
        assert risk.decision_type == DecisionType.AUTO
    
    def test_confirm_decision_exists(self):
        """DecisionType.CONFIRM is reachable."""
        risk = RiskMatrix.get_decision(ImpactLevel.MEDIUM, UncertaintyLevel.MEDIUM)
        assert risk.decision_type == DecisionType.CONFIRM
    
    def test_approval_required_decision_exists(self):
        """DecisionType.APPROVAL_REQUIRED is reachable."""
        risk = RiskMatrix.get_decision(ImpactLevel.MEDIUM, UncertaintyLevel.LOW)
        assert risk.decision_type == DecisionType.APPROVAL_REQUIRED
    
    def test_executive_approval_decision_exists(self):
        """DecisionType.EXECUTIVE_APPROVAL is reachable."""
        risk = RiskMatrix.get_decision(ImpactLevel.HIGH, UncertaintyLevel.HIGH)
        assert risk.decision_type == DecisionType.EXECUTIVE_APPROVAL
    
    def test_escalate_decision_exists(self):
        """DecisionType.ESCALATE is reachable."""
        risk = RiskMatrix.get_decision(ImpactLevel.CRITICAL, UncertaintyLevel.CRITICAL)
        assert risk.decision_type == DecisionType.ESCALATE


class TestRiskMatrixBoundaryConditions:
    """Test boundary conditions and edge cases."""
    
    def test_medium_low_combination(self):
        """Medium impact + Low uncertainty."""
        risk = RiskMatrix.get_decision(ImpactLevel.MEDIUM, UncertaintyLevel.LOW)
        assert risk is not None
        assert risk.decision_type is not None
    
    def test_critical_low_combination(self):
        """Critical impact + Low uncertainty."""
        risk = RiskMatrix.get_decision(ImpactLevel.CRITICAL, UncertaintyLevel.LOW)
        assert risk is not None
        assert risk.decision_type is not None
    
    def test_all_combinations_are_valid(self):
        """All 16 combinations should return a valid RiskArbitration."""
        impact_levels = [ImpactLevel.LOW, ImpactLevel.MEDIUM, ImpactLevel.HIGH, ImpactLevel.CRITICAL]
        uncertainty_levels = [UncertaintyLevel.LOW, UncertaintyLevel.MEDIUM, UncertaintyLevel.HIGH, UncertaintyLevel.CRITICAL]
        
        for impact in impact_levels:
            for uncertainty in uncertainty_levels:
                risk = RiskMatrix.get_decision(impact, uncertainty)
                assert risk is not None, f"No decision for {impact}/{uncertainty}"
                assert hasattr(risk, 'decision_type'), f"Missing decision_type for {impact}/{uncertainty}"
                assert risk.decision_type in DecisionType, f"Invalid decision_type for {impact}/{uncertainty}"
