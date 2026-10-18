"""向量维度适配工具。

``kms_segment.embedding`` 的列维度（``kb_collection.dimensions``）是可配置的，
而嵌入模型产出的向量长度未必恰好等于该维度（例如换用不同维度的模型、或模型
实际输出与声明不符）。写入 pgvector 时长度不符会直接报错::

    expected 768 dimensions, not 2048

故在**写入前**统一适配：过长截断、过短补零。补零只改变模长、不改变非零分量
的方向，在余弦相似度检索下是安全且常见的做法。
"""
from __future__ import annotations

from typing import Optional, Sequence

from loguru import logger
from sqlalchemy import text

# kms_segment.embedding 物理列维度缓存：key=id(engine)；-1/None 表示未约束。
# 维度仅在启动迁移时变更，进程内稳定，故按 engine 缓存避免每次构造重复查 pg_attribute。
_SEGMENT_DIM_CACHE: dict[int, Optional[int]] = {}


def get_segment_vector_dimension(engine) -> Optional[int]:
    """读取 ``kms_segment.embedding`` 物理列维度（``pg_attribute.atttypmod``）。

    pgvector 把 ``vector(n)`` 的列维度存放在 ``atttypmod``（无修饰时为 -1）。
    结果按 ``id(engine)`` 进程级缓存；读取失败或维度无效时返回 ``None``，
    调用方据此回落到 ``settings.EMBEDDING_DIMENSION``。

    这是「数据表定义的向量字段维度」的唯一真相来源：``startup_migrations`` 仅在
    空表时 ALTER 列，非空表保留旧维度（例如早期 nvidia env 的 2048），可能与当前
    向量化模型输出维度（例如 lm-studio 的 768）分歧——运行时按物理列对齐即可兼容。
    """
    if engine is None:
        return None
    if id(engine) in _SEGMENT_DIM_CACHE:
        return _SEGMENT_DIM_CACHE[id(engine)]
    dim: Optional[int] = None
    try:
        with engine.connect() as conn:
            # 按当前 schema 定位 kms_segment，避免多 schema（测试/迁移遗留）下同名表
            # 干扰；pgvector 把 vector(n) 的列维度存放在 atttypmod（无修饰时为 -1）。
            mod = conn.execute(text(
                "SELECT a.atttypmod FROM pg_attribute a "
                "JOIN pg_class c ON c.oid = a.attrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = current_schema() "
                "AND c.relname = 'kms_segment' AND a.attname = 'embedding'"
            )).scalar()
        if mod is not None and mod > 0:
            dim = int(mod)
    except Exception as exc:  # noqa: BLE001 - 读不到物理维度不阻断
        logger.warning(f"[Vector] 读取 kms_segment.embedding 物理维度失败: {exc}")
    _SEGMENT_DIM_CACHE[id(engine)] = dim
    return dim


def resolve_engine(source) -> Optional[object]:
    """从 ``Session`` / ``sessionmaker`` / ``Engine`` 中提取 SQLAlchemy engine。

    两类 ``PgVectorStore`` 构造入参不同（一个收 ``session_factory``，一个收
    ``Session``），统一此处解析出 engine，以便读取物理列维度。
    """
    if source is None:
        return None
    bind = getattr(source, "bind", None)
    if bind is not None:
        return bind
    # 已是 engine 本身（拥有 connect，但无 bind 属性）
    if callable(getattr(source, "connect", None)):
        return source
    return None


def segment_vector_dimension(db) -> Optional[int]:
    """返回 ``kms_segment.embedding`` 的目标对齐维度（物理列维度，回落全局配置）。

    所有直接写 ``kms_segment.embedding`` 的路径（``segment_service`` / ``index_mode``
    重嵌等）都应以此值作为 ``fit_vector_dimension`` 的目标，与 ``PGVectorStore`` 的
    写入/查询对齐保持一致，避免因「集合配置维度 ≠ 数据表物理维度」而写入/检索失败。
    """
    dim = get_segment_vector_dimension(resolve_engine(db))
    if dim:
        return dim
    from app.config import settings

    return getattr(settings, "EMBEDDING_DIMENSION", None)


def fit_vector_dimension(
    vector: Optional[Sequence[float]],
    dimension: Optional[int],
) -> list[float]:
    """把向量适配到目标维度：过长截断、过短补零、等长原样返回。

    :param vector: 原始向量；``None`` 视为空
    :param dimension: 目标维度；``None`` 或非正数表示不限制，原样返回
    """
    vec = list(vector or [])
    if not dimension or dimension <= 0:
        return vec
    if len(vec) == dimension:
        return vec
    if len(vec) > dimension:
        return vec[:dimension]
    return vec + [0.0] * (dimension - len(vec))
