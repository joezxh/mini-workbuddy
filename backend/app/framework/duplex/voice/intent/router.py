"""意图路由器。

根据用户语音转写文本，判断是否需要切换到其他 Agent。
首版采用轻量关键词规则分类，后续可替换为小模型分类。

电商场景意图规则：
- product_catalog: 商品查询（价格/库存/规格/型号）
- cross_border: 跨境贸易（海外/物流/关税/清关）
- marketing: 营销推广（优惠/促销/会员/积分）
- dispute_resolution: 纠纷处理（投诉/退款/质量问题/赔偿）
"""
from __future__ import annotations

import re
from typing import Optional

from ..plugins.base import AgentContext


# 电商/跨境/营销/纠纷场景意图规则
INTENT_RULES: dict[str, list[str]] = {
    "product_catalog": [
        r"(查|找|有没有|推荐).*(商品|产品|耳机|手机|衣服|鞋|价格|库存|规格|型号)",
        r"(多少|多少钱|什么价|价格|价位)",
        r"(有货|没货|缺货|现货)",
        r".*(耳机|手机|衣服|鞋|商品|产品).*(多少|价格|库存|规格|型号)",
    ],
    "cross_border": [
        r"(跨境|海外|国外|国际|美国|日本|欧洲|英国|澳洲|德国|法国)",
        r"(关税|清关|报关|海外仓|直邮|转运|国际物流|国际运费)",
        r"(几天到|多久能到|物流时效).*(海外|国外|跨境|国际)",
    ],
    "marketing": [
        r"(优惠|促销|折扣|打折|券|满减|秒杀|活动|双11|618|黑五)",
        r"(会员|积分|vip|等级|权益)",
        r"(推广|广告|投放|引流|获客)",
    ],
    "dispute_resolution": [
        r"(投诉|退款|退货|换货|差评|质量问题|坏了|破损|假货|虚假宣传)",
        r"(物流慢|没收到|丢件|不发货|发错货)",
        r"(欺骗|套路|霸王条款|客服态度差|服务差)",
        r"(赔偿|补偿|维权|12315|举报)",
    ],
}


class IntentRouter:
    """意图路由：根据用户文本判断应切换到哪个 Agent。

    遍历 INTENT_RULES，返回第一个命中的 Agent key。
    无命中返回 None，表示保持当前 Agent。
    """

    def __init__(self, rules: Optional[dict[str, list[str]]] = None) -> None:
        self._rules = rules or INTENT_RULES

    async def route(self, text: str, context: AgentContext) -> Optional[str]:
        """根据文本路由到目标 Agent。

        Args:
            text: 用户语音转写文本
            context: 当前上下文（可用于更智能的路由，如结合购物车状态）

        Returns:
            目标 Agent key，或 None 表示保持当前 Agent
        """
        for agent_key, patterns in self._rules.items():
            for pat in patterns:
                if re.search(pat, text):
                    return agent_key
        return None
