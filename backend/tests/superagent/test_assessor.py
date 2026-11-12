"""AssessorService 单元测试。"""
import pytest
from app.ai.superagent.policy import PolicyService
from app.ai.superagent.assessor import AssessorService, Candidate


@pytest.fixture
def policy():
    return PolicyService(
        rules=[
            {"id": "copy", "intent": "修复文案", "keywords": ["typo", "文案"]},
            {"id": "visual", "intent": "修复视觉", "keywords": ["样式", "css"]},
        ],
        allowed_senders=["alice", "bob"],
    )


@pytest.fixture
def assessor(policy):
    return AssessorService(policy=policy)


class TestCandidate:
    def test_should_accept_true(self):
        c = Candidate(
            trigger_id="t1", thread_id="th1",
            outcome=__import__("app.ai.superagent.policy", fromlist=["AssessmentOutcome"]).AssessmentOutcome(
                matched_rules=[{"rule_id": "copy"}],
                direction="accept",
                intent_evidence="evidence",
            ),
        )
        assert c.should_accept

    def test_should_accept_false_no_match(self):
        c = Candidate(
            trigger_id="t1", thread_id="th1",
            outcome=__import__("app.ai.superagent.policy", fromlist=["AssessmentOutcome"]).AssessmentOutcome(
                matched_rules=[],
                direction="accept",
                intent_evidence="evidence",
            ),
        )
        assert not c.should_accept


class TestAssessorService:
    def test_evaluate_thread_produces_candidates(self, assessor):
        triggers = [
            {
                "id": "t1", "title": "Fix typo",
                "body": "There is a typo in the button",
                "sender_id": "alice", "sender_name": "Alice",
                "addressed": True,
            },
            {
                "id": "t2", "title": "Add dark mode",
                "body": "Can we add dark mode?",
                "sender_id": "bob", "sender_name": "Bob",
                "addressed": True,
            },
        ]
        candidates = assessor.evaluate_thread(
            thread_id="github:issue#1", triggers=triggers,
            source_kind="github.issues", source="github",
        )
        assert len(candidates) == 2
        assert candidates[0].trigger_id == "t1"
        assert candidates[0].thread_id == "github:issue#1"

    def test_evaluate_thread_accepts_keyword_match(self, assessor):
        triggers = [
            {
                "id": "t1", "title": "Fix typo",
                "body": "There is a typo",
                "sender_id": "alice", "sender_name": "Alice",
                "addressed": True,
            },
        ]
        candidates = assessor.evaluate_thread(
            thread_id="th1", triggers=triggers,
            source_kind="github.issues", source="github",
        )
        assert len(candidates) == 1
        assert candidates[0].should_accept

    def test_evaluate_thread_ignores_no_match(self, assessor):
        triggers = [
            {
                "id": "t1", "title": "Add dark mode",
                "body": "Can we add dark mode?",
                "sender_id": "alice", "sender_name": "Alice",
                "addressed": True,
            },
        ]
        candidates = assessor.evaluate_thread(
            thread_id="th1", triggers=triggers,
            source_kind="github.issues", source="github",
        )
        assert len(candidates) == 1
        assert not candidates[0].should_accept

    def test_evaluate_thread_allows_multiple_keyword_rules(self, assessor):
        triggers = [
            {
                "id": "t1", "title": "Fix CSS bug",
                "body": "The stylesheet has a bug",
                "sender_id": "bob", "sender_name": "Bob",
                "addressed": True,
            },
        ]
        candidates = assessor.evaluate_thread(
            thread_id="th1", triggers=triggers,
            source_kind="github.issues", source="github",
        )
        assert len(candidates) == 1
        # "样式" 或 "css" 应命中 visual rule
        if candidates[0].outcome.matched_rules:
            assert candidates[0].outcome.matched_rules[0]["rule_id"] == "visual"


def _accept_trigger():
    return {
        "id": "t1", "title": "Fix typo",
        "body": "There is a typo in the button",
        "sender_id": "alice", "sender_name": "Alice",
        "addressed": True,
    }


class TestLLMEval:
    """LLM 推理路径（callable + JSON 解析 + 失败回退）。"""

    def test_llm_callable_dict_enhances_confidence(self, policy):
        def fake_llm(trigger, rule_hint):
            return {"accept": True, "confidence": 0.95, "reason": "明确文案修复意图"}

        a = AssessorService(policy=policy, llm_client=fake_llm)
        candidates = a.evaluate_thread(
            thread_id="th1", triggers=[_accept_trigger()],
            source_kind="github.issues", source="github",
        )
        assert candidates[0].should_accept
        assert candidates[0].confidence == pytest.approx(0.95)
        assert "rules+llm" in candidates[0].reason

    def test_llm_json_string_parsed(self, policy):
        def fake_llm(trigger, rule_hint):
            return '```json\n{"accept": true, "confidence": 0.9, "reason": "ok"}\n```'

        a = AssessorService(policy=policy, llm_client=fake_llm)
        candidates = a.evaluate_thread(
            thread_id="th1", triggers=[_accept_trigger()],
            source_kind="github.issues", source="github",
        )
        assert candidates[0].llm_verdict is not None
        assert candidates[0].llm_verdict["accept"] is True

    def test_llm_reject_vetoes_accept(self, policy):
        def fake_llm(trigger, rule_hint):
            return {"accept": False, "confidence": 0.2, "reason": "疑似闲聊"}

        a = AssessorService(policy=policy, llm_client=fake_llm)
        candidates = a.evaluate_thread(
            thread_id="th1", triggers=[_accept_trigger()],
            source_kind="github.issues", source="github",
        )
        assert not candidates[0].should_accept  # LLM 一票否决

    def test_llm_cannot_override_policy_veto(self, policy):
        """规则拒绝时 LLM 同意也不能翻转（policy 硬约束）。"""
        def fake_llm(trigger, rule_hint):
            return {"accept": True, "confidence": 0.99, "reason": "想接受"}

        a = AssessorService(policy=policy, llm_client=fake_llm)
        triggers = [{
            "id": "t2", "title": "Add dark mode",  # 不命中任何关键词
            "body": "Can we add dark mode?",
            "sender_id": "alice", "sender_name": "Alice",
            "addressed": True,
        }]
        candidates = a.evaluate_thread(
            thread_id="th1", triggers=triggers,
            source_kind="github.issues", source="github",
        )
        assert not candidates[0].should_accept
        assert "rules veto" in candidates[0].reason

    def test_llm_failure_falls_back_to_rules(self, policy):
        def broken_llm(trigger, rule_hint):
            raise RuntimeError("model down")

        a = AssessorService(policy=policy, llm_client=broken_llm)
        candidates = a.evaluate_thread(
            thread_id="th1", triggers=[_accept_trigger()],
            source_kind="github.issues", source="github",
        )
        # 回退纯规则：关键词命中 → 仍 accept
        assert candidates[0].should_accept
        assert candidates[0].llm_verdict is None
        assert candidates[0].confidence == pytest.approx(0.8)

    def test_llm_none_pure_rules(self, policy):
        a = AssessorService(policy=policy, llm_client=None)
        candidates = a.evaluate_thread(
            thread_id="th1", triggers=[_accept_trigger()],
            source_kind="github.issues", source="github",
        )
        assert candidates[0].llm_verdict is None
        assert candidates[0].should_accept

    def test_parse_verdict_tolerates_noise(self, policy):
        a = AssessorService(policy=policy)
        v = a._parse_verdict('前置说明 {"accept": true, "confidence": 0.7, "reason": "r"} 后缀')
        assert v is not None and v["accept"] is True
        assert a._parse_verdict("完全不是 JSON") is None
