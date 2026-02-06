import pytest
from app.tools.models import Package, Memory, MemoryType
from app.tools.memory_tools import store_memory, search_memory


@pytest.fixture
def sample_package(db_session):
    """Create a sample package."""
    pkg = Package(code="PKG-MEM-001", title="Memory Test Package")
    db_session.add(pkg)
    db_session.commit()
    return pkg


class TestStoreMemory:
    def test_store_memory_creates_record(self, db_session, sample_package, admin_user):
        """Test that store_memory creates a memory record."""
        result = store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="This is important context about the package.",
            memory_type=MemoryType.CONTEXT,
            user=admin_user,
            package_id=sample_package.id,
            metadata={"source": "analysis"},
            source_refs=["event_123", "task_456"],
        )
        
        assert result["memory_id"] is not None
        assert result["entity_type"] == "package"
        assert result["memory_type"] == "context"
        
        # Verify memory in DB
        memory = db_session.query(Memory).filter_by(id=result["memory_id"]).first()
        assert memory is not None
        assert memory.content == "This is important context about the package."
        assert memory.metadata["source"] == "analysis"
        assert "event_123" in memory.source_refs
    
    def test_store_memory_with_string_type(self, db_session, sample_package, admin_user):
        """Test that memory_type can be passed as string."""
        result = store_memory(
            db_session,
            entity_type="task",
            entity_id="task_123",
            content="Decision memo",
            memory_type="decision",  # String instead of enum
            user=admin_user,
        )
        
        assert result["memory_type"] == "decision"


class TestSearchMemory:
    def test_search_memory_by_entity(self, db_session, sample_package, admin_user):
        """Test searching memories for an entity."""
        # Create multiple memories
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Context about business requirements",
            memory_type=MemoryType.CONTEXT,
            user=admin_user,
        )
        
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Decision to use Python for backend",
            memory_type=MemoryType.DECISION,
            user=admin_user,
        )
        
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Analysis shows 40% performance improvement",
            memory_type=MemoryType.ANALYSIS,
            user=admin_user,
        )
        
        # Search without query
        results = search_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
        )
        
        assert len(results) == 3
    
    def test_search_memory_with_text_query(self, db_session, sample_package, admin_user):
        """Test searching memories with text query."""
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Backend uses Python FastAPI",
            memory_type=MemoryType.CONTEXT,
            user=admin_user,
        )
        
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Frontend uses Next.js TypeScript",
            memory_type=MemoryType.CONTEXT,
            user=admin_user,
        )
        
        # Search for Python
        results = search_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            query="Python",
        )
        
        assert len(results) == 1
        assert "Python FastAPI" in results[0]["content"]
    
    def test_search_memory_with_type_filter(self, db_session, sample_package, admin_user):
        """Test filtering memories by type."""
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Context item",
            memory_type=MemoryType.CONTEXT,
            user=admin_user,
        )
        
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Decision item",
            memory_type=MemoryType.DECISION,
            user=admin_user,
        )
        
        # Filter by DECISION type
        results = search_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            filters={"memory_type": MemoryType.DECISION},
        )
        
        assert len(results) == 1
        assert results[0]["memory_type"] == "decision"
    
    def test_search_memory_top_k_limit(self, db_session, sample_package, admin_user):
        """Test that top_k limits results."""
        # Create 5 memories
        for i in range(5):
            store_memory(
                db_session,
                entity_type="package",
                entity_id=sample_package.id,
                content=f"Memory {i}",
                memory_type=MemoryType.CONTEXT,
                user=admin_user,
            )
        
        # Ask for top 2
        results = search_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            top_k=2,
        )
        
        assert len(results) == 2
    
    def test_search_memory_most_recent_first(self, db_session, sample_package, admin_user):
        """Test that results are returned in reverse chronological order."""
        import time
        
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Oldest memory",
            memory_type=MemoryType.CONTEXT,
            user=admin_user,
        )
        
        time.sleep(0.1)  # Small delay
        
        store_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
            content="Newest memory",
            memory_type=MemoryType.CONTEXT,
            user=admin_user,
        )
        
        results = search_memory(
            db_session,
            entity_type="package",
            entity_id=sample_package.id,
        )
        
        assert len(results) == 2
        assert "Newest" in results[0]["content"]
        assert "Oldest" in results[1]["content"]
    
    def test_search_memory_empty_result(self, db_session, sample_package, admin_user):
        """Test searching for non-existent entity."""
        results = search_memory(
            db_session,
            entity_type="package",
            entity_id="nonexistent-id",
        )
        
        assert results == []
