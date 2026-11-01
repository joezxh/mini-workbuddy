"""pgvector halfvec 列类型（pgvector-py 低版本未内置）。

背景
----
实测环境（PostgreSQL 17 + pgvector 0.8.6）：

* HNSW 对 ``vector`` 类型的维度上限是 **2000**，而本项目生效维度为 **2048** → 不可用；
* IVFFlat 对 ``vector`` 同样受 2000 维限制（实测报
  ``column cannot have more than 2000 dimensions for ivfflat index``）；
* SP-GiST 的向量算子类在本构建中**不存在**；
* pgvector-py 0.3.0 的 SQLAlchemy 模块**没有** ``HalfVector``（0.3.1+ 才有）。

于是唯一可用路径是 **halfvec（半精度）+ HNSW**（HNSW 对 halfvec 的上限是 4000 维）：
以生成列 ``embedding::halfvec`` 存储量化副本，用 HNSW 索引做近似召回。

本类型只承担 **DDL 与列声明**：

* 写入不需要它（生成列由 DB 计算，永不失同步）；
* 查询走显式 SQL（``embedding_half <=> CAST(:q AS halfvec)``），
  因此无需自定义 bind/result processor —— 绑定参数是普通字符串，由 PG 完成类型转换。
"""
from sqlalchemy.types import UserDefinedType


class HalfVector(UserDefinedType):
    """pgvector ``halfvec(dim)`` 列类型。"""

    cache_ok = True

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = int(dim)

    def get_col_spec(self, **kw) -> str:
        return f"halfvec({self.dim})"

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"HalfVector({self.dim})"
