"""LLM 语义补全与采纳（P0-8：E21 suggest + E22 adopt，spec §5.1-§5.5 / §6.1）。

**D3 rev.2 边界**（§5.1）：LLM 的一切**文本**产出（display_name / definition /
semantic_type / aliases / review_hint）只落 ``onto_ontology_semantic(status='suggested')``，
**永不直写结构表**；人工显式采纳（E22）才把文本值回写到**已存在**元素的对应文本列，
并按 §5.1 三值迁移把该元素 ``source`` 改写为 ``human``。

- LLM 置信度仅排序展示，**不参与** ``review_status``（§5.4）；
- 结构化输出三道校验（§5.3）：形态 / 枚举 / 引用（幻觉 code 丢弃并计 ``hallucination_dropped``）；
- LLM 调用失败**不静默返回空**（§5.2）：向上抛，端点降级为 ``SEMANTIC_UNAVAILABLE``。
"""
from __future__ import annotations

import asyncio
import json
from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_NOT_FOUND, SEMANTIC_UNAVAILABLE,
)
from app.models.ontology.ontology import MetaOntology, MetaOntologySemantic
from app.models.dataops.standard_cdm import MetaObjectRelation, MetaObjectStandard

#: 提示词契约版本（§5.2：Python 常量定义并版本化，可重放）
PROMPT_VERSION = "onto-semantic-1"
#: 语义类型枚举（§5.3 枚举校验，越界丢弃）
_SEMANTIC_TYPES = {
    "id", "code", "name", "amount", "quantity", "date", "datetime",
    "boolean", "category", "text", "ratio", "geo", "contact", "other",
}
#: 建议生成的文本字段（field 枚举）
_SUGGEST_FIELDS = {"display_name", "definition", "semantic_type", "aliases", "review_hint"}


def _schema_hint() -> str:
    """显式 JSON Schema 字符串（§5.2 必填参数，由 Python 常量承载）。"""
    return json.dumps({
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["element_code"],
                    "properties": {
                        "element_code": {"type": "string"},
                        "display_name": {"type": "string"},
                        "definition": {"type": "string"},
                        "semantic_type": {"type": "string"},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "review_hint": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                },
            }
        },
    }, ensure_ascii=False)


class OntologySemanticService:
    """语义补全与采纳（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologySemanticService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        obj = self.db.execute(
            select(MetaOntology).where(
                MetaOntology.tenant_id == self.tenant_id, MetaOntology.id == ontology_id
            )
        ).scalar_one_or_none()
        if obj is None:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", http_status=404, detail={"id": ontology_id})
        return obj

    # ------------------------------------------------------------- E21 suggest

    def suggest(
        self, ontology_id: int, *,
        element_kind: str = "object",
        element_codes: Optional[List[str]] = None,
        model_id: Optional[int] = None,
    ) -> dict:
        """为**已存在**的 accepted 元素生成文本语义建议，落 ``onto_ontology_semantic``。"""
        self._ontology_or_404(ontology_id)
        targets = self._load_targets(element_kind, element_codes)
        if not targets:
            return {"ontology_id": ontology_id, "created": 0, "hallucination_dropped": 0,
                    "items": [], "note": "无可补全元素（需先构建并采纳结构元素）"}

        prompt = self._build_prompt(element_kind, targets)
        raw = self._call_llm(prompt, model_id)  # 失败即抛，端点转 SEMANTIC_UNAVAILABLE

        valid_codes = {t["element_code"] for t in targets}
        created = 0
        hallucination_dropped = 0
        items: List[dict] = []
        for entry in (raw.get("items") if isinstance(raw, dict) else None) or []:
            if not isinstance(entry, dict):
                continue
            code = entry.get("element_code")
            # 引用校验（§5.3 三道之一）：code 必须在本次候选集合内
            if code not in valid_codes:
                hallucination_dropped += 1
                continue
            for field, value in self._extract_fields(entry):
                sid = self._upsert_semantic(
                    ontology_id, element_kind, code, field, value,
                    confidence=self._clamp_conf(entry.get("confidence")),
                    model=self._model_label(model_id),
                )
                if sid is not None:
                    created += 1
                    # 回传 semantic_id，前端据此直接调 E22 adopt（采纳闭环）
                    items.append({"semantic_id": sid, "element_code": code,
                                  "field": field, "value": value})
        self.db.flush()
        return {
            "ontology_id": ontology_id, "element_kind": element_kind,
            "created": created, "hallucination_dropped": hallucination_dropped,
            "prompt_version": PROMPT_VERSION, "items": items,
        }

    def _load_targets(self, element_kind: str, codes: Optional[List[str]]) -> List[dict]:
        stmt_codes = [c for c in (codes or []) if c]
        if element_kind == "relation":
            rows = self.db.execute(
                select(MetaObjectRelation).where(
                    MetaObjectRelation.tenant_id == self.tenant_id,
                    MetaObjectRelation.review_status == "accepted",
                )
            ).scalars().all()
            out = [{"element_code": r.code, "name": r.name, "description": r.description}
                   for r in rows]
        else:
            rows = self.db.execute(
                select(MetaObjectStandard).where(
                    MetaObjectStandard.tenant_id == self.tenant_id,
                    MetaObjectStandard.review_status == "accepted",
                )
            ).scalars().all()
            out = [{"element_code": o.code, "name": o.name, "description": o.description,
                    "aliases": o.aliases_json or []} for o in rows]
        if stmt_codes:
            out = [t for t in out if t["element_code"] in stmt_codes]
        return out

    def _build_prompt(self, element_kind: str, targets: List[dict]) -> str:
        """按 token 预算裁剪（§5.5）：最多 40 个元素进提示词，超限先裁。"""
        clipped = targets[:40]
        lines = [f"- {t['element_code']} | 现有名称={t.get('name') or ''} | 现有说明={t.get('description') or ''}"
                 for t in clipped]
        return (
            "你是数据本体治理助手。为下列已存在的元素补全中文语义文本。\n"
            "只输出 JSON，不要 markdown 代码块；键用 snake_case，禁止 PascalCase。\n"
            f"schema: {_schema_hint()}\n"
            f"semantic_type 只能取: {sorted(_SEMANTIC_TYPES)}。\n"
            "示例正例: {\"items\":[{\"element_code\":\"obj_order\",\"display_name\":\"订单\","
            "\"definition\":\"一次客户下单记录\",\"semantic_type\":\"id\",\"aliases\":[\"订单头\"],"
            "\"review_hint\":\"\",\"confidence\":0.8}]}\n"
            "示例负例(不确定给低分): {\"items\":[{\"element_code\":\"obj_x\","
            "\"display_name\":\"\",\"confidence\":0.2}]}\n"
            f"待补全 {element_kind} 元素:\n" + "\n".join(lines)
        )

    def _call_llm(self, prompt: str, model_id: Optional[int]) -> dict:
        from app.ai.research.llm import llm_json
        try:
            result = asyncio.run(llm_json(prompt, model_id=model_id))
        except Exception as exc:  # noqa: BLE001 - 统一降级为语义不可用
            logger.warning(f"语义补全 LLM 调用失败: {exc}")
            raise ApiError(
                SEMANTIC_UNAVAILABLE, "AI 语义补全不可用（模型未配置或调用失败）",
                http_status=503, detail={"reason": str(exc)[:500]},
            )
        # 形态校验（§5.3）：根必须是 object
        if not isinstance(result, dict):
            raise ApiError(SEMANTIC_UNAVAILABLE, "语义补全返回非对象结构", http_status=502,
                           detail={"type": type(result).__name__})
        return result

    @staticmethod
    def _extract_fields(entry: dict) -> List[tuple]:
        out: List[tuple] = []
        for field in ("display_name", "definition", "semantic_type", "review_hint"):
            val = entry.get(field)
            if isinstance(val, str) and val.strip():
                if field == "semantic_type" and val not in _SEMANTIC_TYPES:
                    continue  # 枚举越界丢弃（§5.3）
                out.append((field, val.strip()))
        aliases = entry.get("aliases")
        if isinstance(aliases, list) and aliases:
            out.append(("aliases", json.dumps([str(a) for a in aliases], ensure_ascii=False)))
        return out

    @staticmethod
    def _clamp_conf(val) -> Optional[float]:
        try:
            f = float(val)
        except (TypeError, ValueError):
            return None
        # 越界即视为无效（§5.3：不 clamp 后使用）
        if f < 0 or f > 1 or f != f:  # NaN 检查
            return None
        return f

    def _model_label(self, model_id: Optional[int]) -> str:
        return f"model#{model_id}" if model_id else "default"

    def _upsert_semantic(
        self, ontology_id: int, element_kind: str, element_code: str,
        field: str, value: str, *, confidence: Optional[float], model: str,
    ) -> Optional[int]:
        """新建或更新 suggested 语义行，返回其主键 id（非法 field 返回 None）。

        新建分支内部即刻 flush 以取得自增 id，供 suggest 响应回传给前端采纳。
        """
        if field not in _SUGGEST_FIELDS:
            return None
        existing = self.db.execute(
            select(MetaOntologySemantic).where(
                MetaOntologySemantic.tenant_id == self.tenant_id,
                MetaOntologySemantic.ontology_id == ontology_id,
                MetaOntologySemantic.element_kind == element_kind,
                MetaOntologySemantic.element_code == element_code,
                MetaOntologySemantic.field == field,
                MetaOntologySemantic.model == model,
            )
        ).scalar_one_or_none()
        aliases_json = None
        if field == "aliases":
            try:
                aliases_json = json.loads(value)
            except Exception:  # noqa: BLE001
                aliases_json = None
        if existing is None:
            sem = MetaOntologySemantic(
                tenant_id=self.tenant_id, ontology_id=ontology_id,
                element_kind=element_kind, element_code=element_code,
                field=field, value=None if field == "aliases" else value,
                aliases_json=aliases_json, confidence=confidence,
                model=model, prompt_version=PROMPT_VERSION, status="suggested",
            )
            self.db.add(sem)
            self.db.flush()
            return sem.id
        existing.value = None if field == "aliases" else value
        existing.aliases_json = aliases_json
        existing.confidence = confidence
        existing.status = "suggested"
        existing.prompt_version = PROMPT_VERSION
        return existing.id

    # ------------------------------------------------------------- E22 adopt

    def adopt(self, ontology_id: int, semantic_id: int, *, adopted_by: Optional[int] = None) -> dict:
        """采纳一条文本语义建议 → 回写**已存在**元素对应文本列 + 改写 source=human。"""
        sem = self.db.execute(
            select(MetaOntologySemantic).where(
                MetaOntologySemantic.tenant_id == self.tenant_id,
                MetaOntologySemantic.ontology_id == ontology_id,
                MetaOntologySemantic.id == semantic_id,
            )
        ).scalar_one_or_none()
        if sem is None:
            raise ApiError("ONTOLOGY_NOT_FOUND", "语义建议不存在", http_status=404,
                           detail={"semantic_id": semantic_id})
        if sem.status == "accepted":
            return {"id": sem.id, "status": "accepted", "changed": False,
                    "note": "该建议已采纳"}
        applied = self._apply_to_structural(sem)
        sem.status = "accepted"
        self.db.flush()
        return {
            "id": sem.id, "element_kind": sem.element_kind, "element_code": sem.element_code,
            "field": sem.field, "status": "accepted", "changed": applied,
            "adopted_by": adopted_by,
        }

    def _apply_to_structural(self, sem: MetaOntologySemantic) -> bool:
        """把文本值写入对应结构行的文本列，并按 §5.1 迁移改写 source=human。"""
        value = sem.value if sem.field != "aliases" else None
        if sem.element_kind == "relation":
            row = self.db.execute(
                select(MetaObjectRelation).where(
                    MetaObjectRelation.tenant_id == self.tenant_id,
                    MetaObjectRelation.code == sem.element_code,
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            self._write_text(row, sem.field, value, sem.aliases_json,
                             name_attr="name", desc_attr="description")
            row.source = "human"
            return True
        # 默认按对象处理
        row = self.db.execute(
            select(MetaObjectStandard).where(
                MetaObjectStandard.tenant_id == self.tenant_id,
                MetaObjectStandard.code == sem.element_code,
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        self._write_text(row, sem.field, value, sem.aliases_json,
                         name_attr="name", desc_attr="description")
        row.source = "human"
        return True

    @staticmethod
    def _write_text(row, field: str, value: Optional[str], aliases_json,
                    *, name_attr: str, desc_attr: str) -> None:
        if field == "display_name" and value:
            setattr(row, name_attr, value)
        elif field == "definition" and value:
            setattr(row, desc_attr, value)
        elif field == "aliases" and aliases_json is not None:
            setattr(row, "aliases_json", aliases_json)
        # semantic_type / review_hint 不回写结构列（结构表无对应列，仅作审阅参考）
