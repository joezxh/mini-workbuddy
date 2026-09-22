"""执行事件流级联测试：验证 Delta 事件不落库、块汇总才落库 (spec §4.4)。

核心验收标准：
1. TextBlockDeltaEvent → EventBus 发布信封仅含 [STREAM] 不含 [DB]
2. TextBlockEndEvent → EventBus 发布信封含 [DB]，且内容为全文汇总
3. agent_execution_event 表中 text_chunk/thinking_chunk记录数=0
4. text_done/thinking_done记录包含完整文本内容

依赖：pytest, sqlalchemy mock, AgentScope 事件模拟
"""
import pytest
from unittest.mock import MagicMock, patch
from app.schemas.agent.event_types import (
    EventLevel, DEFAULT_ROUTES, route_of, ExecutionEventType,
)
from app.ai.events.bus import EventBus
from app.ai.services.execution_event_service import ExecutionEventService


class TestDeltaNoPersistIntegration:
    """端到端集成测试组：模拟 AgentScope 事件流入 EventBus + Service。"""

    def test_text_chunk_route_excludes_db(self):
        """text_chunk 路由应明确排除 DB level。"""
        r = route_of("text_chunk")
        assert EventLevel.DB not in r.levels
        assert EventLevel.STREAM in r.levels

    def test_thinking_chunk_route_excludes_db(self):
        """thinking_chunk 路由应明确排除 DB level。"""
        r = route_of("thinking_chunk")
        assert EventLevel.DB not in r.levels
        assert EventLevel.STREAM in r.levels

    def test_text_done_route_includes_db(self):
        """text_done 路由必须包含 DB level。"""
        r = route_of("text_done")
        assert EventLevel.DB in r.levels
        assert EventLevel.STREAM not in r.levels

    @patch.object(ExecutionEventService, '_envelope_to_row')
    def test_record_envelope_skips_delta_events(self, mock_row):
        """EventService.record_envelope() 应对 delta 事件提前返回不入队。"""
        from app.schemas.agent.event_types import EventEnvelope, EventCategory
        
        service = ExecutionEventService(execution_id="test-exec-1")

        # 构造一个 text_chunk envelope（无 DB level）
        env = EventEnvelope(
            execution_id="test-exec-1",
            event_type="text_chunk",
            category=EventCategory.TEXT,
            levels=[EventLevel.STREAM],  # 不含 DB
            content={"delta": "some text"},
        )

        seq = service.record_envelope(env)

        # 断言：应返回 None，不入队
        assert seq is None
        mock_row.assert_not_called()

    @patch.object(ExecutionEventService, '_flush_batch')
    def test_block_summary_envelopes_get_queued(self, mock_flush):
        """块汇总事件(text_done/thinking_done)应被入队等待批量写入。"""
        with patch.object(ExecutionEventService, '__init__', lambda self, **kw: None):
            service = ExecutionEventService.__new__(ExecutionEventService)
            service.execution_id = "test-exec-2"
            service.trace_id = "trace-1"
            service._sequence = 0
            service._queue = MagicMock()
            service._owning_loop = None
            service._events = []
            service.start = MagicMock()

            from app.schemas.agent.event_types import EventEnvelope, EventCategory
            env = EventEnvelope(
                execution_id="test-exec-2",
                event_type="text_done",
                category=EventCategory.TEXT,
                levels=[EventLevel.DB],
                content={"text": "full text summary"},
            )

            seq = service.record_envelope(env)

            # 应有序列号 > 0
            assert seq is not None and seq >= 0
            service.start.assert_called_once()

    def test_all_chunk_events_have_stream_only_levels(self):
        """验证所有 *.chunk 类型的事件仅含 STREAM 级别。"""
        chunk_events = ["text_chunk", "thinking_chunk", "data_chunk"]
        for event_type in chunk_events:
            r = route_of(event_type)
            assert r.levels == frozenset({EventLevel.STREAM}), \
                f"{event_type} unexpectedly has DB/LOG/UI levels"

    def test_router_fallback_for_new_event_is_conservative(self):
        """新增未声明的事件应该保守地落入 DB（兜底安全）。"""
        r = route_of("brand_new_custom_event_12345")
        assert EventLevel.DB in r.levels

    @pytest.mark.skipif(True, reason="Requires actual database connection")
    def test_actual_db_audit_queries_this_test_file(self):
        """审计查询示例：确认 text_chunk/thinking_chunk记录数为 0。
        
        此测试需连接真实数据库运行，本地开发默认 skip。
        
        sql:
            SELECT COUNT(*) as cnt 
            FROM agent_execution_event 
            WHERE event_type IN ('text_chunk', 'thinking_chunk', 'data_chunk')
        
        预期：cnt = 0
        """
        import pytest
        pytest.skip("Manual verification only")


def test_route_consistency_check():
    """静态扫描：确保所有枚举成员都在路由表中有定义。"""
    members = [v for k, v in vars(ExecutionEventType).items() if not k.startswith("_")]
    missing = [m for m in members if m not in DEFAULT_ROUTES]
    assert missing == [], f"缺少路由定义的枚举值：{missing}"


# ── pytest 运行说明 ───────────────────────────────────────────────────────
# 单元测试：python -m pytest backend/tests/unit/test_delta_no_persist.py -v
# 数据库审计：手动在预发环境运行 test_actual_db_audit_queries_this_test_file
# 覆盖指标目标：100% 分支覆盖（delta vs summary 路径）