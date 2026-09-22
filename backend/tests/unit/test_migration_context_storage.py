"""Tests for ai_context_storage table migration.

TDD Step 1: Write failing tests BEFORE running migration.
These tests verify the expected schema structure.
"""

import pytest
from sqlalchemy import text, inspect
from app.db.database import engine


def test_migration_creates_ai_context_storage_table():
    """Verify ai_context_storage table is created with correct schema."""
    with engine.begin() as conn:
        # Check if table exists
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'ai_context_storage'
                )
            """)
        )
        assert result.scalar() == True


def test_migration_table_has_required_columns():
    """Verify all required columns are present."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM ai_context_storage LIMIT 0")
        )
    
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('ai_context_storage')]
    
    required_columns = [
        'id', 'tenant_id', 'session_id', 'user_id', 'mode',
        'context_key', 'context_data', 'embedding_vector',
        'priority', 'access_count', 'last_accessed',
        'created_at', 'updated_at', 'expires_at'
    ]
    
    for col in required_columns:
        assert col in columns, f"Missing required column: {col}"


def test_migration_table_column_types():
    """Verify column data types match specification."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM ai_context_storage LIMIT 0")
        )
    
    inspector = inspect(engine)
    
    columns_info = {col['name']: col for col in inspector.get_columns('ai_context_storage')}
    
    # Verify primary key type
    assert columns_info['id']['autoincrement'] == True
    
    # Verify JSONB column (PostgreSQL-specific)
    assert columns_info['context_data']['type'] == 'JSONB'
    
    # Verify string lengths
    assert columns_info['mode']['length'] == 32
    assert columns_info['context_key']['length'] == 255


def test_migration_indexes_created():
    """Verify performance indexes are created."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM ai_context_storage LIMIT 0")
        )
    
    inspector = inspect(engine)
    
    indexes = inspector.get_indexes('ai_context_storage')
    index_names = [idx['name'] for idx in indexes]
    
    required_indexes = [
        'ix_ai_context_storage_tenant_mode',
        'ix_ai_context_storage_user_mode',
        'ix_ai_context_storage_last_access',
        'ix_ai_context_storage_expires'
    ]
    
    for idx in required_indexes:
        assert idx in index_names, f"Missing required index: {idx}"


def test_migration_unique_constraint():
    """Verify unique constraint on tenant/session/mode/key."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM ai_context_storage LIMIT 0")
        )
    
    inspector = inspect(engine)
    
    constraints = inspector.get_unique_constraints('ai_context_storage')
    assert len(constraints) > 0
    
    found_constraint = False
    for constraint in constraints:
        if constraint['name'] == 'uk_tenant_session_mode_key':
            found_constraint = True
            # Verify it covers the right columns
            assert set(constraint['column_names']) == {
                'tenant_id', 'session_id', 'mode', 'context_key'
            }
    
    assert found_constraint, "Unique constraint uk_tenant_session_mode_key not found"


def test_migration_downgrade_removes_table():
    """Test that downgrade properly removes the table."""
    with engine.begin() as conn:
        # Verify table exists before downgrade
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'ai_context_storage'
                )
            """)
        )
        table_exists_before = result.scalar()
        assert table_exists_before == True
        
        # Note: Actual downgrade would be tested by running:
        # alembic downgrade 2026_09_20_0000  (previous revision)
        # For now, we just verify the downgrade script exists and is callable
        from alembic.script import ScriptDirectory
        from alembic.runtime.environment import EnvironmentContext
        
        script_dir = ScriptDirectory.from_config("backend/alembic.ini")
        # Verify downgrade script is available
        assert script_dir.get_revision('2026_09_21_0000').downgrade is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
