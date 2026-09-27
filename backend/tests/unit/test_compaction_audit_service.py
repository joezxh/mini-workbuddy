"""CrossModeHealthService 跨模式健康度指标测试。"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
from app.services.compaction_audit_service import CrossModeHealthService


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_get_weekly_health_metrics_returns_expected_keys():
    """weekly_health_metrics 返回 total/mem0_synced/mem0_failed/error 四指标"""
    fake_session = MagicMock()
    fake_session.execute.return_value.scalars.return_value.all.return_value = []
    service = CrossModeHealthService(tenant_id=1)

    with patch(
        "app.services.compaction_audit_service.SessionLocal",
        return_value=fake_session,
        create=True,
    ):
        result = asyncio.run(service.get_weekly_health_metrics())

    assert "total" in result
    assert "mem0_synced" in result
    assert "mem0_failed" in result
    assert "error" in result
    assert "mem0_sync_rate" in result


def test_get_weekly_health_metrics_no_data_returns_zero():
    """空数据时返回 0 + 0% 同步率"""
    fake_session = MagicMock()
    fake_session.execute.return_value.scalars.return_value.all.return_value = []
    service = CrossModeHealthService(tenant_id=1)

    with patch(
        "app.services.compaction_audit_service.SessionLocal",
        return_value=fake_session,
        create=True,
    ):
        result = asyncio.run(service.get_weekly_health_metrics())

    assert result["total"] == 0
    assert result["mem0_sync_rate"] == 0.0


def test_get_weekly_health_metrics_handles_exception():
    """DB 异常时返回兜底零值,不抛"""
    fake_session = MagicMock()
    fake_session.execute.side_effect = RuntimeError("db down")
    service = CrossModeHealthService(tenant_id=1)

    with patch(
        "app.services.compaction_audit_service.SessionLocal",
        return_value=fake_session,
        create=True,
    ):
        result = asyncio.run(service.get_weekly_health_metrics())

    assert isinstance(result, dict)
    assert result["total"] == 0