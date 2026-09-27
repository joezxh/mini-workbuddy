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
    # inspector 返回类型对象(编译为 "JSONB(astext_type=Text())"),按类型名前缀断言
    assert 'JSONB' in str(columns_info['context_data']['type']).upper()
    
    # Verify string lengths(长度在类型对象上,列字典无 'length' 键)
    assert columns_info['mode']['type'].length == 32
    assert columns_info['context_key']['type'].length == 255


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
    """Verify unique constraint on tenant/session/mode/key.

    兼容两种建表路径:alembic 迁移建的是命名 UniqueConstraint;
    Base.metadata.create_all 建的是同列 unique Index——两者都保证唯一性。
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM ai_context_storage LIMIT 0")
        )

    inspector = inspect(engine)

    expected_columns = {'tenant_id', 'session_id', 'mode', 'context_key'}

    constraints = inspector.get_unique_constraints('ai_context_storage')
    by_constraint = any(
        set(c.get('column_names') or []) == expected_columns
        for c in constraints
    )

    indexes = inspector.get_indexes('ai_context_storage')
    by_index = any(
        i.get('unique') and set(i.get('column_names') or []) == expected_columns
        for i in indexes
    )

    assert by_constraint or by_index, (
        "未发现覆盖 (tenant_id, session_id, mode, context_key) 的唯一约束或唯一索引"
    )


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
        from pathlib import Path
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        # alembic.ini 相对本文件定位(backend/alembic.ini),不依赖 pytest cwd
        ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
        script_dir = ScriptDirectory.from_config(Config(str(ini_path)))
        # Verify downgrade script is available(Script 公开属性是 module)
        rev = script_dir.get_revision('2026_09_21_0000')
        assert rev is not None
        assert callable(getattr(rev.module, "downgrade", None)), (
            "2026_09_21_0000 迁移缺少可调用的 downgrade()"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
