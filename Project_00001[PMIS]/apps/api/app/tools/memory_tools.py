from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List, Dict, Any
from uuid import uuid4

from .models import Memory, MemoryType, Package
from .user_context import UserContext


def store_memory(
    db: Session,
    entity_type: str,
    entity_id: str,
    content: str,
    memory_type: MemoryType | str,
    user: UserContext,
    package_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    source_refs: Optional[List[str]] = None,
) -> dict:
    """
    Memory tool: Store memory/context for an entity.
    
    Args:
        entity_type: 'package', 'task', 'user', etc.
        entity_id: ID of entity
        content: Memory text (e.g., analysis notes, conversation snippet)
        memory_type: CONTEXT, DECISION, ANALYSIS, INTEGRATION
        package_id: Optional package context
        metadata: Additional metadata
        source_refs: List of source IDs (e.g., event IDs, task IDs)
    
    Returns:
        Dict with memory_id, created_at, etc.
    """
    if isinstance(memory_type, str):
        memory_type = MemoryType(memory_type)
    
    memory = Memory(
        entity_type=entity_type,
        entity_id=entity_id,
        memory_type=memory_type,
        content=content,
        package_id=package_id,
        metadata=metadata or {},
        source_refs=source_refs or [],
    )
    
    db.add(memory)
    db.commit()
    db.refresh(memory)
    
    return {
        "memory_id": memory.id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "memory_type": memory.memory_type.value,
        "created_at": memory.created_at.isoformat(),
    }


def search_memory(
    db: Session,
    entity_type: str,
    entity_id: str,
    query: Optional[str] = None,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[dict]:
    """
    Memory tool: Search memories for entity.
    
    Args:
        entity_type: 'package', 'task', 'user'
        entity_id: ID of entity
        query: Optional text to search in content (simple substring search)
        top_k: Limit results
        filters: Optional filters (e.g., {'memory_type': 'DECISION'})
    
    Returns:
        List of memory dicts, most recent first.
    """
    db_query = db.query(Memory).filter(
        and_(
            Memory.entity_type == entity_type,
            Memory.entity_id == entity_id,
        )
    )
    
    # Apply text filter
    if query:
        db_query = db_query.filter(Memory.content.ilike(f"%{query}%"))
    
    # Apply type filter
    if filters and "memory_type" in filters:
        memory_type = filters["memory_type"]
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)
        db_query = db_query.filter(Memory.memory_type == memory_type)
    
    memories = (
        db_query
        .order_by(Memory.created_at.desc())
        .limit(top_k)
        .all()
    )
    
    return [
        {
            "memory_id": m.id,
            "entity_type": m.entity_type,
            "entity_id": m.entity_id,
            "memory_type": m.memory_type.value,
            "content": m.content,
            "metadata": m.metadata,
            "source_refs": m.source_refs,
            "created_at": m.created_at.isoformat(),
        }
        for m in memories
    ]
