"""``aliases_json`` 统一读写契约。

回归背景：本体导入把 ``{"_opl": {...}}`` 写进 ``meta_object_standard.aliases_json``
后，前端 ``(record.aliases || []).join(', ')`` 抛 ``join is not a function``，
Vue 渲染中断后二次报错成 ``Cannot set properties of null (setting '__vnode')``。
契约：任何形态读出来都必须是 ``list[str]``。
"""
from app.services.dataops import alias_json


class TestAliasesList:
    def test_none_yields_empty_list(self):
        assert alias_json.aliases_list(None) == []

    def test_plain_array_kept(self):
        assert alias_json.aliases_list(["物料", "商品"]) == ["物料", "商品"]

    def test_rich_structure_returns_list_part(self):
        value = {"list": ["物料"], "_opl": {"icon": "📦"}}
        assert alias_json.aliases_list(value) == ["物料"]

    def test_rich_structure_without_list_returns_empty(self):
        # 本体导入的既有形态：只有 _opl，没有 list
        assert alias_json.aliases_list({"_opl": {"icon": "📦"}}) == []

    def test_non_scalar_items_dropped(self):
        assert alias_json.aliases_list(["物料", {"x": 1}, None, 3]) == ["物料", "3"]

    def test_bool_is_not_alias(self):
        assert alias_json.aliases_list([True, "物料"]) == ["物料"]


class TestOplMeta:
    def test_plain_array_has_no_meta(self):
        assert alias_json.opl_meta(["物料"]) is None

    def test_rich_structure_exposes_meta(self):
        meta = {"icon": "📦", "datasources": ["d1"]}
        assert alias_json.opl_meta({"_opl": meta}) == meta


class TestWrite:
    def test_build_without_meta_stays_plain_array(self):
        # 历史契约优先：无扩展元数据时不引入富结构
        assert alias_json.build(["物料"]) == ["物料"]

    def test_build_with_meta_wraps(self):
        assert alias_json.build(["物料"], {"icon": "📦"}) == {
            "list": ["物料"], "_opl": {"icon": "📦"},
        }

    def test_with_aliases_preserves_meta(self):
        """对象编辑保存只改别名，不能静默丢本体元数据。"""
        original = {"_opl": {"icon": "📦", "source": "official/x.rdf"}}
        merged = alias_json.with_aliases(original, ["物料"])
        assert alias_json.aliases_list(merged) == ["物料"]
        assert alias_json.opl_meta(merged) == {"icon": "📦", "source": "official/x.rdf"}

    def test_with_aliases_on_plain_array(self):
        assert alias_json.with_aliases(["旧"], ["新"]) == ["新"]
