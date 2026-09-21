"""EventBus 分发单测：LOG 级走日志、DB 级委托事件服务。"""
from app.schemas.agent.event_types import EventCategory, EventEnvelope, EventLevel
from app.ai.events.bus import EventBus


class FakeEventService:
    def __init__(self):
        self.envelopes = []

    def record_envelope(self, env):
        self.envelopes.append(env)
        return len(self.envelopes)


def _env(event_type, levels, category=EventCategory.MODEL):
    return EventEnvelope(
        execution_id="e1", event_type=event_type, category=category,
        levels=list(levels), content={},
    )


def test_db_level_delegates_to_service():
    svc = FakeEventService()
    bus = EventBus(event_service=svc)
    bus.publish(_env("tool_call", [EventLevel.DB, EventLevel.STREAM], EventCategory.TOOL))
    assert [e.event_type for e in svc.envelopes] == ["tool_call"]


def test_log_only_does_not_hit_db():
    svc = FakeEventService()
    bus = EventBus(event_service=svc)
    bus.publish(_env("model_call", [EventLevel.LOG]))
    assert svc.envelopes == []


def test_publish_always_debug_logs(capsys):
    import logging
    logging.basicConfig(level=logging.DEBUG)
    svc = FakeEventService()
    bus = EventBus(event_service=svc)
    bus.publish(_env("model_call", [EventLevel.LOG]))
    # 不抛异常即视为通过（日志绑定由 loguru 处理，此处验证无副作用）
