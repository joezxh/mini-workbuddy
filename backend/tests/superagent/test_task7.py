"""Task 7 单元测试 —— TR-7.1 / TR-7.3 / TR-7.4 / TR-7.5。

覆盖：Assessment accept 三条件 + inferred 候选、Policy 热变更 policy_effects /
apply_change、RoleModel 注入、EffectQueue per-kind 并发 + 指数退避、
Notices coalescing、AgentDeliveryService 幂等投递。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.superagent.assessor import Candidate
from app.ai.superagent.delivery import _DELIVERED_REQUESTS, AgentDeliveryService
from app.ai.superagent.effects import EFFECT_CONCURRENCY, EFFECT_KINDS, EffectQueue
from app.ai.superagent.notices import (
    _PENDING_NOTICES,
    coalescing_notice,
    followup_relay,
    receipt_notice,
    result_relay,
)
from app.ai.superagent.policy import AssessmentOutcome, PolicyService
from app.ai.superagent.repository import SuperAgentRepository
from app.ai.superagent.role_models import (
    RoleModel,
    RoleModelConfig,
    initialize_role_model,
    role_model_config_from_workspace,
)
from app.ai.superagent.sse_bus import SSEBus


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=SuperAgentRepository)
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    repo.atomic.return_value = ctx
    repo.next_seq.return_value = 1
    repo.enqueue_effect.return_value = MagicMock(id="e1")
    repo.effects_by_status.return_value = []
    repo.update_effect_status.return_value = None
    return repo


# ============ TR-7.1 Assessment accept 三条件 + inferred 候选 ============

class TestTR71Assessment:
    BASE = dict(
        matched_rules=[{"rule_id": "copy", "reason": "kw"}],
        direction="accept",
        intent_evidence="sender=alice · text=fix typo",
    )

    def test_can_accept_true_when_all_three_hold(self):
        assert AssessmentOutcome(**self.BASE).can_accept()

    def test_can_accept_fails_without_matched_rule(self):
        assert not AssessmentOutcome(**{**self.BASE, "matched_rules": []}).can_accept()

    def test_can_accept_fails_with_wrong_direction(self):
        for d in ("ignore", "block"):
            assert not AssessmentOutcome(**{**self.BASE, "direction": d}).can_accept()

    def test_can_accept_fails_without_intent_evidence(self):
        assert not AssessmentOutcome(**{**self.BASE, "intent_evidence": "  "}).can_accept()

    def test_assess_inferred_admission_yields_would_accept(self):
        """github.ci 无 sender → admission=inferred → direction=would_accept。"""
        svc = PolicyService(
            rules=[{"id": "ci", "intent": "CI 修复", "keywords": ["ci"]}],
        )
        outcome = svc.assess(
            source_kind="github.ci", source="ci-main",
            sender_id=None, addressed=False,
            trigger_text="ci failed on main branch",
        )
        assert outcome.gate_passed
        assert outcome.direction == "would_accept"
        # would_accept + matched + evidence → can_accept 走三条件
        assert outcome.can_accept()

    def test_inferred_candidate_records_would_accept_for_manual_confirm(self):
        """inferred 候选不直接 accept，记录 would_accept 待人工确认。"""
        svc = PolicyService(
            rules=[{"id": "ci", "intent": "CI 修复", "keywords": ["ci"]}],
            eval_mode="manual",
        )
        outcome = svc.assess(
            source_kind="github.ci", source="ci-main",
            sender_id=None, addressed=False, trigger_text="ci failed",
        )
        cand = Candidate(trigger_id="t1", thread_id="th1", outcome=outcome)
        assert outcome.direction == "would_accept"
        assert cand.outcome.direction == "would_accept"


# ============ TR-7.3 Policy 热变更：policy_effects + apply_change ============

class TestTR73PolicyEffects:
    @staticmethod
    def _policies():
        old = PolicyService(rules=[
            {"id": "copy", "intent": "文案", "keywords": ["copy"]},
            {"id": "visual", "intent": "视觉", "keywords": ["css"]},
        ])
        new = PolicyService(rules=[
            {"id": "copy", "intent": "文案", "keywords": ["copy"]},
        ])
        return old, new

    def test_removed_rule_affects_only_referencing_tickets(self):
        old, new = self._policies()
        tickets = [
            {"ticket_id": "t1", "title": "A",
             "mandate_matched_rules": [{"rule_id": "visual", "reason": "kw"}]},
            {"ticket_id": "t2", "title": "B",
             "mandate_matched_rules": [{"rule_id": "copy", "reason": "kw"}]},
            {"ticket_id": "t3", "title": "C",
             "mandate_matched_rules": [{"rule_id": "brand_new", "reason": "kw"}]},
        ]
        effects = new.policy_effects(tickets, old)
        assert set(effects) == {"t1"}
        assert effects["t1"] == {"kind": "rules_removed", "rules": ["visual"]}

    def test_string_rule_refs_supported(self):
        old, new = self._policies()
        tickets = [{"ticket_id": "t1", "mandate_matched_rules": ["visual", "copy"]}]
        effects = new.policy_effects(tickets, old)
        assert set(effects) == {"t1"}
        assert effects["t1"]["rules"] == ["visual"]

    def test_modified_instruction_and_added_rule_do_not_affect(self):
        old = PolicyService(rules=[
            {"id": "copy", "intent": "旧 instruction", "keywords": ["copy"]},
        ])
        new = PolicyService(rules=[
            {"id": "copy", "intent": "新 instruction", "keywords": ["copy", "typo"]},
            {"id": "visual", "intent": "视觉", "keywords": ["css"]},
        ])
        tickets = [{"ticket_id": "t1", "mandate_matched_rules": [{"rule_id": "copy"}]}]
        assert new.policy_effects(tickets, old) == {}

    def test_allowed_sender_change_does_not_change_effects(self):
        """allowed 变更不影响已 accept Ticket（Mandate 不可变）。"""
        old, new = self._policies()
        old.allowed_senders = {"alice"}
        new.allowed_senders = {"bob"}
        tickets = [{"ticket_id": "t1", "mandate_matched_rules": [{"rule_id": "visual"}]}]
        assert set(new.policy_effects(tickets, old)) == {"t1"}

    @pytest.mark.asyncio
    async def test_apply_change_pure_compute_mode(self):
        """engine / effects_queue 为 None → 纯计算，affected=0 且返回新 version。"""
        old, new = self._policies()
        result = await new.apply_change(old)
        assert result == {"affected": 0, "new_version": new.version()}

    @pytest.mark.asyncio
    async def test_apply_change_notifies_engine_and_queue(self):
        """受影响 Ticket → ticket_report(kind=progress) + enqueue reply effect。"""
        old, new = self._policies()
        open_tickets = [
            {"ticket_id": "t1", "workspace_id": 1, "title": "A",
             "mandate_matched_rules": [{"rule_id": "visual"}]},
            {"ticket_id": "t2", "workspace_id": 1, "title": "B",
             "mandate_matched_rules": [{"rule_id": "copy"}]},
        ]
        engine = MagicMock()
        queue = MagicMock()
        queue.enqueue = AsyncMock()

        # 注入活 Ticket 收集（避免依赖真实 DB）
        new._collect_open_tickets = lambda eng: open_tickets

        result = await new.apply_change(old, engine=engine, effects_queue=queue)

        assert result == {"affected": 1, "new_version": new.version()}
        # engine.tickets.ticket_report 只对 t1 调用，kind=progress
        report_args = engine.tickets.ticket_report.call_args
        assert report_args.args[0] == "t1"
        assert report_args.args[1]["kind"] == "progress"
        assert report_args.args[1]["message"].startswith("policy_changed:")
        # effects_queue.enqueue：kind=reply + payload（ticket_id/text/channel）
        enq_kwargs = queue.enqueue.await_args.kwargs
        assert enq_kwargs["kind"] == "reply"
        assert enq_kwargs["workspace_id"] == 1
        assert enq_kwargs["payload"]["ticket_id"] == "t1"
        assert enq_kwargs["payload"]["text"].startswith("⚠️ Policy 已更新")
        assert enq_kwargs["payload"]["channel"] == "sse"


# ============ TR-7.3 RoleModel 按角色路由 ============

class TestTR73RoleModels:
    def test_config_from_workspace(self):
        cfg = {"role_models": {
            "worker": {"provider": "dashscope", "model": "qwen-max",
                       "reasoning_effort": "high"},
            "orchestrator": {"provider": "openai", "model": "gpt-4o"},
        }}
        rc = role_model_config_from_workspace(cfg)
        assert rc.worker.model == "qwen-max"
        assert rc.worker.reasoning_effort == "high"
        assert rc.orchestrator.model == "gpt-4o"
        assert rc.reflector is None

    def test_config_from_empty_or_invalid(self):
        rc = role_model_config_from_workspace(None)
        assert rc == RoleModelConfig()
        rc2 = role_model_config_from_workspace(
            {"role_models": {"worker": {"provider": "p"}}}  # 缺 model
        )
        assert rc2.worker is None

    def test_role_models_are_pydantic(self):
        rm = RoleModel(provider="openai", model="gpt-4o", reasoning_effort="low")
        assert RoleModelConfig(orchestrator=rm).orchestrator.reasoning_effort == "low"

    def test_initialize_role_model_overrides_agent_model(self):
        agent = SimpleNamespace(model="default-model")
        ok = initialize_role_model(
            agent, RoleModel(provider="openai", model="gpt-4o", reasoning_effort="high"),
        )
        assert ok is True
        assert agent.model != "default-model"
        assert agent.reasoning_effort == "high"

    def test_initialize_role_model_failure_returns_false(self):
        class Locked:
            @property
            def model(self):  # 无 setter → setattr 必失败
                return "locked"

        assert initialize_role_model(
            Locked(), RoleModel(provider="openai", model="gpt-4o"),
        ) is False
        # 缺 model / agent 为 None 同样 False
        assert initialize_role_model(SimpleNamespace(), RoleModel(provider="p", model="")) is False
        assert initialize_role_model(None, RoleModel(provider="p", model="m")) is False


# ============ TR-7.4 EffectQueue per-kind 并发 + 指数退避 ============

class TestTR74EffectQueue:
    def test_six_kinds_all_have_concurrency(self):
        for kind in EFFECT_KINDS:
            assert kind in EFFECT_CONCURRENCY
            assert EFFECT_CONCURRENCY[kind] > 0

    def test_all_kinds_have_handlers(self):
        queue = EffectQueue(repo=MagicMock(spec=SuperAgentRepository))
        for kind in EFFECT_KINDS:
            assert hasattr(queue, f"_handle_{kind}")

    @pytest.mark.asyncio
    async def test_exponential_backoff_then_failed_after_4(self, mock_repo):
        """连续失败 3 次 → pending + 递增 due；第 4 次 → status=failed。"""
        queue = EffectQueue(repo=mock_repo)
        effect = MagicMock(id="e1", seq=1, attempts=0)

        dues: list = []
        for attempt in range(3):
            effect.attempts = attempt
            await queue._handle_failure("assessment", effect, RuntimeError("boom"))
        calls = mock_repo.update_effect_status.call_args_list
        assert len(calls) == 3
        for c in calls:
            assert c.args[2] == "pending"
        # 逐条断言 attempts=1/2/3 且 due 递增（指数退避）
        assert [c.kwargs["attempts"] for c in calls] == [1, 2, 3]
        dues = [c.kwargs["due"] for c in calls]
        assert all(d is not None for d in dues)
        assert dues[0] < dues[1] < dues[2]

        # 第 4 次失败 → failed
        effect.attempts = 3
        await queue._handle_failure("assessment", effect, RuntimeError("boom"))
        last = mock_repo.update_effect_status.call_args_list[-1]
        assert last.args[1] == "e1"
        assert last.args[2] == "failed"
        assert last.kwargs["attempts"] == 4
        assert "error" in last.kwargs["result"]

    @pytest.mark.asyncio
    async def test_successful_handler_marks_done(self, mock_repo):
        """handler 正常返回 → effect 标记 done。"""
        queue = EffectQueue(repo=mock_repo)
        effect = MagicMock(id="e2", seq=2, payload={"x": 1})
        effect.ticket_id = "t1"

        async def fake_handler(payload, eff):
            return {"ok": True}

        queue._handle_notice = fake_handler
        await queue._execute("notice", effect)
        last = mock_repo.update_effect_status.call_args_list[-1]
        assert last.args[1] == "e2"
        assert last.args[2] == "done"


# ============ TR-7.5 AgentDeliveryService 幂等投递 ============

class TestTR75Delivery:
    def setup_method(self):
        _DELIVERED_REQUESTS.clear()

    @pytest.mark.asyncio
    async def test_same_request_id_delivered_once(self):
        svc = AgentDeliveryService()
        inputs = [
            {"request_id": "r1", "text": "hello"},
            {"request_id": "r2", "text": "world"},
        ]
        first = await svc.deliver("t1", inputs)
        assert [i["request_id"] for i in first] == ["r1", "r2"]
        second = await svc.deliver("t1", inputs)
        assert second == []

    @pytest.mark.asyncio
    async def test_dedup_survives_service_restart(self):
        """模块级缓存：新实例（模拟重启后新 Session）同样去重。"""
        inputs = [{"request_id": "r1", "text": "hello"}]
        await AgentDeliveryService().deliver("t1", inputs)
        second = await AgentDeliveryService().deliver("t1", inputs)
        assert second == []

    @pytest.mark.asyncio
    async def test_repo_done_effect_dedup(self, mock_repo):
        """repo 扫描 sa_effect（kind=delivery, status=done）命中 request_id → 跳过。"""
        db = mock_repo.atomic.return_value.__enter__.return_value
        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(payload={"request_id": "r9"}),
        ]
        svc = AgentDeliveryService(repo=mock_repo)
        out = await svc.deliver("t1", [{"request_id": "r9", "text": "x"}])
        assert out == []

    @pytest.mark.asyncio
    async def test_input_without_request_id_always_delivered(self):
        inputs = [{"text": "no request id"}]
        svc = AgentDeliveryService()
        assert await svc.deliver("t1", inputs) == inputs
        assert await svc.deliver("t1", inputs) == inputs


# ============ TR-7.5 Notices coalescing + SSE 投递 ============

class TestTR75Notices:
    def setup_method(self):
        _PENDING_NOTICES.clear()

    @pytest.mark.asyncio
    async def test_coalescing_notice_overrides_same_name(self):
        assert await coalescing_notice("daily-summary", {"text": "v1"}) is False
        assert await coalescing_notice("daily-summary", {"text": "v2"}) is True
        assert _PENDING_NOTICES["daily-summary"] == {"text": "v2"}
        # 不同 name 互不影响
        assert await coalescing_notice("other", {"text": "x"}) is False
        assert _PENDING_NOTICES["daily-summary"]["text"] == "v2"
        assert _PENDING_NOTICES["other"]["text"] == "x"

    @pytest.mark.asyncio
    async def test_result_relay_publishes_sse(self):
        q = SSEBus.instance().subscribe()
        try:
            await result_relay("t1", "worker asks a question", channel="sse")
            evt = await asyncio.wait_for(q.get(), timeout=2.0)
            assert evt.event == "notice_result_relay"
            assert evt.data["ticket_id"] == "t1"
            assert evt.data["message"] == "worker asks a question"
            assert evt.data["channel"] == "sse"
        finally:
            SSEBus.instance().unsubscribe(q)

    @pytest.mark.asyncio
    async def test_followup_and_receipt_publish_sse(self):
        q = SSEBus.instance().subscribe()
        try:
            await followup_relay("t2", channel="sse")
            evt = await asyncio.wait_for(q.get(), timeout=2.0)
            assert evt.event == "notice_followup_relay"
            assert evt.data["ticket_id"] == "t2"

            await receipt_notice("t2", "m-42")
            evt2 = await asyncio.wait_for(q.get(), timeout=2.0)
            assert evt2.event == "notice_receipt"
            assert evt2.data["message_id"] == "m-42"
        finally:
            SSEBus.instance().unsubscribe(q)
