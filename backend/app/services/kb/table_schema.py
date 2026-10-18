"""表格知识库的**列定义（schema）**与导入格式校验。

唯一存储：``kms_collection.schema_config``，形状为
``[{"name": str, "type": "string"|"number"|"boolean", "enabled": bool,
   "embedding": bool, "filterable": bool}]``，其中 ``embedding=True`` 的字段
**可为 1~N 个**：它们按字段顺序组合成「向量化内容」（每段一行、逗号间隔的 CSV 行），
向量检索依赖该内容；其余列进 ``kb_segment.metadata`` 作为可过滤字段。

导入语义（表格文件处理时）：
* 知识库**尚无**列定义 → 按文件表头**自动生成**并落库（**默认全部字段**均为向量化
  字段，即「所有字段组合为向量化内容」）；
* 知识库**已有**列定义 → 按定义校验文件（缺列 / 多列 / 取值类型），不一致即抛
  :class:`TableSchemaMismatch`，调用方据此拒绝导入（**不落任何数据**）。

设计要点：
* 校验只认「列名集合 + 取值类型」，不要求列顺序一致（不同导出工具列序常变）；
* 取值统一规范化为 JSON 安全标量（``str`` / ``int`` / ``float`` / ``bool``），
  顺带消除 xlsx 读出的 ``datetime`` 直接进 JSONB 会炸的隐患；
* ``ensure_collection_row`` 兜底补建 ``kms_collection`` 行——HTTP 建知识库的路径
  并不会建集合行，列定义需要一个稳定的落点。
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb.kb_collection import KbCollection
from app.services.kb.index_mode import resolve_knowledge_id

# 列类型（与前端「字段定义」的 文本/数字/布尔 对齐）
FIELD_TYPES = ("string", "number", "boolean")

# 类型推断的采样行数：够覆盖类型特征，又不至于全表扫描
_SAMPLE_ROWS = 200

_BOOL_TRUE = {"true", "1", "yes", "y", "t", "on", "是", "真"}
_BOOL_FALSE = {"false", "0", "no", "n", "f", "off", "否", "假"}


class TableSchemaMismatch(ValueError):
    """表格文件与知识库列定义不一致。

    ``code`` 供前端做多语言提示映射；``extra`` 携带缺列/多列/行号等结构化细节。
    """

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra: dict[str, Any] = extra

    def as_detail(self) -> dict:
        """转成 FastAPI ``HTTPException(detail=...)`` 可直接使用的结构。"""
        return {"code": self.code, "message": self.message, **self.extra}


# ── 取值规范化 ────────────────────────────────────────────────────────────

def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _to_number(value: Any) -> float | int:
    if isinstance(value, bool):
        raise ValueError(f"布尔值 {value!r} 不是数字")
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    try:
        num = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{value!r} 不是数字") from exc
    return int(num) if num.is_integer() else num


def _to_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _BOOL_TRUE:
        return True
    if text in _BOOL_FALSE:
        return False
    raise ValueError(f"{value!r} 不是布尔值")


def coerce_value(value: Any, field_type: str) -> Any:
    """按列类型把取值规范化为 JSON 安全标量；类型不符抛 :class:`ValueError`。

    空值统一归一为 ``""``（不参与类型判定），避免 xlsx 的 ``None``/空单元格
    直接进 JSONB 时类型不稳。
    """
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if _is_empty(value):
        return ""
    if field_type == "boolean":
        return _to_boolean(value)
    if field_type == "number":
        return _to_number(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def infer_type(values: Iterable[Any]) -> str:
    """按采样值推断列类型；布尔/数字混排或出现文本则回落 ``string``。"""
    kinds: set[str] = set()
    for value in values:
        if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
            kinds.add("string")
            continue
        if _is_empty(value):
            continue
        if isinstance(value, bool):
            kinds.add("boolean")
            continue
        if isinstance(value, (int, float)):
            kinds.add("number")
            continue
        text = str(value).strip().lower()
        if text in _BOOL_TRUE or text in _BOOL_FALSE:
            kinds.add("boolean")
            continue
        try:
            _to_number(text)
        except ValueError:
            kinds.add("string")
        else:
            kinds.add("number")
    if kinds <= {"number"}:
        return "number"
    if kinds == {"boolean"}:
        return "boolean"
    return "string"


# ── 列定义读写 ────────────────────────────────────────────────────────────

def ensure_collection_row(
    db: Session,
    collection: str,
    *,
    tenant_id: Optional[int] = None,
) -> KbCollection:
    """取 ``kms_collection`` 行，不存在则补建（HTTP 建知识库不建集合行的兜底）。"""
    coll = db.execute(
        select(KbCollection).where(KbCollection.name == collection)
    ).scalar_one_or_none()
    if coll is not None:
        return coll

    from app.config import settings

    kid = resolve_knowledge_id(collection)
    if kid is not None:
        from app.models.wiki.wiki_knowledge import WikiKnowledge

        # 知识库不存在时不写 FK，避免整条链路因外键失败
        if db.get(WikiKnowledge, kid) is None:
            kid = None
    coll = KbCollection(
        tenant_id=tenant_id,
        name=collection,
        dimensions=settings.GPUSTACK_EMBEDDING_DIMENSION,
        knowledge_id=kid,
    )
    db.add(coll)
    db.flush()
    return coll


def normalize_fields(raw: Any) -> list[dict]:
    """清洗列定义：去空白、去重名、类型白名单化。

    ``embedding=True`` 的字段**可为 1~N 个**（组合成向量化内容），不再强制单选。
    """
    if not isinstance(raw, (list, tuple)):
        return []
    fields: list[dict] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        ftype = str(item.get("type") or "string").strip().lower()
        if ftype not in FIELD_TYPES:
            ftype = "string"
        # order 排序序号：缺失时按出现顺序（索引）兜底，保证任何写入路径都可控
        try:
            order = int(item.get("order", idx))
        except (TypeError, ValueError):
            order = idx
        fields.append(
            {
                "name": name,
                "type": ftype,
                "enabled": bool(item.get("enabled", True)),
                "embedding": bool(item.get("embedding", False)),
                "filterable": bool(item.get("filterable", True)),
                "order": order,
            }
        )
    # 向量化字段允许多选（1~N 个组合成向量化内容），不再截断为单个；
    # 按 order 稳定排序，使向量化内容拼接、表格条目列序与字段定义序号一致
    fields.sort(key=lambda f: (f["order"], f["name"]))
    return fields


def embedding_fields(fields: list[dict]) -> list[str]:
    """取「向量化字段组合」：``embedding=True`` 的字段名，按字段定义顺序。

    组合顺序即 CSV 行的列序，决定向量化内容（每段一行、逗号间隔）。
    命名为 ``embedding_fields`` 而非 ``embed_fields``，避免与
    :func:`resolve_import_schema` 的同名入参冲突。
    """
    return [
        str(f["name"])
        for f in normalize_fields(fields)
        if f.get("embedding") and f.get("enabled", True)
    ]


def filterable_fields(fields: list[dict]) -> list[str]:
    """取可过滤字段名：非向量化字段（进 ``kb_segment.metadata`` 供过滤）。"""
    return [
        str(f["name"])
        for f in normalize_fields(fields)
        if f.get("filterable", True) and f.get("enabled", True)
    ]


def get_schema_fields(db: Session, collection: str) -> list[dict]:
    """读取列定义；未定义返回空列表（触发导入时的自动定义）。"""
    coll = db.execute(
        select(KbCollection).where(KbCollection.name == collection)
    ).scalar_one_or_none()
    return normalize_fields(coll.schema_config) if coll else []


def set_schema_fields(db: Session, collection: str, fields: Any) -> list[dict]:
    """落库列定义（**至少**一个向量化字段，可多个），返回规范化结果。"""
    normalized = normalize_fields(fields)
    if not normalized:
        raise TableSchemaMismatch("table_schema_empty", "字段定义不能为空")
    embedded = embedding_fields(normalized)
    if not embedded:
        raise TableSchemaMismatch(
            "table_schema_embed_required", "至少需要一个向量化字段",
            expected=1, actual=len(embedded),
        )
    coll = ensure_collection_row(db, collection)
    coll.schema_config = normalized
    db.commit()
    return normalized


def infer_fields(
    columns: list[str],
    rows: list[dict],
    *,
    embed_field: Optional[str] = None,
    embed_fields: Optional[list[str]] = None,
) -> list[dict]:
    """按文件表头 + 采样值推断列定义。

    向量化字段（``embedding=True``）的取值优先级：
    1. 显式传入 ``embed_fields``（字段组合，支持 1~N 个）；
    2. 兼容旧参数 ``embed_field``（单字段）；
    3. **缺省全部字段**均为向量化字段——满足「按文件记录格式自动生成字段定义，
       默认所有字段组合为向量化内容」。
    """
    sample = rows[:_SAMPLE_ROWS]
    fields = [
        {
            "name": name,
            "type": infer_type(row.get(name) for row in sample),
            "enabled": True,
            "embedding": False,
            "filterable": True,
        }
        for name in columns
    ]
    if not fields:
        return []

    targets: list[str] = []
    if embed_fields:
        targets = [f for f in embed_fields if f in columns]
    if not targets and embed_field:
        targets = [embed_field] if embed_field in columns else []
    if not targets:
        # 缺省：全部字段组合为向量化内容
        targets = [f["name"] for f in fields]
    target_set = set(targets)
    for field in fields:
        field["embedding"] = field["name"] in target_set
        # 向量化字段已进 content，其余字段进 metadata 供过滤
        field["filterable"] = field["name"] not in target_set
    return fields


def _union_keys(rows: list[dict]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def validate_rows(
    fields: list[dict],
    rows: list[dict],
    *,
    columns: Optional[list[str]] = None,
) -> list[dict]:
    """按列定义校验并规范化行数据；不一致抛 :class:`TableSchemaMismatch`。

    列序不参与判定（不同导出工具列序常变），只看列名集合与取值类型。
    """
    defined = [f for f in normalize_fields(fields) if f["enabled"]]
    if not defined:
        raise TableSchemaMismatch("table_schema_empty", "知识库尚未定义表格列")

    names = [f["name"] for f in defined]
    file_columns = list(columns) if columns is not None else _union_keys(rows)
    missing = [name for name in names if name not in file_columns]
    extra = [name for name in file_columns if name not in names]
    if missing or extra:
        raise TableSchemaMismatch(
            "table_schema_mismatch", "表格列与知识库字段定义不一致",
            missing=missing, extra=extra, expected=names,
        )

    by_name = {f["name"]: f for f in defined}
    normalized: list[dict] = []
    for index, row in enumerate(rows):
        item: dict[str, Any] = {}
        for name in file_columns:
            field_type = by_name[name]["type"]
            try:
                item[name] = coerce_value(row.get(name), field_type)
            except ValueError as exc:
                raise TableSchemaMismatch(
                    "table_cell_type_mismatch", str(exc),
                    row=index + 1, column=name, expected=field_type,
                ) from exc
        normalized.append(item)
    return normalized


def resolve_import_schema(
    db: Session,
    collection: str,
    columns: list[str],
    rows: list[dict],
    *,
    embed_field: Optional[str] = None,
    embed_fields: Optional[list[str]] = None,
    tenant_id: Optional[int] = None,
    persist: bool = True,
) -> dict:
    """导入前的列定义决策：**无定义则自动定义，有定义则校验**。

    返回 ``{"fields", "created", "embed_fields", "embed_field", "rows"}``：
    ``embed_fields`` 是向量化字段组合（1~N 个，按字段定义顺序 —— 即每段 CSV 行的
    列序与向量化内容），``embed_field`` 为其中首个（兼容旧调用方）；``rows`` 已按
    定义规范化；列不匹配/类型不符时抛 :class:`TableSchemaMismatch`（拒绝导入）。
    """
    fields = get_schema_fields(db, collection)
    created = False
    if not fields:
        fields = infer_fields(
            columns, rows, embed_field=embed_field, embed_fields=embed_fields
        )
        if not fields:
            raise TableSchemaMismatch("table_schema_empty", "表格文件没有可用表头")
        if persist:
            fields = set_schema_fields(db, collection, fields)
        created = True

    defined_names = {f["name"] for f in fields if f.get("enabled", True)}
    targets: list[str] = []
    if embed_fields:
        targets = [name for name in embed_fields if name in defined_names]
    if not targets and embed_field and embed_field in defined_names:
        targets = [embed_field]
    if not targets:
        targets = embedding_fields(fields)
    if not targets:
        targets = [f["name"] for f in fields if f.get("enabled", True)][:1]
    if not targets:
        raise TableSchemaMismatch("table_schema_empty", "知识库尚未定义可嵌入的表格列")

    return {
        "fields": fields,
        "created": created,
        "embed_fields": targets,
        "embed_field": targets[0],
        "rows": validate_rows(fields, rows, columns=columns),
    }
