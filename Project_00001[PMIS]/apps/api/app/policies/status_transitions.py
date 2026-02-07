"""
Deterministic status transition rules for Package and Task entities.

No LLM involved—pure rule-based state machines.
"""

from enum import Enum
from typing import Set, Dict, List
from dataclasses import dataclass


class PackageStatus(str, Enum):
    """Package lifecycle statuses."""
    DRAFT = "draft"                  # Initial state, editable
    SUBMITTED = "submitted"          # Submitted for review
    IN_REVIEW = "in_review"          # Under evaluation
    APPROVED = "approved"            # Approved by governance
    AWARDED = "awarded"              # Contract awarded
    ACTIVE = "active"                # Executing tasks
    ON_HOLD = "on_hold"              # Paused execution
    COMPLETED = "completed"          # All tasks done
    CANCELLED = "cancelled"          # Cancelled (terminal)
    ARCHIVED = "archived"            # Archived (terminal)


class TaskStatus(str, Enum):
    """Task lifecycle statuses."""
    PENDING = "pending"              # Not started
    IN_PROGRESS = "in_progress"      # Being worked on
    BLOCKED = "blocked"              # Cannot proceed
    REVIEW_NEEDED = "review_needed"  # Awaiting review
    COMPLETED = "completed"          # Done
    CANCELLED = "cancelled"          # Cancelled (terminal)


@dataclass
class Transition:
    """A valid state transition rule."""
    from_status: str
    to_status: str
    description: str
    requires_approval: bool = False
    risk_level: str = "low"           # low, medium, high


class PackageTransitions:
    """Deterministic state machine for Package status transitions."""
    
    # Define all valid transitions
    RULES: List[Transition] = [
        # Initial submissions
        Transition(PackageStatus.DRAFT, PackageStatus.SUBMITTED, 
                  "Submit package for review"),
        
        # Review flow
        Transition(PackageStatus.SUBMITTED, PackageStatus.IN_REVIEW,
                  "Start formal review"),
        Transition(PackageStatus.IN_REVIEW, PackageStatus.APPROVED,
                  "Approve package after review"),
        
        # Rejection to resubmission
        Transition(PackageStatus.IN_REVIEW, PackageStatus.SUBMITTED,
                  "Return to submitter for revisions", risk_level="low"),
        Transition(PackageStatus.SUBMITTED, PackageStatus.DRAFT,
                  "Revert to draft for major changes", risk_level="low"),
        
        # Award and activation
        Transition(PackageStatus.APPROVED, PackageStatus.AWARDED,
                  "Award package/contract", requires_approval=True, risk_level="high"),
        Transition(PackageStatus.AWARDED, PackageStatus.ACTIVE,
                  "Activate and begin execution"),
        
        # Execution phase
        Transition(PackageStatus.ACTIVE, PackageStatus.ON_HOLD,
                  "Pause execution temporarily", risk_level="medium"),
        Transition(PackageStatus.ON_HOLD, PackageStatus.ACTIVE,
                  "Resume execution"),
        
        # Completion / terminal states
        Transition(PackageStatus.ACTIVE, PackageStatus.COMPLETED,
                  "Mark all tasks completed"),
        Transition(PackageStatus.APPROVED, PackageStatus.CANCELLED,
                  "Cancel before award", risk_level="medium"),
        Transition(PackageStatus.AWARDED, PackageStatus.CANCELLED,
                  "Cancel after award (contract termination)", 
                  requires_approval=True, risk_level="high"),
        Transition(PackageStatus.ACTIVE, PackageStatus.CANCELLED,
                  "Terminate active execution",
                  requires_approval=True, risk_level="high"),
        
        # Archival (from any terminal state)
        Transition(PackageStatus.COMPLETED, PackageStatus.ARCHIVED,
                  "Archive completed package"),
        Transition(PackageStatus.CANCELLED, PackageStatus.ARCHIVED,
                  "Archive cancelled package"),
    ]
    
    # Build lookup table for O(1) transition checks
    _TRANSITIONS: Dict[str, Set[str]] = {}
    _TRANSITION_DETAILS: Dict[tuple, Transition] = {}
    
    @classmethod
    def _build_lookup(cls):
        """Build transition lookup tables."""
        if cls._TRANSITIONS:
            return  # Already built
        
        for rule in cls.RULES:
            from_key = rule.from_status.value
            to_key = rule.to_status.value
            
            if from_key not in cls._TRANSITIONS:
                cls._TRANSITIONS[from_key] = set()
            
            cls._TRANSITIONS[from_key].add(to_key)
            cls._TRANSITION_DETAILS[(from_key, to_key)] = rule
    
    @classmethod
    def is_valid(cls, from_status: str, to_status: str) -> bool:
        """Check if transition is allowed."""
        cls._build_lookup()
        from_key = from_status.value if hasattr(from_status, 'value') else from_status
        to_key = to_status.value if hasattr(to_status, 'value') else to_status
        
        return to_key in cls._TRANSITIONS.get(from_key, set())
    
    @classmethod
    def get_rule(cls, from_status: str, to_status: str) -> Transition | None:
        """Get transition rule details."""
        cls._build_lookup()
        from_key = from_status.value if hasattr(from_status, 'value') else from_status
        to_key = to_status.value if hasattr(to_status, 'value') else to_status
        
        return cls._TRANSITION_DETAILS.get((from_key, to_key))
    
    @classmethod
    def get_valid_next_statuses(cls, from_status: str) -> Set[str]:
        """Get all valid next statuses from current status."""
        cls._build_lookup()
        from_key = from_status.value if hasattr(from_status, 'value') else from_status
        return cls._TRANSITIONS.get(from_key, set())


class TaskTransitions:
    """Deterministic state machine for Task status transitions."""
    
    RULES: List[Transition] = [
        # Initial state
        Transition(TaskStatus.PENDING, TaskStatus.IN_PROGRESS,
                  "Start working on task"),
        
        # Blocking
        Transition(TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED,
                  "Task blocked by external factor", risk_level="medium"),
        Transition(TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS,
                  "Unblock and resume work"),
        
        # Review before completion
        Transition(TaskStatus.IN_PROGRESS, TaskStatus.REVIEW_NEEDED,
                  "Submit for review/approval"),
        Transition(TaskStatus.REVIEW_NEEDED, TaskStatus.COMPLETED,
                  "Review approved, mark complete"),
        
        # Return for revisions
        Transition(TaskStatus.REVIEW_NEEDED, TaskStatus.IN_PROGRESS,
                  "Returned from review for revisions"),
        
        # Direct completion
        Transition(TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED,
                  "Mark task complete (no review needed)"),
        
        # Cancellation
        Transition(TaskStatus.PENDING, TaskStatus.CANCELLED,
                  "Cancel before start"),
        Transition(TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED,
                  "Cancel in-progress task", risk_level="medium"),
        Transition(TaskStatus.BLOCKED, TaskStatus.CANCELLED,
                  "Cancel blocked task"),
        Transition(TaskStatus.REVIEW_NEEDED, TaskStatus.CANCELLED,
                  "Cancel instead of approving", risk_level="low"),
    ]
    
    _TRANSITIONS: Dict[str, Set[str]] = {}
    _TRANSITION_DETAILS: Dict[tuple, Transition] = {}
    
    @classmethod
    def _build_lookup(cls):
        """Build transition lookup tables."""
        if cls._TRANSITIONS:
            return
        
        for rule in cls.RULES:
            from_key = rule.from_status.value
            to_key = rule.to_status.value
            
            if from_key not in cls._TRANSITIONS:
                cls._TRANSITIONS[from_key] = set()
            
            cls._TRANSITIONS[from_key].add(to_key)
            cls._TRANSITION_DETAILS[(from_key, to_key)] = rule
    
    @classmethod
    def is_valid(cls, from_status: str, to_status: str) -> bool:
        """Check if transition is allowed."""
        cls._build_lookup()
        from_key = from_status.value if hasattr(from_status, 'value') else from_status
        to_key = to_status.value if hasattr(to_status, 'value') else to_status
        
        return to_key in cls._TRANSITIONS.get(from_key, set())
    
    @classmethod
    def get_rule(cls, from_status: str, to_status: str) -> Transition | None:
        """Get transition rule details."""
        cls._build_lookup()
        from_key = from_status.value if hasattr(from_status, 'value') else from_status
        to_key = to_status.value if hasattr(to_status, 'value') else to_status
        
        return cls._TRANSITION_DETAILS.get((from_key, to_key))
    
    @classmethod
    def get_valid_next_statuses(cls, from_status: str) -> Set[str]:
        """Get all valid next statuses from current status."""
        cls._build_lookup()
        from_key = from_status.value if hasattr(from_status, 'value') else from_status
        return cls._TRANSITIONS.get(from_key, set())
