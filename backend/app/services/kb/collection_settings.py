"""知识库检索设置（spec §10.5 设置面板）。

``kb_collection.retrieval_settings`` 承载 embedding/rerank 模型与检索参数。
本模块只负责「落库 + 判定需要哪些后台重灌作业」，**不执行**长任务 ——
作业由路由用 ``job_runner.run_in_background`` + 独立 Session 启动，避免
绑定请求生命周期。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from app.models.kb.kb_collection import KbCollection
from app.services.kb.embedding_config import resolve_embedding_config
from app.services.kb.index_mode import (
    ECONOMY,
    HIGH_QUALITY,
    downgrade_to_economy,
    resolve_index_mode,
    resolve_knowledge_id,
)

# 允许落库的检索设置键（其余键一律拒绝，避免配置面漂移）
SETTING_KEYS = (
    "embedding_provider",
    "embedding_model",
    "embedding_dimensions",
    "rerank_provider",
    "rerank_model",
    "top_k",
    "score_threshold",
)


def get_retrieval_settings(db, collection: str) -> dict:
    """读取检索设置；collection 不存在返回空字典。"""
    coll = db.execute(
        select(KbCollection).where(KbCollection.name == collection)
    ).scalar_one_or_none()
    return dict(coll.retrieval_settings or {}) if coll else {}


def apply_collection_settings(db, collection: str, payload: dict) -> dict:
    """合并检索设置并处理索引模式；返回 ``{retrieval_settings, index_mode, jobs}``。

    ``jobs`` 是需要后台执行的重灌作业列表（``reembed`` / ``upgrade_index``），
    由调用方按序启动。换嵌入模型触发 ``reembed``（覆盖全部向量）；
    economy → high_quality 触发 ``upgrade_index``（仅回填 NULL 并翻标志）。

    未知键直接失败；嵌入维度与 collection 不一致按 D19 拒绝（物理 vector 列维度固定）。
    """
    coll = db.execute(
        select(KbCollection).where(KbCollection.name == collection)
    ).scalar_one_or_none()
    if coll is None:
        raise ValueError(f"collection 不存在: {collection}")

    unknown = set(payload) - set(SETTING_KEYS) - {"index_mode"}
    if unknown:
        raise ValueError(f"未知设置项: {sorted(unknown)}；可选 {list(SETTING_KEYS)}")

    settings = dict(coll.retrieval_settings or {})
    # 未显式配置时，生效的是全局默认 provider/model（现有向量即由它产出）；
    # 以此为基准比较，避免首次配置触发一次无谓的全量重灌。
    default = resolve_embedding_config(None)
    prev = (
        settings.get("embedding_provider") or default.provider,
        settings.get("embedding_model") or default.model,
    )
    new = (
        payload.get("embedding_provider") or prev[0],
        payload.get("embedding_model") or prev[1],
    )
    embedding_changed = new != prev

    for key in SETTING_KEYS:
        if payload.get(key) is not None:
            settings[key] = payload[key]

    dims: Optional[int] = payload.get("embedding_dimensions")
    if dims is not None and dims != coll.dimensions:
        raise ValueError(
            f"嵌入维度 {dims} 与 collection {coll.dimensions} 不一致"
            f"（D19：物理 vector 列维度固定，需重建 collection）"
        )
    coll.retrieval_settings = settings

    jobs: list[str] = []
    current = resolve_index_mode(db, collection)
    wanted = payload.get("index_mode")
    if wanted == ECONOMY and current != ECONOMY:
        kid = resolve_knowledge_id(collection)
        if kid is None:
            raise ValueError(f"无法从 collection 解析知识库: {collection}")
        downgrade_to_economy(db, kid)  # 仅翻标志，即时生效
        current = ECONOMY
    elif wanted == HIGH_QUALITY and current != HIGH_QUALITY:
        jobs.append("upgrade_index")

    if embedding_changed:
        jobs.append("reembed")

    db.commit()
    return {"retrieval_settings": settings, "index_mode": current, "jobs": jobs}
