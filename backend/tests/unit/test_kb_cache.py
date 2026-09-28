"""KB 缓存层单测（Phase 3 T2）：命中复用 + 显式失效，无 Redis 时内存回退。"""

from app.services.kb import kb_cache


def test_cached_reuses_result_and_invalidates(monkeypatch):
    calls = {"n": 0}

    @kb_cache.cached(key_builder=lambda: kb_cache.cache_key("t", 1))
    def load():
        calls["n"] += 1
        return {"v": calls["n"]}

    kb_cache.invalidate(kb_cache.cache_key("t"))
    assert load()["v"] == 1
    assert load()["v"] == 1          # 命中缓存，未回源
    assert calls["n"] == 1

    kb_cache.invalidate(kb_cache.cache_key("t"))  # 写后失效
    assert load()["v"] == 2          # 失效后回源
    assert calls["n"] == 2


def test_cache_key_and_prefix_invalidation(monkeypatch):
    @kb_cache.cached(key_builder=lambda: kb_cache.cache_key("kb", "a"))
    def a():
        return {"x": 1}

    @kb_cache.cached(key_builder=lambda: kb_cache.cache_key("kb", "b"))
    def b():
        return {"x": 2}

    kb_cache.invalidate(kb_cache.cache_key("kb"))
    assert a()["x"] == 1 and b()["x"] == 2
    kb_cache.invalidate("kms:kb")     # 按前缀失效两者
    assert kb_cache._cache_get(kb_cache.cache_key("kb", "a")) is None
    assert kb_cache._cache_get(kb_cache.cache_key("kb", "b")) is None


def test_redis_unavailable_falls_back_to_memory(monkeypatch):
    """Redis 不可用时不得抛错，回退内存缓存。"""
    monkeypatch.setattr(kb_cache, "_redis_client", lambda: None)
    kb_cache._cache_set("kms:probe", "{}", 60)
    assert kb_cache._cache_get("kms:probe") == "{}"
