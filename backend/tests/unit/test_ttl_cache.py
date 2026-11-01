"""TTL 缓存的键必须把角色签名算进去——漏掉即等于脱敏失效（spec §4.3 安全不变量）。"""
import time

from app.core.cache import TTLCache, make_key


def test_get_after_ttl_returns_none():
    c = TTLCache(maxsize=8, ttl=0.05)
    c.set("k", "v")
    assert c.get("k") == "v"
    time.sleep(0.06)
    assert c.get("k") is None


def test_lru_eviction_keeps_recent():
    c = TTLCache(maxsize=2, ttl=60)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")        # a 变为最近使用
    c.set("c", 3)     # 应淘汰 b
    assert c.get("a") == 1 and c.get("c") == 3 and c.get("b") is None


def test_role_signature_changes_key():
    base = ("100", 7, "abcdef", "sha256ofsql")
    k_exempt = make_key(*base, "SEC_ADMIN")
    k_normal = make_key(*base, "VIEWER")
    assert k_exempt != k_normal


def test_same_roles_different_order_same_key():
    assert make_key("100", 7, "h", "s", *sorted(["A", "B"])) == make_key("100", 7, "h", "s", *sorted(["B", "A"]))
