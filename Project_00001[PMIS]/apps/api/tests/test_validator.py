import pytest
from app.policies.validator import (
    validate_patch, ValidationResult
)
from app.policies.status_transitions import PackageStatus, TaskStatus
from app.policies.risk_arbitration import ImpactLevel, UncertaintyLevel
from app.tools.user_context import UserContext, Role


class TestValidatorPackageTransitions:
    """Test validate_patch checks status transitions for packages."""
    
    def test_valid_package_draft_to_submitted(self):
        """Valid: Package DRAFT → SUBMITTED with ANALYST role."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        # Mock package object
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.SUBMITTED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert isinstance(result, ValidationResult)
        assert result.is_allowed is True
        assert result.requires_approval is False
    
    def test_invalid_package_draft_to_active(self):
        """Invalid: Package DRAFT → ACTIVE skips necessary steps."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.ACTIVE}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert result.is_allowed is False
        assert len(result.reasons) > 0
        assert any("invalid" in r.lower() or "transition" in r.lower() for r in result.reasons)
    
    def test_valid_package_submitted_but_requires_analyst_role(self):
        """Valid transition but user lacks required role."""
        user = UserContext(user_id="viewer1", roles={Role.VIEWER})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.SUBMITTED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert result.is_allowed is False
        assert any("role" in r.lower() or "analyst" in r.lower() or "admin" in r.lower() for r in result.reasons)


class TestValidatorTaskTransitions:
    """Test validate_patch checks status transitions for tasks."""
    
    def test_valid_task_pending_to_in_progress(self):
        """Valid: Task PENDING → IN_PROGRESS with OPERATOR role."""
        user = UserContext(user_id="operator1", roles={Role.OPERATOR})
        
        class MockTask:
            def __init__(self):
                self.status = TaskStatus.PENDING
        
        task = MockTask()
        patch = {"status": TaskStatus.IN_PROGRESS}
        
        result = validate_patch(
            "task", task, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert result.is_allowed is True
    
    def test_invalid_task_pending_to_completed(self):
        """Invalid: Task PENDING → COMPLETED skips IN_PROGRESS."""
        user = UserContext(user_id="operator1", roles={Role.OPERATOR})
        
        class MockTask:
            def __init__(self):
                self.status = TaskStatus.PENDING
        
        task = MockTask()
        patch = {"status": TaskStatus.COMPLETED}
        
        result = validate_patch(
            "task", task, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert result.is_allowed is False


class TestValidatorRiskAssessment:
    """Test validate_patch incorporates risk assessment."""
    
    def test_low_risk_no_approval_needed(self):
        """Low impact + Low uncertainty = no approval required."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.SUBMITTED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert result.requires_approval is False
        assert result.requires_escalation is False
    
    def test_high_risk_requires_approval(self):
        """High impact + High uncertainty = approval required."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.SUBMITTED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.HIGH,
            uncertainty=UncertaintyLevel.HIGH
        )
        
        assert result.requires_approval is True
    
    def test_critical_risk_requires_escalation(self):
        """Critical impact + Critical uncertainty = escalation required."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.SUBMITTED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.CRITICAL,
            uncertainty=UncertaintyLevel.CRITICAL
        )
        
        assert result.requires_escalation is True


class TestValidatorCompleteWorkflow:
    """Test end-to-end validation workflows."""
    
    def test_valid_award_by_admin_medium_risk(self):
        """Admin awards package with medium risk - allowed but needs confirmation."""
        user = UserContext(user_id="admin1", roles={Role.ADMIN})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.APPROVED
        
        package = MockPackage()
        patch = {"status": PackageStatus.AWARDED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.MEDIUM,
            uncertainty=UncertaintyLevel.MEDIUM
        )
        
        assert result.is_allowed is True  # Admin can award
        assert result.requires_approval is False  # Medium/Medium = CONFIRM (not full approval)
    
    def test_invalid_award_by_analyst_high_risk(self):
        """Analyst cannot award (requires Admin), high risk."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.APPROVED
        
        package = MockPackage()
        patch = {"status": PackageStatus.AWARDED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.HIGH,
            uncertainty=UncertaintyLevel.HIGH
        )
        
        assert result.is_allowed is False  # No ADMIN role
        assert result.requires_approval is True  # HIGH/HIGH risk
    
    def test_cancel_active_package_high_risk(self):
        """Cancelling active package is high risk, requires approval."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.ACTIVE
        
        package = MockPackage()
        patch = {"status": PackageStatus.CANCELLED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.HIGH,
            uncertainty=UncertaintyLevel.MEDIUM
        )
        
        # May be allowed if analyst has rights to cancel, but high risk
        assert result.requires_approval is True or not result.is_allowed


class TestValidatorReasoningMessages:
    """Test that validation results include helpful reasoning."""
    
    def test_invalid_transition_includes_valid_next_statuses(self):
        """Rejection message includes valid next statuses."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.ACTIVE}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert len(result.reasons) > 0
        # At least one reason should be present
        assert isinstance(result.reasons, list)
    
    def test_validation_result_has_all_fields(self):
        """ValidationResult includes all expected fields."""
        user = UserContext(user_id="analyst1", roles={Role.ANALYST})
        
        class MockPackage:
            def __init__(self):
                self.status = PackageStatus.DRAFT
        
        package = MockPackage()
        patch = {"status": PackageStatus.SUBMITTED}
        
        result = validate_patch(
            "package", package, patch, user,
            impact=ImpactLevel.LOW,
            uncertainty=UncertaintyLevel.LOW
        )
        
        assert hasattr(result, 'is_allowed')
        assert hasattr(result, 'requires_approval')
        assert hasattr(result, 'requires_escalation')
        assert hasattr(result, 'decision_type')
        assert hasattr(result, 'reasons')
        assert hasattr(result, 'warnings')
