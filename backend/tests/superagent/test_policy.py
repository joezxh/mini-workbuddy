"""PolicyService 单元测试。"""
import pytest
from app.ai.superagent.policy import (
    PolicyService, AdmissionRule, AssessmentOutcome, DEFAULT_RULES,
)


class TestAdmissionRule:
    def test_default_admission_contains_all_expected(self):
        svc = PolicyService()
        kinds = {r.kind for r in svc.admission_rows}
        assert "github.issues" in kinds
        assert "github.pulls" in kinds
        assert "github.comments" in kinds
        assert "github.ci" in kinds
        assert "feishu.group" in kinds
        assert "feishu.dm" in kinds

    def test_admission_github_ci_default_inferred(self):
        svc = PolicyService()
        ci_rows = [r for r in svc.admission_rows if r.kind == "github.ci"]
        assert len(ci_rows) == 1
        assert ci_rows[0].value == "inferred"


class TestPolicyVersion:
    def test_version_is_stable_for_same_config(self):
        svc1 = PolicyService()
        svc2 = PolicyService()
        assert svc1.version() == svc2.version()

    def test_version_changes_when_rules_change(self):
        svc1 = PolicyService(rules=[{"id": "a", "intent": "A", "keywords": ["a"]}])
        svc2 = PolicyService(rules=[{"id": "b", "intent": "B", "keywords": ["b"]}])
        assert svc1.version() != svc2.version()


class TestGate:
    def test_gate_github_ci_no_sender_inferred(self):
        svc = PolicyService()
        rule = svc.gate(
            source_kind="github.ci", source="ci-build",
            sender_id=None, addressed=False,
        )
        assert rule.value == "inferred"

    def test_gate_explicit_sender_addressed(self):
        svc = PolicyService(allowed_senders=["alice"])
        rule = svc.gate(
            source_kind="github.issues", source="issue#1",
            sender_id="alice", addressed=True,
        )
        assert rule.value == "explicit"

    def test_gate_unlisted_sender_addressed(self):
        svc = PolicyService()
        rule = svc.gate(
            source_kind="github.issues", source="issue#1",
            sender_id="bob", addressed=True,
        )
        assert rule.value == "explicit"

    def test_gate_unlisted_sender_unaddressed_ignore(self):
        svc = PolicyService()
        rule = svc.gate(
            source_kind="github.issues", source="issue#1",
            sender_id="bob", addressed=False,
        )
        assert rule.value == "ignore"


class TestAssess:
    def test_assess_accept_with_keyword_match(self):
        svc = PolicyService(
            rules=[{"id": "copy", "intent": "修复文案", "keywords": ["typo"]}],
            allowed_senders=["alice"],
        )
        outcome = svc.assess(
            source_kind="github.issues", source="issue#1",
            sender_id="alice", addressed=True,
            trigger_text="There's a typo on the login page",
        )
        assert len(outcome.matched_rules) >= 1
        assert outcome.direction == "accept"
        assert outcome.can_accept()

    def test_assess_ignore_when_no_keyword_match(self):
        svc = PolicyService(
            rules=[{"id": "copy", "intent": "修复文案", "keywords": ["typo"]}],
            allowed_senders=["alice"],
        )
        outcome = svc.assess(
            source_kind="github.issues", source="issue#1",
            sender_id="alice", addressed=True,
            trigger_text="Please add dark mode support",
        )
        assert outcome.direction == "ignore"
        assert not outcome.can_accept()

    def test_assess_ignore_when_no_text(self):
        svc = PolicyService(allowed_senders=["alice"])
        outcome = svc.assess(
            source_kind="github.issues", source="issue#1",
            sender_id="alice", addressed=True,
            trigger_text="",
        )
        assert outcome.direction == "ignore"
        assert not outcome.intent_evidence

    def test_assess_ignore_unlisted_unaddressed(self):
        svc = PolicyService(rules=[{"id": "copy", "intent": "修复文案", "keywords": ["typo"]}])
        outcome = svc.assess(
            source_kind="github.issues", source="issue#1",
            sender_id="bob", addressed=False,
            trigger_text="There's a typo here",
        )
        # 准入 gate 为 ignore → direction=ignore
        assert outcome.direction == "ignore"


class TestAssessmentOutcome:
    def test_can_accept_true(self):
        outcome = AssessmentOutcome(
            matched_rules=[{"rule_id": "x"}],
            direction="accept",
            intent_evidence="has evidence",
        )
        assert outcome.can_accept()

    def test_can_accept_false_no_match(self):
        outcome = AssessmentOutcome(
            matched_rules=[],
            direction="accept",
            intent_evidence="has evidence",
        )
        assert not outcome.can_accept()

    def test_can_accept_false_no_evidence(self):
        outcome = AssessmentOutcome(
            matched_rules=[{"rule_id": "x"}],
            direction="accept",
            intent_evidence="",
        )
        assert not outcome.can_accept()


class TestChangesFrom:
    def test_changes_detects_removed_rule(self):
        svc = PolicyService(rules=[{"id": "new", "intent": "new", "keywords": ["new"]}])
        changes = svc.changes_from([{"id": "old", "intent": "old", "keywords": ["old"]}])
        assert len(changes) >= 1
        assert any("removed" in c["reason"].lower() or "added" in c["reason"].lower() for c in changes)

    def test_changes_empty_when_same_rules(self):
        old = [{"id": "a", "intent": "A", "keywords": ["a"]}]
        svc = PolicyService(rules=old)
        changes = svc.changes_from(old)
        assert changes == []
