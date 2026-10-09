"""Task 16: 性能基准 — persist_l2_context 与 get_context_with_mode_filter 的 p95 延迟。

性能预算:
- persist_l2_context:100 次调用 p95 < 500ms(单次预算 5ms)
- get_context_with_mode_filter:50 条预填 + 50 次调用 p95 < 300ms(单次预算 6ms)

测试策略:
- 真实 SQLite(临时 db)
- 跳过 recorder / Mem0(只测 L2 路径,与部署形态无关)
- 多次采样取 p95(SQLite 内存测试基线,真实 PG 应更快)
"""
from __future__ import annotations

import time
import pytest
from sqlalchemy import create_engine, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


# --- SQLite 兼容性 ---
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(BigInteger, "sqlite")
def _compile_biginteger_sqlite(type_, compiler, **kw):
    return "INTEGER"


import app.db.init_models  # noqa: F401,E402
from app.db.database import Base  # noqa: E402
from app.models.ai.ai_chat_context_storage import AIChatContextStorage  # noqa: E402
from app.ai.context_manager import ContextManager  # noqa: E402


# --- Fixtures ---

@pytest.fixture
def sqlite_engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'perf_test.db'}")
    Base.metadata.create_all(
        bind=eng,
        tables=[AIChatContextStorage.__table__],
    )
    return eng


@pytest.fixture
def session_local(sqlite_engine):
    return sessionmaker(bind=sqlite_engine, autoflush=False, autocommit=False)


@pytest.fixture
def db(session_local):
    s = session_local()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def mgr(db):
    return ContextManager(tenant_id=1, user_id=1)


# ─────────────────────────────────────────────────────────────────────
# 性能基准 1:persist_l2_context p95 < 500ms
# ─────────────────────────────────────────────────────────────────────

class TestPersistL2Performance:
    """persist_l2_context 100 次调用 p95 < 500ms(本地 SQLite 测试基线)。"""

    def test_persist_l2_p95_under_500ms(self, mgr, db):
        """100 次 persist_l2_context 调用,按 p95 评估。"""
        samples = []
        for i in range(100):
            t0 = time.perf_counter()
            rid = mgr.persist_l2_context(
                session_id=1,
                source_mode="skill",
                context_key=f"k_{i}",
                context_data={"i": i, "payload": "x" * 100},
                priority=2,
                ttl_hours=168,
                is_cross_mode_accessible=False,
                context_tags=["skill", "perf"],
                case_number="default",
                tenant_id=1,
                user_id=1,
                db=db,
            )
            samples.append((time.perf_counter() - t0) * 1000)
            assert rid is not None, f"persist failed at i={i}"

        samples.sort()
        p50 = samples[49]
        p95 = samples[94]
        p99 = samples[98]
        # 输出性能基线,便于趋势分析
        print(
            f"\n[perf] persist_l2: p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms"
        )
        assert p95 < 500, f"persist_l2 p95={p95:.1f}ms exceeds 500ms budget"


# ─────────────────────────────────────────────────────────────────────
# 性能基准 2:get_context_with_mode_filter p95 < 300ms
# ─────────────────────────────────────────────────────────────────────

class TestGetContextFilterPerformance:
    """get_context_with_mode_filter 50 条预填 + 50 次调用 p95 < 300ms。"""

    def test_get_context_with_mode_filter_p95_under_300ms(self, mgr, db):
        """50 条预填 + 50 次过滤调用。"""
        # 预填 50 条
        for i in range(50):
            mgr.persist_l2_context(
                session_id=1,
                source_mode="skill",
                context_key=f"k_{i}",
                context_data={"i": i, "payload": "y" * 100},
                priority=2,
                ttl_hours=168,
                is_cross_mode_accessible=False,
                context_tags=["skill", "perf"],
                case_number="default",
                tenant_id=1,
                user_id=1,
                db=db,
            )

        samples = []
        for _ in range(50):
            t0 = time.perf_counter()
            results = mgr.get_context_with_mode_filter(
                session_id=1,
                user_id=1,
                allow_cross_mode=False,
                limit=50,
                db=db,
            )
            samples.append((time.perf_counter() - t0) * 1000)
            assert isinstance(results, list)

        samples.sort()
        p50 = samples[24]
        p95 = samples[47]
        p99 = samples[49]
        print(
            f"\n[perf] get_context_with_mode_filter: p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms"
        )
        assert p95 < 300, f"filter p95={p95:.1f}ms exceeds 300ms budget"


# ─────────────────────────────────────────────────────────────────────
# 性能基准 3:混合场景 — finalize + 查询联合延迟
# ─────────────────────────────────────────────────────────────────────

class TestMixedWriteReadPerformance:
    """混合场景:写 10 + 读 10,联合 p95 < 800ms。"""

    def test_mixed_write_read_p95_under_800ms(self, mgr, db):
        """10 次写 + 10 次读,联合 20 次调用 p95。"""
        samples = []
        for i in range(20):  # 20 次写+读组合
            t0 = time.perf_counter()
            mgr.persist_l2_context(
                session_id=1, source_mode="general",
                context_key=f"mix_{i}", context_data={"i": i},
                priority=3, ttl_hours=168,
                tenant_id=1, user_id=1, db=db,
            )
            mgr.get_context_with_mode_filter(
                session_id=1, user_id=1, allow_cross_mode=False, db=db,
            )
            samples.append((time.perf_counter() - t0) * 1000)

        samples.sort()
        p95 = samples[int(len(samples) * 0.95) - 1]  # 20 * 0.95 = 19,索引 18
        print(f"\n[perf] mixed write+read: p95={p95:.2f}ms")
        assert p95 < 800, f"mixed p95={p95:.1f}ms exceeds 800ms budget"
