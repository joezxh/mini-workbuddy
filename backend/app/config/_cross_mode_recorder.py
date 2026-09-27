"""跨模式上下文记录器配置。

`ENABLE_CROSS_MODE_RECORDER` 是 Task 6 引入的功能开关,
守卫所有 ``CrossModeContextRecorder`` 入口。
默认关闭以便渐进式上线,上线后由运维在 .env 翻转为 True。
"""
from pydantic import BaseModel


class CrossModeRecorderSettings(BaseModel):
    """跨模式上下文记录器配置字段"""

    # 总开关:关闭时 CrossModeContextRecorder.record_finalize 立即返回,不写 L2/Mem0
    ENABLE_CROSS_MODE_RECORDER: bool = False

    # 周报跨模式同步率告警阈值,低于此值触发 logger.error(配合健康告警)
    CROSS_MODE_SYNC_RATE_ALERT_THRESHOLD: float = 0.8
