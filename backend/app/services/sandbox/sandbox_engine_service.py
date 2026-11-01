"""确定性 Tick 引擎（spec §4.1 sandbox_engine_service，S6–S12/S19/S21）。

内核三约束（A1/R3）：**Decimal 量化 4 位、固定序（(kind, code) 字符串元组）、受控 AST 不 eval**。
单 Tick 八段流水顺序即语义，逐段落 :class:`SandboxObservation`（source='engine'）；
同初态 + 同 accepted 配置 → 逐 Tick 完全一致的 observation 序列与实体终态（可复现、可回放）。

行动效应到期段（⑤）本任务留空实现，由 Task 6 填充 `_apply_due_actions`（行动链不在本任务测试覆盖）。
所有落库数值一律 `str(Decimal)`，`detail_json` 内亦然——比对/回放测试据字符串精确对齐。
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import ApiError, CHECKPOINT_LIMIT, GATE_DENIED_MODE, SCENE_NOT_FOUND
from app.models.sandbox.sandbox import (
    SandboxBranch, SandboxCheckpoint, SandboxEntity, SandboxObservation, SandboxRelation, SandboxScene,
)
from app.services.sandbox.ast_eval import AstEvalError, eval_expr
from app.services.sandbox.sandbox_element_service import SandboxElementService

logger = logging.getLogger(__name__)

_Q = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")


def _to_dec(v) -> Decimal:
    try:
        return Decimal(str(v)).quantize(_Q)
    except Exception:  # noqa: BLE001 - 非数值属性不参与算术，原样兜 0
        return _ZERO


def _clip(x: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(hi, x))


@dataclass
class World:
    """内存世界态：entity_code → 可变真源。props 数值为 Decimal，载入即转，落库再 str。"""

    entities: dict = field(default_factory=dict)   # code -> {props, risk_score, masked, object_code}
    elements: list = field(default_factory=list)   # accepted, (kind,code) 序
    events: list = field(default_factory=list)     # pending derived 实体行

    def get_prop(self, entity_code: str, key: str) -> Decimal:
        e = self.entities.get(entity_code)
        if e is None:
            raise AstEvalError("MISSING_PROP", f"实体不存在: {entity_code}")
        if key == "risk_score":
            return e["risk_score"]
        if key not in e["props"]:
            raise AstEvalError("MISSING_PROP", f"属性缺失: {entity_code}.{key}")
        return e["props"][key]

    def set_prop(self, entity_code: str, key: str, val: Decimal) -> None:
        e = self.entities.get(entity_code)
        if e is None:
            return
        val = val.quantize(_Q)
        if key == "risk_score":
            e["risk_score"] = val
        else:
            e["props"][key] = val


class SandboxEngineService:
    """确定性推演引擎（按 tenant_id 隔离；无租户拒绝构造）。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("SandboxEngineService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._elements = SandboxElementService(db, tenant_id)

    # ------------------------------------------------------------------ 内部取物

    def _scene(self, scene_id: int) -> SandboxScene:
        s = self.db.execute(select(SandboxScene).where(
            SandboxScene.tenant_id == self.tenant_id, SandboxScene.id == scene_id
        )).scalar_one_or_none()
        if s is None:
            raise ApiError(SCENE_NOT_FOUND, "场景不存在", http_status=404)
        return s

    def _branch(self, branch_id: int) -> SandboxBranch:
        b = self.db.get(SandboxBranch, branch_id)
        if b is None or b.tenant_id != self.tenant_id:
            raise ApiError("PARAM_INVALID", "分支不存在", http_status=400)
        return b

    def load_world(self, scene_id: int, branch_id: int) -> World:
        rows = self.db.execute(select(SandboxEntity).where(
            SandboxEntity.tenant_id == self.tenant_id, SandboxEntity.scene_id == scene_id,
            SandboxEntity.branch_id == branch_id, SandboxEntity.checkpoint_id.is_(None),
        ).order_by(SandboxEntity.entity_code)).scalars().all()
        entities = {}
        events = []
        for r in rows:
            # 派生事件行（origin='derived'）是行动效应队列，非可量化的世界态实体：
            # 不进 entities（避免 _flush_world 把 activation_tick 等属性 Decimal 量化写回，
            # 污染字符串属性并使 int(activation_tick) 崩溃），仅登记到事件队列供 _fire_events 读取。
            if r.origin == "derived":
                events.append({"entity_code": r.entity_code, "row": r})
                continue
            entities[r.entity_code] = {
                "props": {k: _to_dec(v) for k, v in (r.props_json or {}).items()},
                "risk_score": _to_dec(r.risk_score),
                "masked": bool(r.masked),
                "object_code": r.object_code,
            }
        return World(entities=entities, elements=self._elements.load_accepted(scene_id),
                     events=events)

    def _obs(self, scene_id: int, branch_id: int, tick: int, kind: str, severity: str,
             title: str, detail) -> None:
        self.db.add(SandboxObservation(
            tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id, tick=tick,
            kind=kind, severity=severity, title=title[:200], detail_json=detail, source="engine"))

    # ------------------------------------------------------------------ 单 Tick 八段流水

    def run_tick(self, scene_id: int, branch_id: int) -> int:
        self._scene(scene_id)
        world = self.load_world(scene_id, branch_id)
        tick = self._branch(branch_id).tick_now + 1
        self._fire_events(scene_id, branch_id, tick, world)
        fired, total = self._propagate_edges(scene_id, branch_id, tick, world)
        self._eval_rules(scene_id, branch_id, tick, world)
        self._eval_goals(scene_id, branch_id, tick, world)
        self._apply_due_actions(scene_id, branch_id, tick, world)  # Task 6 填充，此处空
        self._sample_kpi(scene_id, branch_id, tick, world, fired, total)
        self._risk_top3(scene_id, branch_id, tick, world)
        self._flush_world(scene_id, branch_id, world)
        br = self._branch(branch_id)
        br.tick_now = tick
        self.db.commit()
        return tick

    def _fire_events(self, scene_id, branch_id, tick, world) -> None:
        for ev in world.events:
            act = ev["row"].props_json.get("activation_tick") if ev["row"].props_json else None
            if act is None or int(Decimal(str(act))) <= tick:
                self._obs(scene_id, branch_id, tick, "event_fired", "info",
                          f"事件生效 {ev['entity_code']}", {"entity_code": ev["entity_code"]})

    def _propagate_edges(self, scene_id, branch_id, tick, world):
        fired = 0
        edges = [e for e in world.elements if e["kind"] == "causal_edge"]
        gp = world.get_prop
        gm = lambda k: _ZERO  # noqa: E731 - 引擎无外部参数源，param 恒 0（确定性）
        for e in edges:
            try:
                hit = bool(eval_expr(e["condition_expr_json"], gp, gm)) if e.get("condition_expr_json") else False
            except AstEvalError as err:
                self._obs(scene_id, branch_id, tick, "observation", "warn",
                          f"配置告警 {e['code']}: {err.code}", {"element_code": e["code"]})
                continue
            if not hit:
                continue
            try:
                val = Decimal(str(eval_expr(e["effect_expr_json"], gp, gm))).quantize(_Q)
            except AstEvalError as err:
                self._obs(scene_id, branch_id, tick, "observation", "warn",
                          f"配置告警 {e['code']}: {err.code}", {"element_code": e["code"]})
                continue
            targets = self._resolve_targets(e.get("to_ref"), world)
            for code, prop in targets:
                world.set_prop(code, prop, val)
            fired += 1
            self._obs(scene_id, branch_id, tick, "edge_fired", "info",
                      f"因果边 {e['code']} 触发",
                      {"element_code": e["code"], "to": e.get("to_ref"), "value": str(val)})
        return fired, len(edges)

    @staticmethod
    def _resolve_targets(to_ref, world):
        """支持 '<entity>.<prop>' 与 '<object_code>:<prop>'（后者作用该类型全部实体）。"""
        if not to_ref:
            return []
        if "." in to_ref:
            code, prop = to_ref.split(".", 1)
            return [(code, prop)] if code in world.entities else []
        if ":" in to_ref:
            obj, prop = to_ref.split(":", 1)
            return [(c, prop) for c, e in world.entities.items() if e["object_code"] == obj]
        return []

    def _eval_rules(self, scene_id, branch_id, tick, world):
        gp = world.get_prop
        gm = lambda k: _ZERO  # noqa: E731
        for e in world.elements:
            if e["kind"] != "rule":
                continue
            try:
                hit = bool(eval_expr(e["condition_expr_json"], gp, gm)) if e.get("condition_expr_json") else False
            except AstEvalError as err:
                self._obs(scene_id, branch_id, tick, "observation", "warn",
                          f"配置告警 {e['code']}: {err.code}", {"element_code": e["code"]})
                continue
            if hit:
                self._obs(scene_id, branch_id, tick, "rule_fired", "warn",
                          f"规则命中 {e['code']}: {e['label']}", {"element_code": e["code"]})

    def _eval_goals(self, scene_id, branch_id, tick, world):
        gp = world.get_prop
        gm = lambda k: _ZERO  # noqa: E731
        for e in world.elements:
            if e["kind"] != "goal":
                continue
            try:
                reached = bool(eval_expr(e["effect_expr_json"] or e.get("condition_expr_json"), gp, gm))
            except AstEvalError:
                reached = False
            status = "reached" if reached else "watching"
            self._obs(scene_id, branch_id, tick, "goal_eval", "info",
                      f"目标 {e['code']}: {status}", {"goal_code": e["code"], "status": status})

    def _apply_due_actions(self, scene_id, branch_id, tick, world) -> None:
        # Task 6 填充：消费 pending derived 行动事件、生效 action_effect 观察。本任务保持空实现。
        return None

    def _sample_kpi(self, scene_id, branch_id, tick, world, fired, total):
        ents = list(world.entities.values())
        if ents:
            avg = sum(_ONE - e["risk_score"] for e in ents) / Decimal(len(ents))
            health = _clip(avg.quantize(_Q), _ZERO, _ONE)
        else:
            health = _ONE
        ctrl = (_ONE - (Decimal(fired) / Decimal(total))).quantize(_Q) if total else _ONE
        self._obs(scene_id, branch_id, tick, "kpi_point", "info", f"Tick{tick} KPI",
                  {"health": str(health), "controllability": str(ctrl)})

    def _risk_top3(self, scene_id, branch_id, tick, world):
        ranked = sorted(world.entities.items(),
                        key=lambda kv: (-kv[1]["risk_score"], kv[0]))[:3]
        top = [{"entity_code": c, "score": str(e["risk_score"])} for c, e in ranked]
        self._obs(scene_id, branch_id, tick, "risk_point", "warn", "风险TOP3", top)

    def _flush_world(self, scene_id, branch_id, world):
        rows = self.db.execute(select(SandboxEntity).where(
            SandboxEntity.tenant_id == self.tenant_id, SandboxEntity.scene_id == scene_id,
            SandboxEntity.branch_id == branch_id, SandboxEntity.checkpoint_id.is_(None),
        )).scalars().all()
        for r in rows:
            e = world.entities.get(r.entity_code)
            if e is None:
                continue
            r.props_json = {k: str(v) for k, v in e["props"].items()}
            r.risk_score = float(e["risk_score"])
        self.db.flush()

    # ------------------------------------------------------------------ 推进 / 前瞻

    def advance(self, scene_id: int, branch_id: int, n: int) -> dict:
        scene = self._scene(scene_id)
        br = self._branch(branch_id)
        if scene.exec_mode == "replay":
            raise ApiError(GATE_DENIED_MODE, "replay 只读模式禁止推进", http_status=400)
        if scene.status != "running":
            raise ApiError("PARAM_INVALID", "场景非 running 态，无法推进", http_status=400)
        if n < 1 or br.tick_now + n > scene.tick_max:
            raise ApiError("PARAM_INVALID", f"推进超窗口 tick_max={scene.tick_max}", http_status=400)
        before = br.tick_now
        for _ in range(n):
            self.run_tick(scene_id, branch_id)
        after = self._branch(branch_id).tick_now
        created = len(self.db.execute(select(SandboxObservation.id).where(
            SandboxObservation.branch_id == branch_id, SandboxObservation.tick > before)).scalars().all())
        return {"branch_id": branch_id, "tick_before": before, "tick_after": after,
                "observations_created": created}

    def preview_future(self, scene_id: int, branch_id: int, depth: int = 4) -> list[dict]:
        """内存沿 accepted causal_edge 正向推演 ≤depth Tick，不落任何库（S19 kind=future）。"""
        world = self.load_world(scene_id, branch_id)
        base_tick = self._branch(branch_id).tick_now
        hits: list[dict] = []
        gp = world.get_prop
        gm = lambda k: _ZERO  # noqa: E731
        edges = [e for e in world.elements if e["kind"] == "causal_edge"]
        for offset in range(1, min(depth, 4) + 1):
            tick = base_tick + offset
            for e in edges:
                try:
                    if not (bool(eval_expr(e["condition_expr_json"], gp, gm)) if e.get("condition_expr_json") else False):
                        continue
                    val = Decimal(str(eval_expr(e["effect_expr_json"], gp, gm))).quantize(_Q)
                except AstEvalError:
                    continue
                targets = self._resolve_targets(e.get("to_ref"), world)
                for code, prop in targets:
                    world.set_prop(code, prop, val)
                hits.append({"element_code": e["code"], "expected_tick": tick,
                             "target_ref": e.get("to_ref"), "effect_summary": str(val)})
        return hits

    # ------------------------------------------------------------------ 检查点 / 派生 / 回放

    def save_checkpoint(self, scene_id: int, branch_id: int, label: str,
                        creator_id: Optional[int] = None) -> dict:
        self._scene(scene_id)
        br = self._branch(branch_id)
        cnt = len(self.db.execute(select(SandboxCheckpoint.id).where(
            SandboxCheckpoint.scene_id == scene_id,
            SandboxCheckpoint.tenant_id == self.tenant_id)).scalars().all())
        if cnt >= 5:
            raise ApiError(CHECKPOINT_LIMIT, "检查点场景级合计已达上限 5", http_status=400)
        seq = cnt
        cp = SandboxCheckpoint(tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id,
                               tick=br.tick_now, seq=seq, label=label, creator_id=creator_id)
        self.db.add(cp)
        self.db.flush()
        ents = self.db.execute(select(SandboxEntity).where(
            SandboxEntity.branch_id == branch_id, SandboxEntity.checkpoint_id.is_(None))).scalars().all()
        for e in ents:
            self.db.add(SandboxEntity(
                tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id, checkpoint_id=cp.id,
                entity_code=e.entity_code, object_code=e.object_code, props_json=dict(e.props_json or {}),
                risk_score=e.risk_score, masked=e.masked, source_ref_json=e.source_ref_json, origin=e.origin))
        rels = self.db.execute(select(SandboxRelation).where(
            SandboxRelation.branch_id == branch_id, SandboxRelation.checkpoint_id.is_(None))).scalars().all()
        for rl in rels:
            self.db.add(SandboxRelation(
                tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id, checkpoint_id=cp.id,
                rel_code=rl.rel_code, link_type_code=rl.link_type_code, from_entity_code=rl.from_entity_code,
                to_entity_code=rl.to_entity_code, props_json=dict(rl.props_json or {}), origin=rl.origin))
        kpi = self.db.execute(select(SandboxObservation).where(
            SandboxObservation.branch_id == branch_id, SandboxObservation.kind == "kpi_point",
            SandboxObservation.tick <= br.tick_now).order_by(SandboxObservation.tick.desc())).scalars().first()
        stats = {"entities": len(ents), "relations": len(rels), "kpi": (kpi.detail_json if kpi else {})}
        cp.stats_json = stats
        self.db.commit()
        return {"id": cp.id, "seq": seq, "tick": br.tick_now, "label": label, "count_used": cnt + 1}

    def delete_checkpoint(self, checkpoint_id: int) -> None:
        cp = self.db.get(SandboxCheckpoint, checkpoint_id)
        if cp is None or cp.tenant_id != self.tenant_id:
            raise ApiError("PARAM_INVALID", "检查点不存在", http_status=400)
        dep = self.db.execute(select(SandboxBranch.id).where(
            SandboxBranch.base_checkpoint_id == checkpoint_id)).scalars().first()
        if dep is not None:
            raise ApiError("PARAM_INVALID", "存在派生分支依赖该检查点", http_status=400)
        self.db.delete(cp)  # 快照行由 checkpoint_id FK ON DELETE CASCADE 清理
        self.db.commit()

    def derive_branch(self, scene_id: int, checkpoint_id: int, name: str) -> dict:
        self._scene(scene_id)
        cp = self.db.get(SandboxCheckpoint, checkpoint_id)
        if cp is None or cp.tenant_id != self.tenant_id or cp.scene_id != scene_id:
            raise ApiError("PARAM_INVALID", "检查点不存在", http_status=400)
        br = SandboxBranch(tenant_id=self.tenant_id, scene_id=scene_id, name=name,
                           base_checkpoint_id=checkpoint_id, tick_now=cp.tick)
        self.db.add(br)
        try:
            self.db.flush()
        except Exception as exc:  # noqa: BLE001 - uq_sandbox_branch_name 冲突
            self.db.rollback()
            raise ApiError("PARAM_INVALID", f"分支名冲突: {exc}") from exc
        snap = self.db.execute(select(SandboxEntity).where(
            SandboxEntity.checkpoint_id == checkpoint_id)).scalars().all()
        for e in snap:
            self.db.add(SandboxEntity(
                tenant_id=self.tenant_id, scene_id=scene_id, branch_id=br.id, checkpoint_id=None,
                entity_code=e.entity_code, object_code=e.object_code, props_json=dict(e.props_json or {}),
                risk_score=e.risk_score, masked=e.masked, source_ref_json=e.source_ref_json, origin=e.origin))
        self.db.commit()
        return {"branch_id": br.id, "name": name, "tick_now": br.tick_now, "restored_entities": len(snap)}

    def replay_to(self, scene_id: int, branch_id: int, to_tick: int) -> dict:
        """删除当前态 → 从基线 seq=0 快照恢复 → 删 tick>to_tick 观察 → run_tick 重放至 to_tick（A1 一致）。"""
        self._scene(scene_id)
        br = self._branch(branch_id)
        base = self.db.execute(select(SandboxCheckpoint).where(
            SandboxCheckpoint.scene_id == scene_id, SandboxCheckpoint.seq == 0)).scalars().first()
        self.db.query(SandboxEntity).filter(
            SandboxEntity.branch_id == branch_id, SandboxEntity.checkpoint_id.is_(None)
        ).delete(synchronize_session=False)
        restored = 0
        if base is not None:
            for e in self.db.execute(select(SandboxEntity).where(
                    SandboxEntity.checkpoint_id == base.id)).scalars().all():
                self.db.add(SandboxEntity(
                    tenant_id=self.tenant_id, scene_id=scene_id, branch_id=branch_id, checkpoint_id=None,
                    entity_code=e.entity_code, object_code=e.object_code, props_json=dict(e.props_json or {}),
                    risk_score=e.risk_score, masked=e.masked, source_ref_json=e.source_ref_json, origin=e.origin))
                restored += 1
        self.db.query(SandboxObservation).filter(
            SandboxObservation.branch_id == branch_id, SandboxObservation.tick > to_tick
        ).delete(synchronize_session=False)
        br.tick_now = 0
        self.db.commit()
        while br.tick_now < to_tick:
            self.run_tick(scene_id, branch_id)
            br = self._branch(branch_id)
        return {"tick_now": br.tick_now, "restored_entities": restored}

    # ------------------------------------------------------------------ 对比 / 只读渲染

    def compare(self, scene_id: int, branch_ids: list[int]) -> dict:
        branches = []
        series: dict[int, dict] = {}
        for bid in branch_ids:
            b = self._branch(bid)
            branches.append({"branch_id": bid, "name": b.name})
            kps = self.db.execute(select(SandboxObservation).where(
                SandboxObservation.branch_id == bid, SandboxObservation.kind == "kpi_point",
                SandboxObservation.scene_id == scene_id).order_by(SandboxObservation.tick)).scalars().all()
            for o in kps:
                series.setdefault(o.tick, {})[bid] = {"health": (o.detail_json or {}).get("health")}
        diff = []
        for bid in branch_ids:
            last = self._branch(bid).tick_now
            o = self.db.execute(select(SandboxObservation).where(
                SandboxObservation.branch_id == bid, SandboxObservation.kind == "kpi_point",
                SandboxObservation.tick == last)).scalars().first()
            diff.append({"kpi": "health", "branch_id": bid,
                         "branch_a_final": (o.detail_json or {}).get("health") if o else None,
                         "delta": None})
        return {"branches": branches,
                "series": [{"tick": t, "values": v} for t, v in sorted(series.items())],
                "diff_table": diff}

    def world_view(self, scene_id: int, branch_id: int, tick: Optional[int] = None,
                   view: str = "world") -> dict:
        self._scene(scene_id)
        rows = self.db.execute(select(SandboxEntity).where(
            SandboxEntity.tenant_id == self.tenant_id, SandboxEntity.scene_id == scene_id,
            SandboxEntity.branch_id == branch_id, SandboxEntity.checkpoint_id.is_(None),
        ).order_by(SandboxEntity.entity_code)).scalars().all()
        rels = self.db.execute(select(SandboxRelation).where(
            SandboxRelation.tenant_id == self.tenant_id, SandboxRelation.scene_id == scene_id,
            SandboxRelation.branch_id == branch_id, SandboxRelation.checkpoint_id.is_(None),
        ).order_by(SandboxRelation.rel_code)).scalars().all()
        # accepted 因果边元素：前端「因果传播」画布的边来源（clone 只产实体，结构关系常为空）
        edges = [{"code": e["code"], "label": e["label"], "from_ref": e["from_ref"],
                  "to_ref": e["to_ref"], "activation_tick": e["activation_tick"]}
                 for e in self._elements.load_accepted(scene_id) if e["kind"] == "causal_edge"]
        return {"scene_id": scene_id, "branch_id": branch_id, "tick": self._branch(branch_id).tick_now,
                "view": view, "entities": [
                    {"entity_code": r.entity_code, "object_code": r.object_code,
                     "props": r.props_json, "risk_score": r.risk_score, "masked": r.masked,
                     "origin": r.origin, "source_ref": r.source_ref_json}
                    for r in rows],
                "relations": [
                    {"rel_code": rl.rel_code, "link_type_code": rl.link_type_code,
                     "from_entity_code": rl.from_entity_code, "to_entity_code": rl.to_entity_code,
                     "props": rl.props_json, "origin": rl.origin}
                    for rl in rels],
                "causal_edges": edges}

    def list_checkpoints(self, scene_id: int, branch_id: Optional[int] = None) -> list[dict]:
        """检查点列表（时间轴 cp 标记 / 上限计数用）：按 (tick, seq) 升序，可选按分支过滤。"""
        self._scene(scene_id)
        q = select(SandboxCheckpoint).where(
            SandboxCheckpoint.tenant_id == self.tenant_id, SandboxCheckpoint.scene_id == scene_id)
        if branch_id is not None:
            q = q.where(SandboxCheckpoint.branch_id == branch_id)
        rows = self.db.execute(q.order_by(SandboxCheckpoint.tick, SandboxCheckpoint.seq)).scalars().all()
        return [{"id": c.id, "branch_id": c.branch_id, "tick": c.tick, "seq": c.seq,
                 "label": c.label, "stats": c.stats_json} for c in rows]

    def entity_detail(self, scene_id: int, branch_id: int, entity_code: str) -> dict:
        r = self.db.execute(select(SandboxEntity).where(
            SandboxEntity.tenant_id == self.tenant_id, SandboxEntity.scene_id == scene_id,
            SandboxEntity.branch_id == branch_id, SandboxEntity.entity_code == entity_code,
            SandboxEntity.checkpoint_id.is_(None))).scalars().first()
        if r is None:
            raise ApiError("PARAM_INVALID", "实体不存在", http_status=400)
        return {"entity_code": r.entity_code, "object_code": r.object_code,
                "props": r.props_json, "risk_score": r.risk_score, "masked": r.masked,
                "origin": r.origin}

    def list_observations(self, scene_id: int, branch_id: int, *, kind: Optional[str] = None,
                          tick_from: Optional[int] = None, tick_to: Optional[int] = None) -> list[dict]:
        if kind == "future":
            return [{"kind": "future", "tick": None,
                     "title": f"前瞻 {h['element_code']} @T{h['expected_tick']}",
                     "detail_json": h, "severity": "info"}
                    for h in self.preview_future(scene_id, branch_id)]
        q = select(SandboxObservation).where(
            SandboxObservation.tenant_id == self.tenant_id, SandboxObservation.scene_id == scene_id,
            SandboxObservation.branch_id == branch_id)
        if kind:
            q = q.where(SandboxObservation.kind == kind)
        if tick_from is not None:
            q = q.where(SandboxObservation.tick >= tick_from)
        if tick_to is not None:
            q = q.where(SandboxObservation.tick <= tick_to)
        rows = self.db.execute(q.order_by(SandboxObservation.tick, SandboxObservation.id)).scalars().all()
        return [{"id": o.id, "tick": o.tick, "kind": o.kind, "severity": o.severity,
                 "title": o.title, "detail_json": o.detail_json} for o in rows]

    def list_kpis(self, scene_id: int, branch_id: int) -> list[dict]:
        rows = self.db.execute(select(SandboxObservation).where(
            SandboxObservation.tenant_id == self.tenant_id, SandboxObservation.scene_id == scene_id,
            SandboxObservation.branch_id == branch_id,
            SandboxObservation.kind.in_(["kpi_point", "risk_point"]),
        ).order_by(SandboxObservation.tick, SandboxObservation.kind)).scalars().all()
        return [{"tick": o.tick, "kind": o.kind, "detail_json": o.detail_json} for o in rows]
