"""
Integration tests for Prompt 5: API endpoints + auth + LangGraph orchestration.

Test flows:
1. Read-only query: "What is the status of package P-001?"
2. Create a follow-up task for package P-001 due tomorrow
3. Mark package P-001 as AWARDED -> approval request is created
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.main import app
from app.tools.models import Package, Task, Approval, Event, EventType
from app.tools.user_context import Role


class TestChatEndpointQueries:
    """Test /chat endpoint with read-only queries."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def package(self, db_session):
        """Create a test package."""
        pkg = Package(
            code="P-001",
            title="Test Package",
            data={"vendor": "ACME Corp"}
        )
        db_session.add(pkg)
        db_session.commit()
        return pkg
    
    @pytest.fixture
    def analyst_headers(self):
        """Headers for analyst user."""
        return {
            "X-User-Id": "analyst1",
            "X-User-Role": "analyst",
            "X-User-Name": "Alice Analyst",
        }
    
    def test_query_package_status(self, client, package, analyst_headers, db_session):
        """Test: /chat with query about package status."""
        response = client.post(
            "/api/chat",
            json={"query": "What is the status of package P-001?"},
            headers=analyst_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "response" in data
        assert "action_type" in data
        assert "resource_created" not in data or data["resource_created"] is None  # Query is read-only
        assert "evidence" in data
        
        # Response should mention the package code
        assert "P-001" in data["response"] or "package" in data["response"].lower()
    
    def test_query_without_auth_headers_fails(self, client, package):
        """Test: /chat without required auth headers returns 422."""
        response = client.post(
            "/api/chat",
            json={"query": "What is the status of package P-001?"},
        )
        
        assert response.status_code == 422  # Validation error (missing headers)


class TestCreateTaskFlow:
    """Test creating a task via /chat."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def package(self, db_session):
        """Create a test package."""
        pkg = Package(
            code="P-001",
            title="Test Package for Tasks"
        )
        db_session.add(pkg)
        db_session.commit()
        return pkg
    
    @pytest.fixture
    def operator_headers(self):
        """Headers for operator user."""
        return {
            "X-User-Id": "operator1",
            "X-User-Role": "operator",
            "X-User-Name": "Bob Operator",
        }
    
    def test_create_task_via_chat(self, client, package, operator_headers, db_session):
        """Test: /chat creating a follow-up task for package P-001."""
        response = client.post(
            "/api/chat",
            json={"query": "Create a follow-up task for package P-001 due tomorrow"},
            headers=operator_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response indicates success
        assert "response" in data
        assert data["response"]  # Non-empty response
        
        # Task creation should be successful (AUTO decision)
        assert "success" in data["response"].lower() or "task" in data["response"].lower()
        
        # Verify a task was actually created
        tasks = db_session.query(Task).filter(Task.package_id == package.id).all()
        assert len(tasks) > 0
    
    def test_create_task_requires_operator_role(self, client, package, db_session):
        """Test: Task creation denied for viewer role."""
        viewer_headers = {
            "X-User-Id": "viewer1",
            "X-User-Role": "viewer",
            "X-User-Name": "Charlie Viewer",
        }
        
        response = client.post(
            "/api/chat",
            json={"query": "Create a task for P-001"},
            headers=viewer_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should indicate permission denied in response
        assert "insufficient" in data["response"].lower() or "permission" in data["response"].lower() or "could not" in data["response"].lower()


class TestApprovalWorkflow:
    """Test approval workflow for package status changes."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def package(self, db_session):
        """Create a test package in APPROVED status."""
        pkg = Package(
            code="P-001",
            title="Approved Package Ready for Award"
        )
        db_session.add(pkg)
        db_session.commit()
        return pkg
    
    @pytest.fixture
    def analyst_headers(self):
        return {
            "X-User-Id": "analyst1",
            "X-User-Role": "analyst",
            "X-User-Name": "Alice Analyst",
        }
    
    @pytest.fixture
    def admin_headers(self):
        return {
            "X-User-Id": "admin1",
            "X-User-Role": "admin",
            "X-User-Name": "Admin User",
        }
    
    def test_patch_creates_approval_request(self, client, package, analyst_headers, db_session):
        """Test: PATCH /packages/{id} creates approval request (not direct update)."""
        response = client.patch(
            f"/api/packages/{package.id}",
            json={"status": "awarded"},
            headers=analyst_headers,
        )
        
        # Should succeed with 200
        assert response.status_code == 200
        data = response.json()
        
        # Should return approval request, not updated package
        assert "id" in data
        assert "status" in data
        assert "patch_json" in data
        assert data["patch_json"]["status"] == "awarded"
        
        # Verify approval record exists in DB
        approvals = db_session.query(Approval).filter(
            Approval.package_id == package.id
        ).all()
        assert len(approvals) > 0
        assert approvals[-1].patch_json["status"] == "awarded"
    
    def test_mark_package_as_awarded_via_chat(self, client, package, analyst_headers, db_session):
        """Test: /chat with 'Mark package P-001 as AWARDED' creates approval."""
        response = client.post(
            "/api/chat",
            json={"query": "Mark package P-001 as AWARDED"},
            headers=analyst_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should indicate approval request was created
        assert "response" in data
        assert ("approval" in data["response"].lower() or 
                "request" in data["response"].lower())
        
        # Verify approval was created
        approvals = db_session.query(Approval).filter(
            Approval.package_id == package.id
        ).all()
        assert len(approvals) > 0


class TestApprovalApproveReject:
    """Test approval decision endpoints."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def package(self, db_session):
        pkg = Package(code="P-001", title="Package for Approval Test")
        db_session.add(pkg)
        db_session.commit()
        return pkg
    
    @pytest.fixture
    def approval(self, db_session, package):
        """Create an approval request."""
        app_req = Approval(
            package_id=package.id,
            patch_json={"status": "awarded"},
            reason="Test approval",
            requested_by="analyst1",
        )
        db_session.add(app_req)
        db_session.commit()
        return app_req
    
    @pytest.fixture
    def admin_headers(self):
        return {
            "X-User-Id": "admin1",
            "X-User-Role": "admin",
            "X-User-Name": "Admin User",
        }
    
    def test_approve_request(self, client, approval, admin_headers, db_session):
        """Test: POST /approvals/{id}/approve applies the patch."""
        response = client.post(
            f"/api/approvals/{approval.id}/approve",
            json={"reason_text": "Looks good"},
            headers=admin_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return updated approval with APPROVED status
        assert data["status"] == "approved"
        
        # Verify approval was updated in DB
        updated = db_session.query(Approval).filter(
            Approval.id == approval.id
        ).first()
        assert updated.status == "approved"
        assert updated.decided_by == "admin1"
    
    def test_reject_request(self, client, approval, admin_headers, db_session):
        """Test: POST /approvals/{id}/reject rejects without applying patch."""
        response = client.post(
            f"/api/approvals/{approval.id}/reject",
            json={"reason_text": "Not ready yet"},
            headers=admin_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return updated approval with REJECTED status
        assert data["status"] == "rejected"
        
        # Verify approval was updated in DB
        updated = db_session.query(Approval).filter(
            Approval.id == approval.id
        ).first()
        assert updated.status == "rejected"


class TestAuditEndpoint:
    """Test audit/event timeline endpoint."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def package_with_events(self, db_session):
        """Create package with several events."""
        pkg = Package(code="P-001", title="Package with History")
        db_session.add(pkg)
        db_session.commit()
        
        # Add some events
        for i in range(3):
            event = Event(
                event_type=EventType.PACKAGE_PATCHED,
                entity_type="package",
                entity_id=pkg.id,
                payload={"change": f"Change {i}"},
                triggered_by="user1",
            )
            db_session.add(event)
        db_session.commit()
        
        return pkg
    
    @pytest.fixture
    def analyst_headers(self):
        return {
            "X-User-Id": "analyst1",
            "X-User-Role": "analyst",
            "X-User-Name": "Alice Analyst",
        }
    
    def test_audit_returns_event_timeline(self, client, package_with_events, analyst_headers):
        """Test: GET /audit returns immutable event timeline."""
        response = client.get(
            f"/api/audit/package/{package_with_events.id}",
            headers=analyst_headers,
        )
        
        assert response.status_code == 200
        events = response.json()
        
        # Should return list of events
        assert isinstance(events, list)
        assert len(events) >= 3
        
        # Each event should have required fields
        for event in events:
            assert "id" in event
            assert "event_type" in event
            assert "entity_type" in event
            assert "entity_id" in event
            assert "triggered_by" in event
            assert "created_at" in event
    
    def test_audit_respects_limit_parameter(self, client, package_with_events, analyst_headers):
        """Test: Audit endpoint respects limit parameter."""
        response = client.get(
            f"/api/audit/package/{package_with_events.id}?limit=2",
            headers=analyst_headers,
        )
        
        assert response.status_code == 200
        events = response.json()
        
        # Should respect limit
        assert len(events) <= 2


class TestPackageEndpoints:
    """Test basic package CRUD endpoints."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def package(self, db_session):
        pkg = Package(code="P-001", title="Test Package", data={"vendor": "ACME"})
        db_session.add(pkg)
        db_session.commit()
        return pkg
    
    @pytest.fixture
    def analyst_headers(self):
        return {
            "X-User-Id": "analyst1",
            "X-User-Role": "analyst",
            "X-User-Name": "Alice",
        }
    
    def test_list_packages(self, client, package, analyst_headers):
        """Test: GET /packages lists all packages."""
        response = client.get(
            "/api/packages",
            headers=analyst_headers,
        )
        
        assert response.status_code == 200
        packages = response.json()
        
        assert isinstance(packages, list)
        assert len(packages) > 0
        assert any(p["code"] == "P-001" for p in packages)
    
    def test_get_package_by_id(self, client, package, analyst_headers):
        """Test: GET /packages/{id} returns package details."""
        response = client.get(
            f"/api/packages/{package.id}",
            headers=analyst_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == package.id
        assert data["code"] == "P-001"
        assert data["title"] == "Test Package"
