import pytest
from app.policies.status_transitions import (
    PackageStatus, TaskStatus, PackageTransitions, TaskTransitions
)


class TestPackageStatusTransitions:
    """Test package status transition rules."""
    
    def test_valid_transition_draft_to_submitted(self):
        """Valid: Draft → Submitted."""
        assert PackageTransitions.is_valid(PackageStatus.DRAFT, PackageStatus.SUBMITTED)
    
    def test_valid_transition_submitted_to_in_review(self):
        """Valid: Submitted → In Review."""
        assert PackageTransitions.is_valid(PackageStatus.SUBMITTED, PackageStatus.IN_REVIEW)
    
    def test_valid_transition_in_review_to_approved(self):
        """Valid: In Review → Approved."""
        assert PackageTransitions.is_valid(PackageStatus.IN_REVIEW, PackageStatus.APPROVED)
    
    def test_valid_transition_approved_to_awarded(self):
        """Valid: Approved → Awarded."""
        assert PackageTransitions.is_valid(PackageStatus.APPROVED, PackageStatus.AWARDED)
    
    def test_valid_transition_awarded_to_active(self):
        """Valid: Awarded → Active."""
        assert PackageTransitions.is_valid(PackageStatus.AWARDED, PackageStatus.ACTIVE)
    
    def test_valid_transition_active_to_completed(self):
        """Valid: Active → Completed."""
        assert PackageTransitions.is_valid(PackageStatus.ACTIVE, PackageStatus.COMPLETED)
    
    def test_valid_transition_active_to_on_hold(self):
        """Valid: Active → On Hold."""
        assert PackageTransitions.is_valid(PackageStatus.ACTIVE, PackageStatus.ON_HOLD)
    
    def test_valid_transition_on_hold_to_active(self):
        """Valid: On Hold → Active (resume)."""
        assert PackageTransitions.is_valid(PackageStatus.ON_HOLD, PackageStatus.ACTIVE)
    
    def test_valid_transition_in_review_back_to_submitted(self):
        """Valid: In Review → Submitted (request revisions)."""
        assert PackageTransitions.is_valid(PackageStatus.IN_REVIEW, PackageStatus.SUBMITTED)
    
    def test_invalid_transition_draft_to_active(self):
        """Invalid: Cannot skip to Active from Draft."""
        assert not PackageTransitions.is_valid(PackageStatus.DRAFT, PackageStatus.ACTIVE)
    
    def test_invalid_transition_completed_to_active(self):
        """Invalid: Cannot resume from Completed."""
        assert not PackageTransitions.is_valid(PackageStatus.COMPLETED, PackageStatus.ACTIVE)
    
    def test_invalid_transition_drafted_to_awarded(self):
        """Invalid: Cannot jump from Draft to Awarded."""
        assert not PackageTransitions.is_valid(PackageStatus.DRAFT, PackageStatus.AWARDED)
    
    def test_get_valid_next_statuses(self):
        """Get all valid next statuses from current status."""
        valid_next = PackageTransitions.get_valid_next_statuses(PackageStatus.DRAFT)
        assert PackageStatus.SUBMITTED in valid_next
        assert PackageStatus.ACTIVE not in valid_next
    
    def test_transition_requires_approval_award(self):
        """Award transition requires approval."""
        rule = PackageTransitions.get_rule(PackageStatus.APPROVED, PackageStatus.AWARDED)
        assert rule is not None
        assert rule.requires_approval is True
    
    def test_transition_risk_level_high_for_cancel_active(self):
        """Cancelling active package is high risk."""
        rule = PackageTransitions.get_rule(PackageStatus.ACTIVE, PackageStatus.CANCELLED)
        assert rule is not None
        assert rule.risk_level == "high"


class TestTaskStatusTransitions:
    """Test task status transition rules."""
    
    def test_valid_transition_pending_to_in_progress(self):
        """Valid: Pending → In Progress."""
        assert TaskTransitions.is_valid(TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
    
    def test_valid_transition_in_progress_to_completed(self):
        """Valid: In Progress → Completed."""
        assert TaskTransitions.is_valid(TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED)
    
    def test_valid_transition_in_progress_to_blocked(self):
        """Valid: In Progress → Blocked."""
        assert TaskTransitions.is_valid(TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)
    
    def test_valid_transition_blocked_to_in_progress(self):
        """Valid: Blocked → In Progress (unblock)."""
        assert TaskTransitions.is_valid(TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS)
    
    def test_valid_transition_in_progress_to_review_needed(self):
        """Valid: In Progress → Review Needed."""
        assert TaskTransitions.is_valid(TaskStatus.IN_PROGRESS, TaskStatus.REVIEW_NEEDED)
    
    def test_valid_transition_review_needed_to_completed(self):
        """Valid: Review Needed → Completed."""
        assert TaskTransitions.is_valid(TaskStatus.REVIEW_NEEDED, TaskStatus.COMPLETED)
    
    def test_valid_transition_review_needed_back_to_in_progress(self):
        """Valid: Review Needed → In Progress (revisions needed)."""
        assert TaskTransitions.is_valid(TaskStatus.REVIEW_NEEDED, TaskStatus.IN_PROGRESS)
    
    def test_invalid_transition_pending_to_completed(self):
        """Invalid: Cannot skip directly from Pending to Completed."""
        assert not TaskTransitions.is_valid(TaskStatus.PENDING, TaskStatus.COMPLETED)
    
    def test_invalid_transition_completed_to_in_progress(self):
        """Invalid: Cannot reopen completed task."""
        assert not TaskTransitions.is_valid(TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS)
    
    def test_valid_transition_pending_to_cancelled(self):
        """Valid: Pending → Cancelled (cancel before start)."""
        assert TaskTransitions.is_valid(TaskStatus.PENDING, TaskStatus.CANCELLED)
    
    def test_valid_transition_in_progress_to_cancelled(self):
        """Valid: In Progress → Cancelled."""
        assert TaskTransitions.is_valid(TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED)
    
    def test_get_valid_next_statuses_pending(self):
        """Get valid next statuses from Pending."""
        valid_next = TaskTransitions.get_valid_next_statuses(TaskStatus.PENDING)
        assert TaskStatus.IN_PROGRESS in valid_next
        assert TaskStatus.CANCELLED in valid_next
        assert TaskStatus.BLOCKED not in valid_next
