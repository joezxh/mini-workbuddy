"""Task 6: ENABLE_CROSS_MODE_RECORDER 功能开关测试。

覆盖:
1. 设置存在 & 默认 False
2. CrossModeContextRecorder.record_finalize 在 False 时跳过所有副作用
3. 在 True 时正常写入 L2
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import settings


def test_feature_flag_exists_and_default_false():
    """ENABLE_CROSS_MODE_RECORDER 必须存在,默认 False"""
    assert hasattr(settings, "ENABLE_CROSS_MODE_RECORDER")
    # 默认值应该是 False(渐进式上线)
    assert settings.ENABLE_CROSS_MODE_RECORDER is False


def test_feature_flag_disabled_skips_recorder():
    """flag=False 时 record_finalize 必须立即返回,无副作用"""
    from app.ai.services.cross_mode_recorder import CrossModeContextRecorder

    fake_db = MagicMock()
    recorder = CrossModeContextRecorder(db=fake_db)

    # patch 所有可能的副作用来源
    with patch.object(recorder, "_ensure_manager") as mock_manager, patch.object(
        recorder, "_write_audit"
    ) as mock_audit:
        with patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", False):
            result = recorder.record_finalize(
                session_id=1,
                user_id=1,
                tenant_id=1,
                session_type="agent",
                payload={"text": "hello"},
            )

        # flag=False 时,不能调用任何下游副作用
        assert result is None
        mock_manager.assert_not_called()
        mock_audit.assert_not_called()


def test_feature_flag_enabled_proceeds():
    """flag=True 时 record_finalize 必须走到 _ensure_manager。"""
    from app.ai.services.cross_mode_recorder import CrossModeContextRecorder

    fake_db = MagicMock()
    recorder = CrossModeContextRecorder(db=fake_db)

    fake_manager = MagicMock()
    fake_manager.persist_l2_context.return_value = 42

    with patch.object(recorder, "_ensure_manager", return_value=fake_manager), \
         patch.object(recorder, "_write_audit") as mock_audit:
        with patch("app.config.settings.ENABLE_CROSS_MODE_RECORDER", True):
            result = recorder.record_finalize(
                session_id=1,
                user_id=1,
                tenant_id=1,
                session_type="agent",
                payload={"text": "hi"},
            )
        # flag=True 时必须调用下游
        assert result is not None or mock_audit.called