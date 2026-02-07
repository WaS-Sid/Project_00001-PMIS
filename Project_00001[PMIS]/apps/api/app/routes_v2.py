"""
FastAPI endpoints for PMIS agent.

Endpoints:
- POST /chat: Run the orchestration graph
- GET /packages, GET /packages/{id}, PATCH /packages/{id}
- GET /approvals, POST /approvals/{id}/approve, POST /approvals/{id}/reject
- GET /audit/{entity_type}/{entity_id}
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.tools.user_context import UserContext, Role
from app.tools.read_tools import get_package, get_package_by_code, get_audit_timeline
from app.tools.write_tools import propose_package_patch, approve_proposal
from app.tools.models import Package, Approval, Event, ApprovalStatus
from app.graph import create_runnable_graph


# ============== Request / Response Models ==============

class ChatRequest(BaseModel):
    """User chat input."""
    query: str
    impact_level: Optional[str] = "medium"  # ImpactLevel
    uncertainty_level: Optional[str] = "medium"  # UncertaintyLevel


class ChatResponse(BaseModel):
    """Chat response from orchestration."""
    response: str
    action_type: str
    resource_created: Optional[dict] = None  # {type, id}
    evidence: list[dict] = []


class PackageResponse(BaseModel):
    """Package data."""
    id: str
    code: str
    title: str
    data: Optional[dict] = None


class ApprovalRequest(BaseModel):
    """Approval decision."""
    approved: bool
    decision_reason: str


class ApprovalResponse(BaseModel):
    """Approval workflow item."""
    id: str
    package_id: str
    patch_json: dict
    status: str
    requested_by: str
    created_at: str


# ============== Auth Helper ==============

def get_user_from_headers(
    x_user_id: str = Header(...),
    x_user_role: str = Header(...),
    x_user_name: str = Header(default="Unknown"),
) -> UserContext:
    """Extract user context from request headers."""
    # Parse roles (comma-separated)
    roles = {Role(r.strip().lower()) for r in x_user_role.split(",")}
    return UserContext(user_id=x_user_id, name=x_user_name, roles=roles)


# ============== Routes ==============

router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Run the orchestration graph with user query.
    
    Headers required:
    - X-User-Id: User ID
    - X-User-Role: Comma-separated roles (admin, analyst, operator, viewer)
    - X-User-Name: User display name (optional)
    
    Example:
    ```
    POST /api/chat
    X-User-Id: analyst1
    X-User-Role: analyst
    X-User-Name: Alice
    
    {"query": "What is the status of package P-001?"}
    ```
    """
    try:
        # Build and run the graph
        graph = create_runnable_graph()

        result = graph.invoke({
            "user_query": request.query,
            "user": user,
            "db": db,
        })

        # Normalize result (graph may return a dict-like state)
        response_text = None
        action_type = "query"
        resource_created = None
        evidence = []

        if isinstance(result, dict):
            response_text = result.get("response") or "No response generated"
            intake = result.get("intake")
            if intake:
                action_type = getattr(intake, "action_type", str(intake.action_type) if hasattr(intake, "action_type") else "query")
            execute = result.get("execute")
            if execute:
                # support object or dict
                resource_type = getattr(execute, "resource_type", execute.get("resource_type") if isinstance(execute, dict) else None)
                resource_id = getattr(execute, "resource_id", execute.get("resource_id") if isinstance(execute, dict) else None)
                if resource_id:
                    resource_created = {"type": resource_type, "id": resource_id}
            evidence = result.get("response_evidence", [])
        else:
            response_text = str(result)
        
        return ChatResponse(
            response=response_text,
            action_type=str(action_type),
            resource_created=resource_created,
            evidence=evidence,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")


# ============== Package Endpoints ==============

@router.get("/packages")
async def list_packages(
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> list[PackageResponse]:
    """List all packages (read-only)."""
    try:
        # Check read permission
        if not user.has_any_role(Role.ANALYST, Role.OPERATOR, Role.VIEWER, Role.ADMIN):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        packages = db.query(Package).all()
        return [
            PackageResponse(
                id=p.id,
                code=p.code,
                title=p.title,
                data=p.data,
            )
            for p in packages
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/packages/{package_id}")
async def get_package_detail(
    package_id: str,
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> PackageResponse:
    """Get package details by ID."""
    try:
        pkg = get_package(db, package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail="Package not found")
        
        return PackageResponse(
            id=pkg.id,
            code=pkg.code,
            title=pkg.title,
            data=pkg.data,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/packages/{package_id}")
async def update_package(
    package_id: str,
    patch: dict,
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """
    Propose a package patch (creates approval request, not direct update).
    
    Write operations always create an approval workflow.
    The patch is not applied until approved.
    
    Example:
    ```
    PATCH /api/packages/pkg-123
    {"status": "awarded"}
    ```
    """
    try:
        # Load package
        pkg = get_package(db, package_id)
        if not pkg:
            raise HTTPException(status_code=404, detail="Package not found")
        
        # Only certain roles may propose patches
        if not user.has_any_role(Role.ANALYST, Role.OPERATOR, Role.ADMIN):
            raise HTTPException(status_code=403, detail="Insufficient permissions to propose changes")

        # Create approval request (not direct update)
        approval_res = propose_package_patch(
            db,
            package_id=package_id,
            patch_json=patch,
            reason=f"Via PATCH endpoint",
            requested_by=user.user_id,
            user=user,
        )

        # approval_res may be a dict; load approval row for full info
        approval_obj = db.query(Approval).filter(Approval.id == approval_res.get("approval_id") or approval_res.get("approval_id")).first()
        if not approval_obj:
            # if tools returned limited info, construct minimal response
            return ApprovalResponse(
                id=approval_res.get("approval_id"),
                package_id=package_id,
                patch_json=patch,
                status=approval_res.get("status") or str(ApprovalStatus.PENDING.value),
                requested_by=user.user_id,
                created_at=approval_res.get("created_at"),
            )

        return ApprovalResponse(
            id=approval_obj.id,
            package_id=approval_obj.package_id,
            patch_json=approval_obj.patch_json,
            status=approval_obj.status.value if hasattr(approval_obj.status, 'value') else str(approval_obj.status),
            requested_by=approval_obj.requested_by,
            created_at=approval_obj.created_at.isoformat() if approval_obj.created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create approval request: {str(e)}")


# ============== Approval Endpoints ==============

@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = None,
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> list[ApprovalResponse]:
    """List approval requests."""
    try:
        query = db.query(Approval)
        if status:
            query = query.filter(Approval.status == status)
        
        approvals = query.all()
        return [
            ApprovalResponse(
                id=a.id,
                package_id=a.package_id,
                patch_json=a.patch_json,
                status=a.status,
                requested_by=a.requested_by,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
            for a in approvals
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    reason_text: str = "",
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Approve a patch request (applies the patch)."""
    try:
        # Load approval
        approval = db.query(Approval).filter(Approval.id == approval_id).first()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        # Only admins may approve
        if not user.has_any_role(Role.ADMIN):
            raise HTTPException(status_code=403, detail="Only admins may approve requests")

        # Call approve_proposal (applies patch + creates event)
        idempotency_key = f"api-approve-{approval_id}-{datetime.now().timestamp()}"
        try:
            approve_result = approve_proposal(
                db,
                approval_id=approval_id,
                decided_by=user.user_id,
                decision="approved",
                reason=reason_text or "Approved via API",
                idempotency_key=idempotency_key,
                user=user,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to approve: {str(e)}")

        # Reload approval to get updated state
        approval = db.query(Approval).filter(Approval.id == approval_id).first()

        return ApprovalResponse(
            id=approval.id,
            package_id=approval.package_id,
            patch_json=approval.patch_json,
            status=approval.status.value if hasattr(approval.status, 'value') else str(approval.status),
            requested_by=approval.requested_by,
            created_at=approval.created_at.isoformat() if approval.created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to approve: {str(e)}")


@router.post("/approvals/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    reason_text: str = "",
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Reject a patch request (no change applied)."""
    try:
        # Load approval
        approval = db.query(Approval).filter(Approval.id == approval_id).first()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        # Only admins may reject
        if not user.has_any_role(Role.ADMIN):
            raise HTTPException(status_code=403, detail="Only admins may reject requests")

        idempotency_key = f"api-reject-{approval_id}-{datetime.now().timestamp()}"
        try:
            approve_result = approve_proposal(
                db,
                approval_id=approval_id,
                decided_by=user.user_id,
                decision="rejected",
                reason=reason_text or "Rejected via API",
                idempotency_key=idempotency_key,
                user=user,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to reject: {str(e)}")

        # Reload approval to get updated state
        approval = db.query(Approval).filter(Approval.id == approval_id).first()

        return ApprovalResponse(
            id=approval.id,
            package_id=approval.package_id,
            patch_json=approval.patch_json,
            status=approval.status.value if hasattr(approval.status, 'value') else str(approval.status),
            requested_by=approval.requested_by,
            created_at=approval.created_at.isoformat() if approval.created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to reject: {str(e)}")


# ============== Audit Endpoints ==============

@router.get("/audit/{entity_type}/{entity_id}")
async def get_audit_log(
    entity_type: str,
    entity_id: str,
    limit: int = 50,
    user: UserContext = Depends(get_user_from_headers),
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Get audit/event timeline for an entity.
    
    Returns immutable event log showing all state changes.
    
    Example:
    ```
    GET /api/audit/package/pkg-123?limit=20
    ```
    """
    try:
        timeline = get_audit_timeline(db, entity_type, entity_id, limit=limit)
        # get_audit_timeline already returns list[dict]
        return timeline
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
