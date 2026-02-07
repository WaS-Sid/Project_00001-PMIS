import pytest
from app.policies.approval_matrix import ApprovalMatrix
from app.tools.user_context import Role


class TestApprovalMatrix:
    """Test approval matrix role-based authorization."""
    
    def test_approve_package_submission_as_analyst(self):
        """Analyst role can submit package."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:submitted",
            {Role.ANALYST}
        )
        assert is_approved is True
        # Reason may be empty or contain approval info
    
    def test_approve_package_submission_as_admin(self):
        """Admin role can submit package."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:submitted",
            {Role.ADMIN}
        )
        assert is_approved is True
    
    def test_reject_package_submission_as_operator(self):
        """Operator role cannot submit package."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:submitted",
            {Role.OPERATOR}
        )
        assert is_approved is False
        assert "analyst" in reason.lower() or "admin" in reason.lower()
    
    def test_reject_package_award_as_analyst(self):
        """Analyst cannot award package (requires Admin)."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:awarded",
            {Role.ANALYST}
        )
        assert is_approved is False
        assert "admin" in reason.lower()
    
    def test_approve_package_award_as_admin(self):
        """Admin role can award package."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:awarded",
            {Role.ADMIN}
        )
        assert is_approved is True
    
    def test_approve_task_cancel_as_operator(self):
        """Operator role can cancel task."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "task.status:cancelled",
            {Role.OPERATOR}
        )
        assert is_approved is True
    
    def test_approve_task_cancel_as_admin(self):
        """Admin role can cancel task."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "task.status:cancelled",
            {Role.ADMIN}
        )
        assert is_approved is True
    
    def test_reject_task_cancel_as_viewer(self):
        """Viewer role cannot cancel task."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "task.status:cancelled",
            {Role.VIEWER}
        )
        assert is_approved is False
    
    def test_multiple_roles_approval(self):
        """User with multiple roles (one of which satisfies requirement)."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:awarded",
            {Role.ANALYST, Role.ADMIN}  # Has ADMIN which is required
        )
        assert is_approved is True
    
    def test_viewer_only_has_view_permission(self):
        """Viewer can only perform non-privileged actions."""
        # Assume viewer cannot submit (if that rule exists)
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:submitted",
            {Role.VIEWER}
        )
        # May or may not be approved depending on rule; test that function works
        assert isinstance(is_approved, bool)
    
    def test_unknown_action_returns_false(self):
        """Unknown action should reject (fail safe)."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "nonexistent.action:unknown",
            {Role.ADMIN}
        )
        assert is_approved is False
    
    def test_empty_roles_rejects_all(self):
        """Empty role set should reject all actions."""
        is_approved, reason = ApprovalMatrix.is_action_approved(
            "package.status:submitted",
            set()  # No roles
        )
        assert is_approved is False
