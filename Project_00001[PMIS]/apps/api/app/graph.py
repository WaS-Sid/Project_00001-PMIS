"""
LangGraph orchestration for package management agent.

Nodes:
- Intake: parse user request (query vs action)
- Retrieve: pull SoR snapshot + recent events + memory hits
- Plan: produce structured plan (read/answer, create task, propose patch)
- Validate: run deterministic policy checks on proposed writes
- Arbitration: decide AUTO vs APPROVAL_REQUIRED based on risk
- Execute: call tool adapters (create task or create approval request)
- Verify: re-read and confirm invariants
- MemoryUpdate: store summaries/decisions
- Respond: respond with evidence references
"""

from typing import TypedDict, Literal, Any
from enum import Enum
from dataclasses import dataclass, asdict
import json
from datetime import datetime

from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from app.tools.user_context import UserContext, Role
from app.tools.read_tools import (
    get_package, get_package_by_code, list_overdue_tasks, get_audit_timeline
)
from app.tools.write_tools import (
    append_event, create_task, propose_package_patch
)
from app.tools.memory_tools import store_memory, search_memory
from app.policies.status_transitions import PackageStatus
from app.policies.validator import validate_patch
from app.policies.risk_arbitration import ImpactLevel, UncertaintyLevel


class ActionType(str, Enum):
    """Types of actions the agent can take."""
    QUERY = "query"              # Read-only question
    CREATE_TASK = "create_task"  # Create a task
    PROPOSE_PATCH = "propose_patch"  # Propose status change


@dataclass
class IntakeResult:
    """Parsed user request."""
    action_type: ActionType
    package_code: str | None
    query: str
    proposed_change: dict | None  # e.g., {"status": "AWARDED"}
    metadata: dict | None


@dataclass
class RetrieveResult:
    """Retrieved context for decision."""
    package: dict | None
    recent_events: list[dict]
    memory_hits: list[dict]


@dataclass
class PlanResult:
    """Structured plan."""
    action_type: ActionType
    reasoning: str
    proposed_steps: list[str]


@dataclass
class ValidateResult:
    """Validation outcome."""
    is_valid: bool
    requires_approval: bool
    requires_escalation: bool
    reasons: list[str]
    warnings: list[str]


@dataclass
class ExecuteResult:
    """Execution outcome."""
    success: bool
    resource_id: str | None
    resource_type: str | None  # "task", "approval", etc.
    message: str


@dataclass
class GraphState(TypedDict, total=False):
    """State shape for the LangGraph."""
    # Input
    user_query: str
    user: UserContext
    db: Session
    
    # Processing results
    intake: IntakeResult
    retrieve: RetrieveResult
    plan: PlanResult
    validate: ValidateResult
    arbitration: dict  # {decision_type, risk_level, ...}
    execute: ExecuteResult
    verify: dict  # {is_valid, final_state, ...}
    memory_update: dict  # {stored_memories, ...}
    
    # Final response
    response: str
    response_evidence: list[dict]  # References to events, approvals, etc.


# ============== Node Functions ==============


def node_intake(state: GraphState) -> GraphState:
    """Parse user request into structured intent."""
    query = state["user_query"]
    
    # Simple heuristic parsing (in production, use LLM or NLU)
    action = ActionType.QUERY
    package_code = None
    proposed_change = None
    
    # Extract package code (e.g., "P-001")
    import re
    pkg_match = re.search(r'(P-\d{3,})', query, re.IGNORECASE)
    if pkg_match:
        package_code = pkg_match.group(1)
    
    # Detect action type
    if any(word in query.lower() for word in ['create', 'add', 'new', 'task']):
        action = ActionType.CREATE_TASK
    elif any(word in query.lower() for word in ['mark', 'change', 'set', 'awarded', 'status']):
        action = ActionType.PROPOSE_PATCH
        # Extract status (e.g., "awarded", "completed")
        if 'awarded' in query.lower():
            proposed_change = {"status": PackageStatus.AWARDED}
        elif 'completed' in query.lower():
            proposed_change = {"status": PackageStatus.COMPLETED}
    
    state["intake"] = IntakeResult(
        action_type=action,
        package_code=package_code,
        query=query,
        proposed_change=proposed_change,
        metadata={"parsed_at": datetime.now().isoformat()}
    )
    return state


def node_retrieve(state: GraphState) -> GraphState:
    """Pull SoR snapshot + recent events + memory hits."""
    db = state["db"]
    intake = state["intake"]
    
    package = None
    recent_events = []
    memory_hits = []
    
    if intake.package_code:
        try:
            pkg = get_package_by_code(db, intake.package_code)
            if pkg:
                package = {
                    "id": pkg.id,
                    "code": pkg.code,
                    "title": pkg.title,
                }
                # Get recent events
                timeline = get_audit_timeline(db, "package", pkg.id, limit=10)
                recent_events = [
                    {
                        "id": evt.id,
                        "type": evt.event_type,
                        "triggered_by": evt.triggered_by,
                        "created_at": evt.created_at.isoformat() if evt.created_at else None,
                        "payload": evt.payload,
                    }
                    for evt in timeline
                ]
                # Get memory hits
                hits = search_memory(db, "package", pkg.id, limit=5)
                memory_hits = [
                    {
                        "id": mem.id,
                        "memory_type": mem.memory_type,
                        "content": mem.content,
                    }
                    for mem in hits
                ]
        except Exception as e:
            # Package not found or error
            pass
    
    state["retrieve"] = RetrieveResult(
        package=package,
        recent_events=recent_events,
        memory_hits=memory_hits,
    )
    return state


def node_plan(state: GraphState) -> GraphState:
    """Produce structured plan."""
    intake = state["intake"]
    retrieve = state["retrieve"]
    
    reasoning = ""
    proposed_steps = []
    
    if intake.action_type == ActionType.QUERY:
        reasoning = "User is asking for information. Read-only retrieval."
        proposed_steps = ["Retrieve package details", "Format response"]
    
    elif intake.action_type == ActionType.CREATE_TASK:
        reasoning = "User wants to create a new task."
        proposed_steps = [
            "Validate task creation parameters",
            "Check user has OPERATOR or ANALYST role",
            "Create task via idempotent create_task()",
            "Store memory of task intent",
        ]
    
    elif intake.action_type == ActionType.PROPOSE_PATCH:
        reasoning = "User wants to change package status. Requires approval workflow."
        proposed_steps = [
            "Validate status transition rules",
            "Check user role has permission",
            "Assess risk level (impact x uncertainty)",
            "Create approval request (since patch changes state)",
            "Await approval before applying patch",
        ]
    
    state["plan"] = PlanResult(
        action_type=intake.action_type,
        reasoning=reasoning,
        proposed_steps=proposed_steps,
    )
    return state


def node_validate(state: GraphState) -> GraphState:
    """Run deterministic policy checks."""
    intake = state["intake"]
    retrieve = state["retrieve"]
    user = state["user"]
    db = state["db"]
    
    is_valid = True
    requires_approval = False
    requires_escalation = False
    reasons = []
    warnings = []
    
    # For write operations, validate against policies
    if intake.action_type == ActionType.PROPOSE_PATCH and retrieve.package:
        pkg = retrieve.package
        
        try:
            # Load actual package object for validation
            pkg_obj = get_package(db, pkg["id"])
            
            # Validate patch
            result = validate_patch(
                entity_type="package",
                entity=pkg_obj,
                patch=intake.proposed_change,
                user=user,
                impact=ImpactLevel.MEDIUM,  # Default, can be caller-specified
                uncertainty=UncertaintyLevel.MEDIUM,
            )
            
            is_valid = result.is_allowed
            requires_approval = result.requires_approval
            requires_escalation = result.requires_escalation
            reasons = result.reasons
            warnings = result.warnings
        except Exception as e:
            is_valid = False
            reasons = [f"Validation error: {str(e)}"]
    
    elif intake.action_type == ActionType.CREATE_TASK:
        # Task creation requires OPERATOR or ANALYST
        if not user.has_any_role(Role.OPERATOR, Role.ANALYST):
            is_valid = False
            reasons = ["Requires OPERATOR or ANALYST role"]
        else:
            requires_approval = False  # Tasks don't need approval
    
    state["validate"] = ValidateResult(
        is_valid=is_valid,
        requires_approval=requires_approval,
        requires_escalation=requires_escalation,
        reasons=reasons,
        warnings=warnings,
    )
    return state


def node_arbitration(state: GraphState) -> GraphState:
    """Decide AUTO vs APPROVAL_REQUIRED based on validation."""
    validate = state["validate"]
    
    decision_type = "AUTO"
    risk_level = "low"
    
    if not validate.is_valid:
        decision_type = "REJECT"
        risk_level = "blocked"
    elif validate.requires_escalation:
        decision_type = "ESCALATE"
        risk_level = "critical"
    elif validate.requires_approval:
        decision_type = "APPROVAL_REQUIRED"
        risk_level = "high"
    else:
        decision_type = "AUTO"
        risk_level = "low"
    
    state["arbitration"] = {
        "decision_type": decision_type,
        "risk_level": risk_level,
        "timestamp": datetime.now().isoformat(),
    }
    return state


def node_execute(state: GraphState) -> GraphState:
    """Call tool adapters based on decision."""
    intake = state["intake"]
    retrieve = state["retrieve"]
    user = state["user"]
    db = state["db"]
    arbitration = state["arbitration"]
    
    success = False
    resource_id = None
    resource_type = None
    message = ""
    
    if arbitration["decision_type"] == "REJECT":
        message = "Request rejected due to policy violation. " + "; ".join(state["validate"].reasons)
        success = False
    
    elif intake.action_type == ActionType.QUERY:
        # Read-only, no execution needed
        success = True
        message = "Query retrieved successfully"
    
    elif intake.action_type == ActionType.CREATE_TASK and arbitration["decision_type"] == "AUTO":
        try:
            # Create task (idempotent)
            task = create_task(
                db,
                package_id=retrieve.package["id"] if retrieve.package else None,
                title=f"Follow-up for {retrieve.package['code'] if retrieve.package else 'Unknown'}",
                assignee_id=user.user_id,
                triggered_by=user.user_id,
                idempotency_key=f"graph-{user.user_id}-{datetime.now().timestamp()}",
            )
            success = True
            resource_id = task.id
            resource_type = "task"
            message = f"Task created successfully: {task.id}"
        except Exception as e:
            success = False
            message = f"Failed to create task: {str(e)}"
    
    elif intake.action_type == ActionType.PROPOSE_PATCH:
        try:
            # Create approval request (not direct update)
            approval = propose_package_patch(
                db,
                package_id=retrieve.package["id"],
                patch=intake.proposed_change,
                reason=f"User request: {intake.query}",
                requested_by=user.user_id,
                idempotency_key=f"graph-approval-{user.user_id}-{datetime.now().timestamp()}",
            )
            success = True
            resource_id = approval.id
            resource_type = "approval"
            if arbitration["decision_type"] == "APPROVAL_REQUIRED":
                message = f"Approval request created: {approval.id}. Awaiting approval."
            else:
                message = f"Approval request created: {approval.id}"
        except Exception as e:
            success = False
            message = f"Failed to create approval request: {str(e)}"
    
    state["execute"] = ExecuteResult(
        success=success,
        resource_id=resource_id,
        resource_type=resource_type,
        message=message,
    )
    return state


def node_verify(state: GraphState) -> GraphState:
    """Re-read and confirm invariants."""
    execute = state["execute"]
    db = state["db"]
    
    is_valid = True
    final_state = None
    message = ""
    
    if execute.success and execute.resource_id:
        try:
            if execute.resource_type == "task":
                from app.tools.models import Task
                task = db.query(Task).filter(Task.id == execute.resource_id).first()
                if task:
                    final_state = {
                        "type": "task",
                        "id": task.id,
                        "status": task.status,
                    }
                    message = f"Task verified: {task.id}"
            elif execute.resource_type == "approval":
                from app.tools.models import Approval
                approval = db.query(Approval).filter(Approval.id == execute.resource_id).first()
                if approval:
                    final_state = {
                        "type": "approval",
                        "id": approval.id,
                        "status": approval.status,
                    }
                    message = f"Approval verified: {approval.id}"
        except Exception as e:
            is_valid = False
            message = f"Verification failed: {str(e)}"
    else:
        message = "No resource created, verification skipped"
    
    state["verify"] = {
        "is_valid": is_valid,
        "final_state": final_state,
        "message": message,
    }
    return state


def node_memory_update(state: GraphState) -> GraphState:
    """Store summaries/decisions in memory."""
    intake = state["intake"]
    retrieve = state["retrieve"]
    user = state["user"]
    db = state["db"]
    execute = state["execute"]
    
    stored_memories = []
    
    if retrieve.package and execute.success:
        try:
            # Store decision memory
            memory = store_memory(
                db,
                entity_type="package",
                entity_id=retrieve.package["id"],
                memory_type="decision",
                content=f"User {user.name} ({user.user_id}) requested: {intake.query}",
                metadata={"user_id": user.user_id, "action": intake.action_type},
                source_refs={"approval_id": execute.resource_id} if execute.resource_type == "approval" else None,
            )
            stored_memories.append(memory.id)
        except Exception as e:
            pass  # Memory storage is best-effort
    
    state["memory_update"] = {
        "stored_memories": stored_memories,
        "timestamp": datetime.now().isoformat(),
    }
    return state


def node_respond(state: GraphState) -> GraphState:
    """Format final response with evidence."""
    intake = state["intake"]
    retrieve = state["retrieve"]
    execute = state["execute"]
    verify = state["verify"]
    
    response = ""
    response_evidence = []
    
    if not execute.success:
        response = f"Request could not be fulfilled. {execute.message}"
    else:
            if intake.action_type == ActionType.QUERY and retrieve.package:
                response = f"Package {retrieve.package['code']}: {retrieve.package['title']}\n\n"
                response += f"Recent events: {len(retrieve.recent_events)} in history.\n"
            response += execute.message
        else:
            response = execute.message
        
        if verify["final_state"]:
            response_evidence.append({
                "type": "created_resource",
                "resource_type": verify["final_state"]["type"],
                "resource_id": verify["final_state"]["id"],
                "resource_status": verify["final_state"].get("status"),
            })
        
        if retrieve.recent_events:
            response_evidence.append({
                "type": "event_timeline",
                "count": len(retrieve.recent_events),
                "latest_event": retrieve.recent_events[0] if retrieve.recent_events else None,
            })
    
    state["response"] = response
    state["response_evidence"] = response_evidence
    return state


# ============== Graph Construction ==============


def build_graph() -> StateGraph:
    """Build the LangGraph orchestration graph."""
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("intake", node_intake)
    graph.add_node("retrieve", node_retrieve)
    graph.add_node("plan", node_plan)
    graph.add_node("validate", node_validate)
    graph.add_node("arbitration", node_arbitration)
    graph.add_node("execute", node_execute)
    graph.add_node("verify", node_verify)
    graph.add_node("memory_update", node_memory_update)
    graph.add_node("respond", node_respond)
    
    # Add edges (linear flow for now)
    graph.add_edge("intake", "retrieve")
    graph.add_edge("retrieve", "plan")
    graph.add_edge("plan", "validate")
    graph.add_edge("validate", "arbitration")
    graph.add_edge("arbitration", "execute")
    graph.add_edge("execute", "verify")
    graph.add_edge("verify", "memory_update")
    graph.add_edge("memory_update", "respond")
    graph.add_edge("respond", END)
    
    # Set entry point
    graph.set_entry_point("intake")
    
    return graph


def create_runnable_graph():
    """Create a compiled, executable graph."""
    return build_graph().compile()
