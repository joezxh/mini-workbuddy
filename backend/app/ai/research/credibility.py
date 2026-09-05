"""可信度评分（纯规则，无 LLM 调用）

对检索来源按「来源类型权重 + 交叉命中加权」给出 0-1 分值：
- 来源类型：官方/权威库（如 .gov / 法条库 / 学校 / 机构）高于一般网页
- 交叉命中：同一来源被多个子问题命中时加权，代表信息被多方印证
"""
from __future__ import annotations

from typing import Dict, Iterable, List
from urllib.parse import urlparse


# 来源域名类型权重基线
_AUTHORITY_KEYWORDS = ("gov", "edu", "org", "court", "law", "ncov", "gov.cn", "chinacourt")
_HIGH_TRUST_TLDS = (".gov", ".edu", ".gov.cn", ".edu.cn")


def _domain_type(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return "web"
    if any(netloc.endswith(t) for t in _HIGH_TRUST_TLDS):
        return "official"
    if any(k in netloc for k in _AUTHORITY_KEYWORDS):
        return "authority"
    if url.startswith("kb:"):
        return "kb"  # 内部知识库来源
    return "web"


_TYPE_WEIGHT = {"official": 0.95, "authority": 0.85, "kb": 0.9, "web": 0.6}


def score_source(url: str, title: str = "", cross_hits: int = 1) -> float:
    """对单条来源评分。cross_hits=该来源被多少个子问题命中。"""
    base = _TYPE_WEIGHT.get(_domain_type(url), 0.6)
    # 交叉命中加权（最多 +0.15）
    boost = min(0.15, 0.05 * max(0, cross_hits - 1))
    return round(min(1.0, base + boost), 4)


def score_sources(
    sources: Iterable[Dict[str, str]],
    cross_map: Dict[str, int],
) -> List[Dict[str, float]]:
    """批量评分，返回 [(source, score)]。

    sources: 每个元素含 url/title；cross_map: url -> 命中子问题数。
    """
    out: List[Dict[str, float]] = []
    for s in sources:
        url = s.get("url", "")
        out.append({
            "url": url,
            "title": s.get("title", ""),
            "credibility": score_source(url, s.get("title", ""), cross_map.get(url, 1)),
        })
    return out
