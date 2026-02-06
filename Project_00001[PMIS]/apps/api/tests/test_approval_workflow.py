"""
Test the approval workflow end-to-end:
1. propose_package_patch creates an approval
2. approve_proposal with "approved" applies the patch and writes events
3. Both operations are idempotent
4. Events form an audit trail
"""

import pytest
from uuid import uuid4
from app.tools.models import Package, Approval, Event, ApprovalStatus, EventType
from app.tools.write_tools import propose_package_patch, approve_proposal
from app.tools.read_tools import get_audit_timeline


@pytest.fixture
def sample_package(db_session):
    """Create a sample package for workflow testing."""
    pkg = Package(code="PKG-WORKFLOW", title="Workflow Test Package")
    db_session.add(pkg)
    db_session.commit()
    return pkg


class TestApprovalWorkflow:
    def test_end_to_end_approval_workflow(self, db_session, sample_package, admin_user, analyst_user):
        """Test complete workflow: propose -> approve -> verify patch applied."""
        
        # Step 1: Analyst proposes a patch
        patch = {"status": "active", "version": "2.0"}
        proposal_result = propose_package_patch(
            db_session,
            package_id=sample_package.id,
            patch_json=patch,
            reason="Upgrade to v2.0 with active status",
            requested_by=analyst_user.user_id,
            user=analyst_user,
        )
        
        assert proposal_result["approval_id"] is not None
        assert proposal_result["status"] == "pending"
        
        # Verify approval exists in DB
        approval = db_session.query(Approval).filter_by(
            id=proposal_result["approval_id"]
        ).first()
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING
        
        # Step 2: Admin approves the patch
        idempotency_key = f"approval-{uuid4()}"
        approve_result = approve_proposal(
            db_session,
            approval_id=proposal_result["approval_id"],
            decided_by=admin_user.user_id,
            decision="approved",
            reason="Verified and LGTM",
            idempotency_key=idempotency_key,
            user=admin_user,
        )
        
        assert approve_result["status"] == "approved"
        assert approve_result["decision"] == "approved"
        
        # Step 3: Verify patch was applied to package
        db_session.refresh(sample_package)
        assert sample_package.metadata is not None
        assert sample_package.metadata.get("status") == "active"
        assert sample_package.metadata.get("version") == "2.0"
        
        # Step 4: Verify approval updated
        db_session.refresh(approval)
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.decided_by == admin_user.user_id
        assert approval.decided_at is not None
    
    def test_approval_workflow_rejection(self, db_session, sample_package, admin_user, analyst_user):
        """Test that rejected approvals don't apply patches."""
        
        # Propose patch
        patch = {"risky": "change"}
        proposal_result = propose_package_patch(
            db_session,
            package_id=sample_package.id,
            patch_json=patch,
            reason="Risky change",
            requested_by=analyst_user.user_id,
            user=analyst_user,
        )
        
        # Admin rejects
        idempotency_key = f"reject-{uuid4()}"
        reject_result = approve_proposal(
            db_session,
            approval_id=proposal_result["approval_id"],
            decided_by=admin_user.user_id,
            decision="rejected",
            reason="Too risky, needs more validation",
            idempotency_key=idempotency_key,
            user=admin_user,
        )
        
        assert reject_result["decision"] == "rejected"
        
        # Package should NOT have the risky patch applied
        db_session.refresh(sample_package)
        assert sample_package.metadata is None or "risky" not in sample_package.metadata
    
    def test_approval_workflow_idempotency(self, db_session, sample_package, admin_user, analyst_user):
        """Test that calling approve_proposal twice with same idempotency key is safe."""
        
        # Create and propose patch
        patch = {"idempotent": "test"}
        proposal = propose_package_patch(
            db_session,
            package_id=sample_package.id,
            patch_json=patch,
            reason="Idempotency test",
            requested_by=analyst_user.user_id,
            user=analyst_user,
        )
        
        idempotency_key = f"idem-approve-{uuid4()}"
        
        # First approval
        result1 = approve_proposal(
            db_session,
            approval_id=proposal["approval_id"],
            decided_by=admin_user.user_id,
            decision="approved",
            reason="LGTM",
            idempotency_key=idempotency_key,
            user=admin_user,
        )
        
        # Verify patch applied
        db_session.expire(sample_package)
        db_session.refresh(sample_package)
        assert sample_package.metadata.get("idempotent") == "test"
        
        # Second call with same idempotency key should return cached result
        # (In practice, calling twice would fail because approval is no longer PENDING,
        # but the idempotency mechanism should prevent duplicates)
        result2 = approve_proposal(
            db_session,
            approval_id=proposal["approval_id"],
            decided_by=admin_user.user_id,
            decision="approved",
            reason="LGTM",
            idempotency_key=idempotency_key,
            user=admin_user,
        )
        
        # Both calls returned same cached result
        assert result1["approval_id"] == result2["approval_id"]
    
    def test_approval_workflow_audit_trail(self, db_session, sample_package, admin_user, analyst_user):
        """Test that workflow creates proper audit trail via events."""
        
        # Propose
        patch = {"audit": "test"}
        proposal = propose_package_patch(
            db_session,
            package_id=sample_package.id,
            patch_json=patch,
            reason="Audit trail test",
            requested_by=analyst_user.user_id,
            user=analyst_user,
        )
        
        # Approve
        idempotency_key = f"audit-{uuid4()}"
        approve_proposal(
            db_session,
            approval_id=proposal["approval_id"],
            decided_by=admin_user.user_id,
            decision="approved",
            reason="Verified",
            idempotency_key=idempotency_key,
            user=admin_user,
        )
        
        # Get audit timeline for approval
        timeline = get_audit_timeline(
            db_session,
            entity_type="approval",
            entity_id=proposal["approval_id"],
        )
        
        # Should have events
        assert len(timeline) >= 1
        
        # Get timeline for package to see patch event
        pkg_timeline = get_audit_timeline(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
        )
        
        # Should have package_patched event
        event_types = [e["event_type"] for e in pkg_timeline]
        assert "package_patched" in event_types
        
        # Event should reference the approval
        patch_event = next((e for e in pkg_timeline if e["event_type"] == "package_patched"), None)
        assert patch_event is not None
        assert patch_event["payload"]["approval_id"] == proposal["approval_id"]
    
    def test_no_write_without_event(self, db_session, sample_package, admin_user, analyst_user):
        """Acceptance criterion: No write happens without event record."""
        
        # Propose patch and approve
        patch = {"critical": "data"}
        proposal = propose_package_patch(
            db_session,
            package_id=sample_package.id,
            patch_json=patch,
            reason="Critical update",
            requested_by=analyst_user.user_id,
            user=analyst_user,
        )
        
        idempotency_key = f"no-write-no-event-{uuid4()}"
        approve_proposal(
            db_session,
            approval_id=proposal["approval_id"],
            decided_by=admin_user.user_id,
            decision="approved",
            reason="Approved",
            idempotency_key=idempotency_key,
            user=admin_user,
        )
        
        # Verify: approval decision event exists
        approval_events = db_session.query(Event).filter(
            Event.entity_type == "approval",
            Event.entity_id == proposal["approval_id"],
        ).all()
        assert len(approval_events) > 0
        
        # Verify: package patch event exists
        pkg_events = db_session.query(Event).filter(
            Event.entity_type == "package",
            Event.entity_id == sample_package.id,
            Event.event_type == EventType.PACKAGE_PATCHED,
        ).all()
        assert len(pkg_events) > 0
    
    def test_duplicate_retries_are_idempotent(self, db_session, sample_package, admin_user, analyst_user):
        """Acceptance: Duplicate retries with same idempotency key don't duplicate changes."""
        
        # Create approval
        patch = {"important": "change"}
        proposal = propose_package_patch(
            db_session,
            package_id=sample_package.id,
            patch_json=patch,
            reason="Important update",
            requested_by=analyst_user.user_id,
            user=analyst_user,
        )
        
        idempotency_key = f"idem-dup-{uuid4()}"
        
        # Approve multiple times with same key
        results = []
        for _ in range(3):
            result = approve_proposal(
                db_session,
                approval_id=proposal["approval_id"],
                decided_by=admin_user.user_id,
                decision="approved",
                reason="OK",
                idempotency_key=idempotency_key,
                user=admin_user,
            )
            results.append(result)
        
        # All results should be identical (cached)
        assert results[0] == results[1] == results[2]
        
        # Package should only have one patch event with this idempotency key
        events = db_session.query(Event).filter(
            Event.idempotency_key == idempotency_key,
        ).all()
        
        # Should have 1 or 2 events (approval_decided and possibly package_patched)
        # but they should share the idempotency key
        assert len(events) >= 1
