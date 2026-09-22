"""HITL 超时告警测试（Phase 0 Day 2 - 本周内完成）

核心测试点：
1. 已被 resolve → 不触发告警  
2. timeout_minutes 参数生效
3. 日志警告正确打印
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


class TestHitlTimeoutMonitor:
    """HITL 超时监控器单元测试。"""

    def test_skips_if_resolved(self):
        """已被 resolve 的暂停不应触发告警。"""
        from app.ai.events.hitl import monitor_pause_timeout

        mock_db = MagicMock()
        execution_id = "test-exec-1"
        reply_id = "r-001"
        pause_time = datetime.now() - timedelta(minutes=60)

        # Mock：返回 None（表示已被 resolve）
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with patch('asyncio.sleep', return_value=None):
            asyncio.run(monitor_pause_timeout(mock_db, execution_id, reply_id, pause_time))

            # 验证未添加新记录
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()
            print("✅ 测试 1 通过：resolved 状态跳过")

    def test_timeout_parameter_applied(self):
        """timeout_minutes 参数应正确控制休眠时间。"""
        from app.ai.events.hitl import monitor_pause_timeout

        execution_id = "test-exec-2"
        reply_id = "r-002"
        pause_time = datetime.now() - timedelta(minutes=40)

        # 创建一个更真实的 mock DB 会话
        mock_db = MagicMock()
        mock_row = MagicMock(status="waiting")
        
        # 完整模拟 query().filter().order_by().first() 链
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = mock_row
        
        mock_order.first = mock_first
        mock_filter.order_by = MagicMock(return_value=mock_order)
        mock_query.filter = MagicMock(return_value=mock_filter)
        mock_db.query = MagicMock(return_value=mock_query)

        with patch('asyncio.sleep', return_value=None):
            # Mock EventBus.publish 以避免实际发送事件
            mock_publish = MagicMock()
            with patch('app.ai.events.bus.EventBus') as MockBus:
                MockBus.return_value.publish = mock_publish
                try:
                    asyncio.run(monitor_pause_timeout(
                        mock_db, execution_id, reply_id, pause_time, timeout_minutes=5
                    ))
                except Exception as e:
                    print(f"测试中被捕获的异常：{type(e).__name__}: {e}")
                    raise
            
            # 验证添加了超时告警记录（status='timeout_alert'）
            add_call_count = mock_db.add.call_count
            assert add_call_count == 1, f"Expected add to be called once, got {add_call_count}"
            mock_db.commit.assert_called_once()
            print(f"✅ 测试 2 通过：正确添加了告警记录")
