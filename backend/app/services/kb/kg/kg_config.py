"""图谱知识库 KB 级配置（P3）。

配置**不新增列**，存于 ``kms_knowledge.pipeline_config["graph"]``（spec §6.4），
与既有 ``clean`` / ``chunker`` / ``index`` 编排键并列，共用同一套读写与校验入口。

取值一律走 :func:`resolve_graph_config`：缺省补齐、越界钳制、类型纠错，
**不抛错**——配置面板的脏值不应让检索或构建直接 500（与 spec「降级但显式」一致）。
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.wiki.wiki_knowledge import WikiKnowledge

GRAPH_CONFIG_KEY = "graph"

# 最近一次构建的运行元信息（不新增列，与 graph 配置并列存放）
BUILD_META_KEY = "graph_build"

DEFAULTS: dict[str, Any] = {
    # ── 抽取 ──
    "extractor_type": "llm",          # llm | rule（当前仅 llm）
    "model_spec": None,               # {provider, model}；None = 走系统默认
    "schema_source": "free_text",     # none | cdm | free_text
    "catalog_id": None,               # schema_source=cdm 时圈定的 CDM 目录
    "schema": "",                     # schema_source=free_text 时的自由文本约束
    "concurrency_count": 8,
    "timeout_seconds": 60,
    # ── 检索 ──
    "use_graph_retrieval": True,
    "graph_entity_top_k": 10,
    "graph_triple_top_k": 10,
    "graph_max_nodes": 10000,
    "graph_top_k": 20,
    "graph_weight": 1.0,
    "ppr_damping": 0.85,
}

# 取值范围（越界钳制，不报错）
_BOUNDS: dict[str, tuple[float, float]] = {
    "concurrency_count": (1, 1000),
    "timeout_seconds": (0, 600),
    "graph_entity_top_k": (1, 200),
    "graph_triple_top_k": (1, 200),
    "graph_max_nodes": (100, 100000),
    "graph_top_k": (1, 200),
    "graph_weight": (0.0, 10.0),
    "ppr_damping": (0.1, 0.99),      # networkx pagerank 要求 <1
}

_BOOL_KEYS = ("use_graph_retrieval",)
_INT_KEYS = (
    "concurrency_count", "timeout_seconds", "graph_entity_top_k",
    "graph_triple_top_k", "graph_max_nodes", "graph_top_k", "catalog_id",
)
_STR_KEYS = ("extractor_type", "schema_source", "schema")


def _clamp(key: str, value: Any) -> Any:
    bounds = _BOUNDS.get(key)
    try:
        if key in _INT_KEYS:
            v = int(value)
        else:
            v = float(value)
    except (TypeError, ValueError):
        return DEFAULTS.get(key)
    if bounds:
        lo, hi = bounds
        v = max(lo, min(hi, v))
    return int(v) if key in _INT_KEYS else v


def resolve_graph_config(kb: Optional[WikiKnowledge]) -> dict:
    """读取并规整图谱配置（缺省补齐 + 越界钳制 + 未知键忽略）。"""
    raw: dict = {}
    if kb is not None:
        cfg = getattr(kb, "pipeline_config", None) or {}
        if isinstance(cfg, dict):
            g = cfg.get(GRAPH_CONFIG_KEY)
            if isinstance(g, dict):
                raw = g

    out = dict(DEFAULTS)
    for key in DEFAULTS:
        if key not in raw or raw[key] is None:
            continue
        val = raw[key]
        if key in _BOOL_KEYS:
            out[key] = bool(val)
        elif key in _STR_KEYS:
            out[key] = str(val) if val is not None else DEFAULTS[key]
        elif key in _BOUNDS:
            out[key] = _clamp(key, val)
        else:
            out[key] = val  # model_spec 等自由结构原样透传

    # 枚举收敛：非法值回落默认，避免下游分支膨胀
    if out["schema_source"] not in ("none", "cdm", "free_text"):
        out["schema_source"] = DEFAULTS["schema_source"]
    if out["extractor_type"] not in ("llm", "rule"):
        out["extractor_type"] = DEFAULTS["extractor_type"]
    return out


def get_graph_config(db: Session, knowledge_id: int) -> dict:
    kb = db.get(WikiKnowledge, knowledge_id)
    return resolve_graph_config(kb)


def save_graph_config(db: Session, knowledge_id: int, patch: dict) -> dict:
    """合并写入图谱配置（只动 ``graph`` 子键，其余编排键原样保留）。"""
    kb = db.get(WikiKnowledge, knowledge_id)
    if kb is None:
        raise ValueError(f"知识库不存在: {knowledge_id}")

    current = resolve_graph_config(kb)
    current.update({k: v for k, v in (patch or {}).items() if k in DEFAULTS})
    current = resolve_graph_config(
        type("_K", (), {"pipeline_config": {GRAPH_CONFIG_KEY: current}})()
    )

    cfg = dict(getattr(kb, "pipeline_config", None) or {})
    cfg[GRAPH_CONFIG_KEY] = current
    kb.pipeline_config = cfg
    db.commit()
    db.refresh(kb)
    return current


def get_build_meta(db: Session, knowledge_id: int) -> dict:
    """读取最近一次图谱构建的运行元信息（无记录时返回空 dict）。"""
    kb = db.get(WikiKnowledge, knowledge_id)
    if kb is None:
        return {}
    cfg = getattr(kb, "pipeline_config", None) or {}
    if not isinstance(cfg, dict):
        return {}
    meta = cfg.get(BUILD_META_KEY)
    return meta if isinstance(meta, dict) else {}


def save_build_meta(db: Session, knowledge_id: int, meta: dict) -> None:
    """写入最近一次图谱构建的运行元信息（只动 ``graph_build`` 子键）。"""
    kb = db.get(WikiKnowledge, knowledge_id)
    if kb is None:
        return
    cfg = dict(getattr(kb, "pipeline_config", None) or {})
    cfg[BUILD_META_KEY] = dict(meta or {})
    kb.pipeline_config = cfg
    db.commit()
