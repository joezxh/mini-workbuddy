"""AutoCompactionScheduler 跨模式健康度周报接入测试。"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.auto_compaction_scheduler import AutoCompactionScheduler


def test_generate_weekly_report_uses_health_service():
    """_generate_weekly_report 必须委托给 CrossModeHealthService。"""
    scheduler = AutoCompactionScheduler()

    fake_metrics = {
        "total": 5,
        "mem0_synced": 4,
        "mem0_failed": 1,
        "error": 0,
        "mem0_sync_rate": 0.8,
        "window_start": "2026-09-20T00:00:00",
        "window_end": "2026-09-27T00:00:00",
    }

    fake_service = MagicMock()
    fake_service.get_weekly_health_metrics = AsyncMock(return_value=fake_metrics)

    with patch(
        "app.services.auto_compaction_scheduler.CrossModeHealthService",
        return_value=fake_service,
        create=True,
    ):
        result = asyncio.run(scheduler._generate_weekly_report())

    assert result["total"] == 5
    assert result["mem0_synced"] == 4
    assert result["mem0_failed"] == 1
    assert result["mem0_sync_rate"] == 0.8
    assert result["period_days"] == 7
    fake_service.get_weekly_health_metrics.assert_awaited_once()


def test_generate_weekly_report_returns_safe_default_on_failure():
    """DB 异常时周报仍能返回结构化 dict,不抛。"""
    scheduler = AutoCompactionScheduler()

    fake_service = MagicMock()
    fake_service.get_weekly_health_metrics = AsyncMock(
        side_effect=RuntimeError("db down"),
    )

    with patch(
        "app.services.auto_compaction_scheduler.CrossModeHealthService",
        return_value=fake_service,
        create=True,
    ):
        result = asyncio.run(scheduler._generate_weekly_report())

    assert isinstance(result, dict)
    assert result.get("total", 0) == 0


def test_generate_weekly_report_includes_generated_at():
    """周报必须包含 generated_at 时间戳字段。"""
    scheduler = AutoCompactionScheduler()

    fake_service = MagicMock()
    fake_service.get_weekly_health_metrics = AsyncMock(
        return_value={
            "total": 0,
            "mem0_synced": 0,
            "mem0_failed": 0,
            "error": 0,
            "mem0_sync_rate": 0.0,
            "window_start": None,
            "window_end": None,
        },
    )

    with patch(
        "app.services.auto_compaction_scheduler.CrossModeHealthService",
        return_value=fake_service,
        create=True,
    ):
        result = asyncio.run(scheduler._generate_weekly_report())

    assert "generated_at" in result
    assert result["period_days"] == 7