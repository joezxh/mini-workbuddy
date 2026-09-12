"""链式编排执行器测试"""
import pytest
from app.services.workflow.chain_executor import ChainExecutor


class TestChainExecutorHelpers:
    def test_evaluate_condition_true(self):
        ctx = {"steps": [{"status": "success"}]}
        assert ChainExecutor._evaluate_condition("$.steps[0].status == 'success'", ctx) is True

    def test_evaluate_condition_false(self):
        ctx = {"steps": [{"status": "failed"}]}
        assert ChainExecutor._evaluate_condition("$.steps[0].status == 'success'", ctx) is False

    def test_resolve_mapping_literal(self):
        mapping = {"mode": '"analysis"'}
        result = ChainExecutor._resolve_mapping(mapping, {})
        assert result == {"mode": "analysis"}

    def test_resolve_mapping_json_path(self):
        mapping = {"query": "$.user_input"}
        ctx = {"user_input": "hello"}
        result = ChainExecutor._resolve_mapping(mapping, ctx)
        assert result == {"query": "hello"}

    def test_json_path_get_simple(self):
        data = {"a": {"b": {"c": 42}}}
        assert ChainExecutor._json_path_get("$.a.b.c", data) == 42

    def test_json_path_get_array(self):
        data = {"steps": [{"output": {"result": "ok"}}]}
        assert ChainExecutor._json_path_get("$.steps[0].output.result", data) == "ok"

    def test_json_path_get_missing(self):
        data = {"a": 1}
        assert ChainExecutor._json_path_get("$.b.c", data) is None
