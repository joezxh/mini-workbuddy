"""脱敏覆盖判定的真值表——发布门禁 5 与孪生编译共用（spec §4.1 第 4 步、§8.1 事实行）。

覆盖成立 = 非敏感 | 已豁免 | mask_rule 非空 | override 降级至 L1 以下
"""
import pytest

from app.services.ontology.ontology_publish_service import _SENSITIVE_PII, sensitive_covered


@pytest.mark.parametrize("pii,mask,ovr,exempt,expected", [
    ("L0", None, None, False, True),    # 非敏感
    (None,  None, None, False, True),   # 未标 pii_level 视为非敏感
    ("L2", None, None, False, False),   # 敏感且无 mask_rule → 未覆盖
    ("L3", "phone", None, False, True),  # 有 mask_rule → 覆盖
    ("L2", None, "L1", False, True),    # 显式降级 → 覆盖
    ("L2", None, "L2", False, False),   # 降级到仍敏感 → 不算覆盖
    ("L2", None, None, True, True),     # 豁免清单命中 → 覆盖
])
def test_truth_table(pii, mask, ovr, exempt, expected):
    assert sensitive_covered(pii, mask, ovr, exempt) is expected


def test_sensitive_set_is_L2_L3():
    assert _SENSITIVE_PII == {"L2", "L3"}
