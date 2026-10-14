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
