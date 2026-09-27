"""Task 7: lifespan startup/shutdown 接入验证。"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch


def _lifespan_patches(stack: ExitStack) -> None:
    """lifespan 测试用的副作用隔离 patch 集合。"""
    stack.enter_context(patch("app.config.settings.AUTO_CREATE_TABLES", False))
    stack.enter_context(patch("app.main.start_audit_writer"))
    stack.enter_context(patch("app.main.stop_audit_writer", new=AsyncMock()))
    stack.enter_context(patch("app.ai.tool_manager.get_tool_manager"))
    stack.enter_context(patch("app.ai.telemetry.exporter.setup_telemetry"))


def test_lifespan_initializes_scheduler_when_flag_enabled():
    """lifespan 启动阶段:flag=True 时必须 await initialize_scheduler()"""
    from app.main import lifespan

    fake_app = MagicMock()
    stack = ExitStack()
    _lifespan_patches(stack)

    try:
        mock_init = stack.enter_context(patch(
            "app.services.auto_compaction_scheduler.initialize_scheduler",
            new=AsyncMock(),
        ))
        mock_stop = stack.enter_context(patch(
            "app.services.auto_compaction_scheduler.shutdown_scheduler",
            new=AsyncMock(),
        ))
        stack.enter_context(patch(
            "app.config.settings.ENABLE_CROSS_MODE_RECORDER",
            True,
        ))

        async def drive():
            async with lifespan(fake_app):
                pass

        asyncio.run(drive())

        mock_init.assert_awaited_once()
        mock_stop.assert_awaited_once()
    finally:
        stack.close()


def test_lifespan_skips_scheduler_when_flag_disabled():
    """lifespan 启动阶段:flag=False 时不调用 initialize_scheduler"""
    from app.main import lifespan

    fake_app = MagicMock()
    stack = ExitStack()
    _lifespan_patches(stack)

    try:
        mock_init = stack.enter_context(patch(
            "app.services.auto_compaction_scheduler.initialize_scheduler",
            new=AsyncMock(),
        ))
        mock_stop = stack.enter_context(patch(
            "app.services.auto_compaction_scheduler.shutdown_scheduler",
            new=AsyncMock(),
        ))
        stack.enter_context(patch(
            "app.config.settings.ENABLE_CROSS_MODE_RECORDER",
            False,
        ))

        async def drive():
            async with lifespan(fake_app):
                pass

        asyncio.run(drive())

        mock_init.assert_not_called()
        mock_stop.assert_awaited_once()
    finally:
        stack.close()


def test_lifespan_tolerates_scheduler_init_failure():
    """初始化调度器失败不应阻断 lifespan 主流程"""
    from app.main import lifespan

    fake_app = MagicMock()
    stack = ExitStack()
    _lifespan_patches(stack)

    try:
        stack.enter_context(patch(
            "app.services.auto_compaction_scheduler.initialize_scheduler",
            new=AsyncMock(side_effect=RuntimeError("scheduler init boom")),
        ))
        stack.enter_context(patch(
            "app.services.auto_compaction_scheduler.shutdown_scheduler",
            new=AsyncMock(),
        ))
        stack.enter_context(patch(
            "app.config.settings.ENABLE_CROSS_MODE_RECORDER",
            True,
        ))

        async def drive():
            async with lifespan(fake_app):
                pass

        asyncio.run(drive())
    finally:
        stack.close()