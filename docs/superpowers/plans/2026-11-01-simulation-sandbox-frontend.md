# 推演沙盘前端 `/admin/simulation` §4.3 组件化重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有单文件 `SimulationSandbox.vue`（918 行）重构为 §4.3 规定的 8 个子组件 + Pinia 游标 store，并补足两处后端接口缺口（compare 差异表、entity_detail 来源/行动可用标志），保持像素级对齐原型。

**Architecture:** 外壳 `SimulationSandbox.vue` 降级为「编排壳」——持有服务端数据 refs 与加载时序，子组件是无状态哑渲染（props 进、intent 事件出）。世界真源恒在后端沙箱表；Pinia `useSandboxStore` 仅持 `{sceneId, branchId, tick, execMode}` 游标。可测的纯视图逻辑（画布布局、边解析、KPI 选择、观察格式化）抽到独立 `.ts` 模块做单测，组件渲染用 `@vue/server-renderer` 的 `renderToString` 断言。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、Pinia ^2.1.7、ant-design-vue ^4.1.2（仅 `message`）、vitest ^2.1.9（node 环境，`@vue/server-renderer`）、FastAPI + SQLAlchemy + pytest。

**Spec:** `docs/superpowers/specs/2026-11-01-simulation-sandbox-design.md`（§4.3 前端组件拆分、§5 门禁、F1–F8）——执行者与计划共读此规格。

## Global Constraints

- **同步契约不变**：S1–S21 沿用已交付同步返回（`advance`/`actions` 直接返回终态、`ask` 返回完整 JSON）。本计划**不**引入 task-id 轮询与 SSE（列 P1）。唯一例外：新建场景 `createScene` 返回 `{scene_id,status:'pending'}`，克隆在后台线程执行，前端轮询 `getScene.status` 至 `running`/`failed`（无后端改动）。
- **注册已完成，不在本计划范围**：`componentMap.ts` 键 `simulation`、真实路由 `/admin/simulation`、`sys_menu` 种子 2408、4 个 locale `knowledge.menu.simulation` —— 上一会话已交付，本计划仅重构页面本体 + 补后端 G1/G2。
- **CSS 变量**：全部沿用现有 `.sandbox-root` 内定义（`--accent:#4aa3ff`、`--purple:#b48ef0`、`--amber:#f2b66d`、`--ok:#4cc38a`、`--err:#ff7b72`、`--bg-surface/--bg-elevated/--bg-input`、`--fg/--fg2/--fg3`、`--divider`、`--mono`、`--r:14px`、`--sh`、`--t:200ms cubic-bezier(.4,0,.2,1)`）。
- **前端测试纪律**：`@vue/test-utils`/`jsdom`/`happy-dom` **未安装**——纯逻辑写 `src/views/sandbox/__tests__/*.spec.ts`（vitest node 环境直接断言返回值）；组件渲染写 `renderToString(createSSRApp(Comp, props).use(Antd))` 断言 HTML 子串。运行：`npx vitest run <文件>`。
- **后端测试纪律**：`pytest tests/sandbox`（per-schema 隔离，`world`/`db` fixture 见 `backend/tests/sandbox/conftest.py`）。落库数值一律 `str(Decimal)` 量化 4 位。
- **commit 纪律**：每个 Task 末尾一次提交，只 `git add` 本任务相关文件；工作树含大量无关改动，绝不 `git add -A`。

---

## 文件结构（拆分决策在此锁定）

**新建（前端）**
- `frontend/src/stores/sandbox.ts` — Pinia `useSandboxStore`（游标 only）
- `frontend/src/views/sandbox/sandboxView.ts` — 纯视图逻辑（布局/边解析/KPI 选择/过滤）
- `frontend/src/views/sandbox/sandboxFormat.ts` — 纯格式化（标题/状态/严重度/转义/future 摘要）
- `frontend/src/views/sandbox/sandbox.css` — 非 scoped 共享样式（`.sandbox-root` 命名空间），壳 `import` 一次，子组件用普通 class
- `frontend/src/views/sandbox/components/ContextBar.vue`
- `frontend/src/views/sandbox/components/TickBar.vue`
- `frontend/src/views/sandbox/components/ScenePanel.vue`
- `frontend/src/views/sandbox/components/CausalCanvas.vue`
- `frontend/src/views/sandbox/components/TracePanel.vue`
- `frontend/src/views/sandbox/components/AdvisorPanel.vue`
- `frontend/src/views/sandbox/components/ActionModal.vue`
- `frontend/src/views/sandbox/components/CompareView.vue`
- `frontend/src/views/sandbox/components/KpiModal.vue`
- `frontend/src/views/sandbox/components/NewSceneModal.vue`
- `frontend/src/views/sandbox/components/DeleteConfirmModal.vue`

**修改（前端）**
- `frontend/src/api/sandbox.ts` — `getEntity` 返回补 `can_act`、`compare` 返回补 `branch_summary`
- `frontend/src/views/sandbox/SimulationSandbox.vue` — 重写为编排壳（模板换成子组件组合、脚本换成加载时序）

**新建（前端测试）**
- `frontend/src/views/sandbox/__tests__/sandboxView.spec.ts`
- `frontend/src/views/sandbox/__tests__/sandboxFormat.spec.ts`
- `frontend/src/stores/__tests__/sandbox.spec.ts`
- `frontend/src/views/sandbox/__tests__/panels.spec.ts`（子组件 renderToString）

**修改（后端）**
- `backend/app/services/sandbox/sandbox_engine_service.py` — `compare()` 加 `branch_summary`；`entity_detail()` 加 `source_ref`/`can_act`
- `backend/tests/sandbox/test_engine.py` — 加两测试

---

## Task B1: 后端 `entity_detail` 补 `source_ref` + `can_act`（G2）

**Files:**
- Modify: `backend/app/services/sandbox/sandbox_engine_service.py:471-480`
- Test: `backend/tests/sandbox/test_engine.py`

**Interfaces:**
- Consumes: fixture `world`（`db`,`world` → `{scene_id,branch_id,baseline_cp}`），`SandboxEngineService`
- Produces: `entity_detail(scene_id, branch_id, entity_code) -> dict`，新增键 `source_ref: dict | None`、`can_act: bool`（`can_act = origin != 'derived' and not masked`）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/sandbox/test_engine.py` 末尾追加：

```python
def test_entity_detail_includes_source_ref_and_can_act(db, world):
    sid, bid = world["scene_id"], world["branch_id"]
    # SUP006: origin=clone, masked=False → can_act True
    d = SandboxEngineService(db, TENANT_A).entity_detail(sid, bid, "SUP006")
    assert d["can_act"] is True
    assert "source_ref" in d and d["source_ref"] is None
    # 补一条脱敏实体 → can_act False，带 source_ref
    db.add(SandboxEntity(tenant_id=TENANT_A, scene_id=sid, branch_id=bid,
                         entity_code="MASK1", object_code="Supplier", props_json={},
                         risk_score=0.1, masked=True, origin="clone",
                         source_ref_json={"asset": "dwd_supp", "col": "phone"}))
    db.commit()
    m = SandboxEngineService(db, TENANT_A).entity_detail(sid, bid, "MASK1")
    assert m["can_act"] is False and m["source_ref"] == {"asset": "dwd_supp", "col": "phone"}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/sandbox/test_engine.py::test_entity_detail_includes_source_ref_and_can_act -v`
Expected: FAIL（KeyError/`can_act` 断言失败——现返回无这两个键）

- [ ] **Step 3: 改实现**

`sandbox_engine_service.py:478-480` 返回体改为：

```python
        return {"entity_code": r.entity_code, "object_code": r.object_code,
                "props": r.props_json, "risk_score": r.risk_score, "masked": r.masked,
                "origin": r.origin, "source_ref": r.source_ref_json,
                "can_act": r.origin != "derived" and not bool(r.masked)}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/sandbox/test_engine.py -v`
Expected: PASS（含新增测试，旧引擎测试全绿）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/sandbox/sandbox_engine_service.py backend/tests/sandbox/test_engine.py
git commit -m "feat(sandbox): entity_detail 补 source_ref 与 can_act 行动可用标志"
```

---

## Task B2: 后端 `compare` 补 `branch_summary` 富差异表（G1）

**Files:**
- Modify: `backend/app/services/sandbox/sandbox_engine_service.py:408-430`
- Test: `backend/tests/sandbox/test_engine.py`

**Interfaces:**
- Consumes: fixture `world`，`SandboxEngineService.advance/derive_branch`；模型 `SandboxAction`（`app.models.sandbox.sandbox`）；观察 kind `goal_eval`（detail `{goal_code,status}`）、`rule_fired`
- Produces: `compare(scene_id, branch_ids) -> dict` 新增键 `branch_summary: list[dict]`，每项 `{branch_id, name, final_tick, final_health: str|None, health_delta: str|None, goal_reached_count: int, rule_fired_count: int, action_count: int}`；`health_delta` = 本分支末 health − 首分支末 health（Decimal 量化 4 位字符串）；既有 `branches/series/diff_table` 保持不变（向后兼容）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/sandbox/test_engine.py` 顶部 import 追加 `SandboxAction`：

```python
from app.models.sandbox.sandbox import (
    SandboxBranch, SandboxCheckpoint, SandboxElement, SandboxEntity,
    SandboxObservation, SandboxRelation, SandboxScene, SandboxAction,
)
```

末尾追加：

```python
def test_compare_returns_branch_summary(db, world):
    eng = SandboxEngineService(db, TENANT_A)
    sid, b1 = world["scene_id"], world["branch_id"]
    eng.advance(sid, b1, 2)
    d = eng.derive_branch(sid, world["baseline_cp"], "分支二")
    eng.advance(sid, d["branch_id"], 1)
    # b1 落一条 allowed 行动审计行，验证 action_count
    db.add(SandboxAction(tenant_id=TENANT_A, scene_id=sid, branch_id=b1, tick=1,
                         template_code="adjust_capacity", target_entity_code="FAC007",
                         gate_result="allowed", params_json={}))
    db.commit()
    cmp = eng.compare(sid, [b1, d["branch_id"]])
    s = {x["branch_id"]: x for x in cmp["branch_summary"]}
    assert s[b1]["final_tick"] == 2 and s[b1]["action_count"] == 1
    assert s[b1]["rule_fired_count"] == 2 and s[b1]["goal_reached_count"] == 0
    assert s[d["branch_id"]]["final_tick"] == 1
    assert s[b1]["health_delta"] == "0.0000"           # 首分支相对自身
    assert isinstance(s[d["branch_id"]]["health_delta"], str)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/sandbox/test_engine.py::test_compare_returns_branch_summary -v`
Expected: FAIL（`KeyError: 'branch_summary'`）

- [ ] **Step 3: 改实现**

`sandbox_engine_service.py:408` 的 `compare` 方法体内，`return` 之前（L428 前）插入 `branch_summary` 计算，并把返回 dict 追加该键。用 `_dec = Decimal(str(...))` 统一量化：

```python
        # 逐分支末态汇总（CompareView 富差异表数据源）
        first_final = None
        summaries = []
        for bid in branch_ids:
            b = self._branch(bid)
            last = b.tick_now
            o = self.db.execute(select(SandboxObservation).where(
                SandboxObservation.branch_id == bid, SandboxObservation.kind == "kpi_point",
                SandboxObservation.tick == last)).scalars().first()
            final_health = (o.detail_json or {}).get("health") if o else None
            if first_final is None:
                first_final = final_health
            delta = (_to_dec(final_health) - _to_dec(first_final)).quantize(_Q) \
                if final_health is not None and first_final is not None else None
            goal_reached = len(self.db.execute(select(SandboxObservation.id).where(
                SandboxObservation.branch_id == bid, SandboxObservation.kind == "goal_eval",
                SandboxObservation.tick == last,
                SandboxObservation.detail_json["status"].astext == "reached")).scalars().all())
            rule_fired = len(self.db.execute(select(SandboxObservation.id).where(
                SandboxObservation.branch_id == bid, SandboxObservation.kind == "rule_fired",
                SandboxObservation.tick <= last)).scalars().all())
            action_count = len(self.db.execute(select(SandboxAction.id).where(
                SandboxAction.branch_id == bid, SandboxAction.scene_id == scene_id,
                SandboxAction.tenant_id == self.tenant_id)).scalars().all())
            summaries.append({"branch_id": bid, "name": b.name, "final_tick": last,
                              "final_health": final_health,
                              "health_delta": str(delta) if delta is not None else None,
                              "goal_reached_count": goal_reached,
                              "rule_fired_count": rule_fired, "action_count": action_count})
        return {"branches": branches,
                "series": [{"tick": t, "values": v} for t, v in sorted(series.items())],
                "diff_table": diff,
                "branch_summary": summaries}
```

> 顶部 import 追加：`from app.models.sandbox.sandbox import ... SandboxAction`（并入现有 import 行 L22-24）。`detail_json["status"].astext` 需 SQLAlchemy JSON 访问，Postgres 支持。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/sandbox -v`
Expected: PASS（全套 ≥63 绿，含 B1/B2 新测试；旧 `test_compare_series_from_observations` 不受影响）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/sandbox/sandbox_engine_service.py backend/tests/sandbox/test_engine.py
git commit -m "feat(sandbox): compare 返回 branch_summary 富差异表（health_delta/目标/规则/行动计数）"
```

---

## Task F1: `api/sandbox.ts` 类型对齐后端新字段

**Files:**
- Modify: `frontend/src/api/sandbox.ts:162-195`

**Interfaces:**
- Consumes: 后端 B1/B2 返回
- Produces: `getEntity` 返回 `WorldEntity & { origin: string; can_act: boolean }`；`compare` 返回补 `branch_summary: BranchSummary[]`，`export interface BranchSummary { branch_id:number; name:string; final_tick:number; final_health:string|null; health_delta:string|null; goal_reached_count:number; rule_fired_count:number; action_count:number }`

- [ ] **Step 1: 无独立测试，本任务由 vue-tsc 把关**（类型层，后续 F12 集成时统一校验）

- [ ] **Step 2: 改 `getEntity`（L162-164）**

```ts
export function getEntity(sceneId: number, entityCode: string, params: { branch_id: number }) {
  return request.get<WorldEntity & { origin: string; can_act: boolean }>(
    `${BASE}/scenes/${sceneId}/entities/${entityCode}`, { params })
}
```

- [ ] **Step 3: 改 `compare`（L189-195）并加导出接口**

在 `// ── S19 对比` 区块上方加：

```ts
export interface BranchSummary {
  branch_id: number; name: string; final_tick: number
  final_health: string | null; health_delta: string | null
  goal_reached_count: number; rule_fired_count: number; action_count: number
}
```

`compare` 返回泛型补 `branch_summary: BranchSummary[]`：

```ts
export function compare(sceneId: number, branchIds: number[]) {
  return request.get<{
    branches: { branch_id: number; name: string }[]
    series: { tick: number; values: Record<string, any> }[]
    diff_table: any[]
    branch_summary: BranchSummary[]
  }>(`${BASE}/scenes/${sceneId}/compare`, { params: { branches: branchIds.join(',') } })
}
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/sandbox.ts
git commit -m "types(sandbox): getEntity 补 can_act、compare 补 branch_summary"
```

---

## Task F2: 纯视图逻辑 `sandboxView.ts`（画布布局/边解析/KPI/过滤）

**Files:**
- Create: `frontend/src/views/sandbox/sandboxView.ts`
- Test: `frontend/src/views/sandbox/__tests__/sandboxView.spec.ts`

**Interfaces:**
- Consumes: `WorldView`/`WorldEntity`/`CausalEdge`/`KpiPoint`/`Observation`（`@/api/sandbox`）
- Produces:
  - `type LayoutNode = WorldEntity & { x:number; y:number; isEvent:boolean; name:string; risk:number; riskColor:string }`
  - `buildCanvasLayout(entities: WorldEntity[]): LayoutNode[]`
  - `resolveEdgeEntity(ref: string|null, nodes: LayoutNode[]): string|null`
  - `buildCanvasEdges(nodes: LayoutNode[], edges: CausalEdge[], tick: number): {path:string;mx:number;my:number;wl:number;label:string;active:boolean}[]`
  - `selectLatestKpi(kpis: KpiPoint[], tick: number, kind: string): KpiPoint|null`
  - `deriveHealth(kpi: KpiPoint|null): {num:number; label:string; color:string}`
  - `deriveControllability(kpi: KpiPoint|null): {label:'high'|'medium'|'low'; color:string}`
  - `deriveRiskTop3(kpis: KpiPoint[], tick: number): {entity_code:string; score:number}[]`
  - `timelineItems(obs: Observation[]): Observation[]`
  - `traceObservations(obs: Observation[], tick: number): Observation[]`

- [ ] **Step 1: 写失败测试**

`frontend/src/views/sandbox/__tests__/sandboxView.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import type { WorldEntity, KpiPoint, Observation } from '@/api/sandbox'
import {
  buildCanvasLayout, resolveEdgeEntity, buildCanvasEdges, selectLatestKpi,
  deriveHealth, deriveControllability, deriveRiskTop3, timelineItems, traceObservations,
} from '../sandboxView'

const ent = (code: string, obj: string, risk: number, masked = false): WorldEntity =>
  ({ entity_code: code, object_code: obj, props: { name: code }, risk_score: risk, masked, origin: 'clone', source_ref: null })

describe('buildCanvasLayout', () => {
  it('网格列数 ≤3，SimEvent 标记 isEvent', () => {
    const nodes = buildCanvasLayout([ent('A', 'Supplier', 0.7), ent('E', 'SimEvent', 0)])
    expect(nodes).toHaveLength(2)
    expect(nodes[0].x).toBeGreaterThanOrEqual(0)
    expect(nodes[1].isEvent).toBe(true)
    expect(nodes[0].riskColor).toBe('#ff7b72') // ≥0.6
  })
})

describe('resolveEdgeEntity', () => {
  const nodes = buildCanvasLayout([ent('SUP006', 'Supplier', 0.5), ent('FAC007', 'Factory', 0.5)])
  it('A.prop → A', () => expect(resolveEdgeEntity('SUP006.supply_cut', nodes)).toBe('SUP006'))
  it('OBJ:prop → 匹配 object_code 实体', () => expect(resolveEdgeEntity('Factory:capacity', nodes)).toBe('FAC007'))
  it('未知 → null', () => expect(resolveEdgeEntity('NOPE:x', nodes)).toBeNull())
})

describe('buildCanvasEdges', () => {
  it('仅两端可解析才成边；tick≥activation 点亮', () => {
    const nodes = buildCanvasLayout([ent('SUP006', 'Supplier', 0.5), ent('FAC007', 'Factory', 0.5)])
    const edges = [{ code: 'CE1', label: '断供→减产', from_ref: 'SUP006', to_ref: 'FAC007.capacity', activation_tick: 2 }]
    const out = buildCanvasEdges(nodes, edges as any, 3)
    expect(out).toHaveLength(1)
    expect(out[0].active).toBe(true)
    expect(buildCanvasEdges(nodes, edges as any, 1)[0].active).toBe(false)
  })
})

describe('KPI 选择', () => {
  const kpis: KpiPoint[] = [
    { tick: 1, kind: 'kpi_point', detail_json: { health: '0.9', controllability: '0.95' } },
    { tick: 2, kind: 'kpi_point', detail_json: { health: '0.5', controllability: '0.4' } },
    { tick: 2, kind: 'risk_point', detail_json: [{ entity_code: 'SUP006', score: '0.8' }] },
  ]
  it('selectLatestKpi ≤tick 末值', () => expect(selectLatestKpi(kpis, 2, 'kpi_point')!.tick).toBe(2))
  it('deriveHealth 0.5 → 预警 C err', () => { expect(deriveHealth(selectLatestKpi(kpis, 2, 'kpi_point')).label).toBe('预警 C') })
  it('deriveControllability 0.4 → low', () => { expect(deriveControllability(selectLatestKpi(kpis, 2, 'kpi_point')).label).toBe('low') })
  it('deriveRiskTop3 取 ≤tick 末 risk_point', () => { expect(deriveRiskTop3(kpis, 2)[0].score).toBe(0.8) })
})

describe('观察过滤', () => {
  const obs: Observation[] = [
    { tick: 1, kind: 'edge_fired', severity: 'info', title: 'x', detail_json: {} },
    { tick: 3, kind: 'kpi_point', severity: 'info', title: 'y', detail_json: {} },
    { tick: 5, kind: 'rule_fired', severity: 'warn', title: 'z', detail_json: {} },
  ]
  it('timelineItems 排除 kpi/risk', () => expect(timelineItems(obs).map(o => o.kind)).toEqual(['edge_fired', 'rule_fired']))
  it('traceObservations 仅 ≤tick', () => expect(traceObservations(obs, 1).map(o => o.title)).toEqual(['x']))
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/sandboxView.spec.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `sandboxView.ts`**

把 `SimulationSandbox.vue:447-503` 的 `entityDisplayName`/`riskColorOf`/`canvasNodes`/`resolveEdgeEntity`/`canvasEdges` 与 `:403-425` 的 KPI/时间线 computed **改写为纯函数**（去响应式，参数注入）。关键实现：

```ts
import type { WorldEntity, CausalEdge, KpiPoint, Observation } from '@/api/sandbox'

export type LayoutNode = WorldEntity & {
  x: number; y: number; isEvent: boolean; name: string; risk: number; riskColor: string
}

export function entityDisplayName(entities: WorldEntity[], code: string): string {
  const e = entities.find(x => x.entity_code === code)
  if (!e) return code
  return e.props?.name || e.props?.display_name || e.object_code || code
}
export function riskColorOf(score: number): string {
  return score >= 0.6 ? '#ff7b72' : score >= 0.35 ? '#f2b66d' : '#4cc38a'
}
export function buildCanvasLayout(entities: WorldEntity[]): LayoutNode[] {
  const W = 960, H = 460
  const cols = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(entities.length))))
  const rows = Math.max(1, Math.ceil(entities.length / cols))
  const cellW = W / cols, cellH = H / rows
  return entities.map((e, i) => {
    const r = Math.floor(i / cols), c = i % cols
    return { ...e, isEvent: e.object_code === 'SimEvent',
      name: entityDisplayName(entities, e.entity_code), risk: Number(e.risk_score) || 0,
      riskColor: riskColorOf(Number(e.risk_score) || 0), x: c * cellW + 60, y: r * cellH + 20 }
  })
}
export function resolveEdgeEntity(ref: string | null, nodes: LayoutNode[]): string | null {
  if (!ref) return null
  if (ref.includes('.')) return ref.split('.', 1)[0]
  if (ref.includes(':')) {
    const obj = ref.split(':', 1)[0]
    const hit = nodes.find(n => n.object_code === obj)
    return hit ? hit.entity_code : null
  }
  return nodes.find(n => n.entity_code === ref) ? ref : null
}
export function buildCanvasEdges(nodes: LayoutNode[], edges: CausalEdge[], tick: number) {
  const pos = new Map(nodes.map(n => [n.entity_code, n]))
  const out: { path: string; mx: number; my: number; wl: number; label: string; active: boolean }[] = []
  for (const e of edges) {
    const a = pos.get(resolveEdgeEntity(e.from_ref, nodes) || '')
    const b = pos.get(resolveEdgeEntity(e.to_ref, nodes) || '')
    if (!a || !b) continue
    const x1 = a.x + (a.isEvent ? 92 : 156), y1 = a.y + 22
    const x2 = b.x, y2 = b.y + 22
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
    const path = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`
    const active = e.activation_tick == null || tick >= e.activation_tick
    out.push({ path, mx, my, wl: (e.label || '').length * 6 + 12, label: e.label || '', active })
  }
  return out
}
export function selectLatestKpi(kpis: KpiPoint[], tick: number, kind: string): KpiPoint | null {
  const pts = kpis.filter(k => k.kind === kind && (k.tick ?? 0) <= tick).sort((a, b) => (a.tick ?? 0) - (b.tick ?? 0))
  return pts.length ? pts[pts.length - 1] : null
}
export function deriveHealth(kpi: KpiPoint | null) {
  const num = Number(kpi?.detail_json?.health ?? 1)
  return { num, label: num >= 0.8 ? '健康 A' : num >= 0.6 ? '关注 B' : '预警 C',
    color: num >= 0.8 ? 'var(--ok)' : num >= 0.6 ? 'var(--amber)' : 'var(--err)' }
}
export function deriveControllability(kpi: KpiPoint | null) {
  const c = Number(kpi?.detail_json?.controllability ?? 1)
  const label = c >= 0.8 ? 'high' : c >= 0.5 ? 'medium' : 'low'
  return { label, color: label === 'high' ? 'var(--ok)' : label === 'medium' ? 'var(--amber)' : 'var(--err)' }
}
export function deriveRiskTop3(kpis: KpiPoint[], tick: number): { entity_code: string; score: number }[] {
  const pts = kpis.filter(k => k.kind === 'risk_point' && (k.tick ?? 0) <= tick).sort((a, b) => (a.tick ?? 0) - (b.tick ?? 0))
  const last = pts[pts.length - 1]
  if (!last) return []
  const arr = last.detail_json
  return Array.isArray(arr) ? arr.map((x: any) => ({ entity_code: x.entity_code, score: Number(x.score) })) : []
}
export function timelineItems(obs: Observation[]): Observation[] {
  return obs.filter(o => o.kind !== 'kpi_point' && o.kind !== 'risk_point').slice(0, 60)
}
export function traceObservations(obs: Observation[], tick: number): Observation[] {
  return obs.filter(o => (o.tick ?? 0) <= tick && o.kind !== 'kpi_point' && o.kind !== 'risk_point')
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/sandboxView.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/sandbox/sandboxView.ts frontend/src/views/sandbox/__tests__/sandboxView.spec.ts
git commit -m "refactor(sandbox): 抽纯视图逻辑到 sandboxView.ts + vitest"
```

---

## Task F3: 纯格式化 `sandboxFormat.ts`

**Files:**
- Create: `frontend/src/views/sandbox/sandboxFormat.ts`
- Test: `frontend/src/views/sandbox/__tests__/sandboxFormat.spec.ts`

**Interfaces:**
- Consumes: `Observation`
- Produces: `sceneStatusLabel(st)`,`sceneTagClass(st)`,`obsSevClass(sev)`,`sevIcon(sev)`,`truncate(s,n)`,`escapeHtml(s)`,`formatFutureSummary(f: Observation): string`

- [ ] **Step 1: 写失败测试**

```ts
import { describe, it, expect } from 'vitest'
import type { Observation } from '@/api/sandbox'
import { sceneStatusLabel, sceneTagClass, obsSevClass, sevIcon, truncate, escapeHtml, formatFutureSummary } from '../sandboxFormat'

describe('sandboxFormat', () => {
  it('状态标签/样式', () => {
    expect(sceneStatusLabel('running')).toBe('进行中')
    expect(sceneStatusLabel('draft')).toBe('克隆中')
    expect(sceneTagClass('completed')).toBe('g')
    expect(sceneTagClass('running')).toBe('p')
  })
  it('严重度 → class/icon', () => {
    expect(obsSevClass('error')).toBe('err'); expect(obsSevClass('info')).toBe('info'); expect(obsSevClass('warn')).toBe('')
    expect(sevIcon('err')).toBe('⚠'); expect(sevIcon('warn')).toBe('◑'); expect(sevIcon('info')).toBe('◷')
  })
  it('truncate + escapeHtml', () => {
    expect(truncate('abcdefgh', 5)).toBe('abcd…')
    expect(escapeHtml('a<b>&c\nd')).toBe('a&lt;b&gt;&amp;c<br>d')
  })
  it('formatFutureSummary', () => {
    const f = { kind: 'future', tick: null, title: 'x', severity: 'info',
      detail_json: { element_code: 'CE1', target_ref: 'FAC007.capacity', expected_tick: 4, effect_summary: '23.83' } } as Observation
    expect(formatFutureSummary(f)).toContain('CE1 → FAC007.capacity @T4')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/sandboxFormat.spec.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**（从 monolith `:711-716` 抽为纯函数）

```ts
import type { Observation } from '@/api/sandbox'
export const sceneStatusLabel = (st: string) =>
  st === 'running' ? '进行中' : st === 'draft' ? '克隆中' : st === 'completed' ? '已完成' : st
export const sceneTagClass = (st: string) => (st === 'running' ? 'p' : st === 'completed' ? 'g' : 'a')
export const obsSevClass = (sev: string) => (sev === 'err' || sev === 'error' ? 'err' : sev === 'info' ? 'info' : '')
export const sevIcon = (sev: string) => (sev === 'err' || sev === 'error' ? '⚠' : sev === 'warn' ? '◑' : '◷')
export const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n) + '…' : s)
export const escapeHtml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
export function formatFutureSummary(f: Observation): string {
  const d = (f.detail_json || {}) as Record<string, any>
  return `${d.element_code || ''} → ${d.target_ref || ''} · 预期 T${d.expected_tick ?? '?'} · 效应 ${d.effect_summary ?? ''}`
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/sandboxFormat.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/sandbox/sandboxFormat.ts frontend/src/views/sandbox/__tests__/sandboxFormat.spec.ts
git commit -m "refactor(sandbox): 抽纯格式化到 sandboxFormat.ts + vitest"
```

---

## Task F4: Pinia 游标 store `useSandboxStore`

**Files:**
- Create: `frontend/src/stores/sandbox.ts`
- Test: `frontend/src/stores/__tests__/sandbox.spec.ts`

**Interfaces:**
- Consumes: `defineStore`（pinia）
- Produces: `useSandboxStore`：state `{sceneId:number|null, branchId:number|null, tick:number, execMode:string}`；action `setCursor(p: Partial<state>)`、`reset()`。**仅游标**，不含世界数据。

- [ ] **Step 1: 写失败测试**

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSandboxStore } from '../sandbox'

describe('useSandboxStore 游标', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('默认游标', () => {
    const s = useSandboxStore()
    expect(s.sceneId).toBeNull(); expect(s.tick).toBe(0); expect(s.execMode).toBe('auto')
  })
  it('setCursor 局部更新', () => {
    const s = useSandboxStore()
    s.setCursor({ sceneId: 7, branchId: 3, tick: 5, execMode: 'replay' })
    expect(s.sceneId).toBe(7); expect(s.branchId).toBe(3); expect(s.tick).toBe(5); expect(s.execMode).toBe('replay')
  })
  it('reset 清空', () => {
    const s = useSandboxStore(); s.setCursor({ sceneId: 7, tick: 5 }); s.reset()
    expect(s.sceneId).toBeNull(); expect(s.tick).toBe(0)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/stores/__tests__/sandbox.spec.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `stores/sandbox.ts`**

```ts
import { defineStore } from 'pinia'

export const useSandboxStore = defineStore('sandbox', {
  state: () => ({
    sceneId: null as number | null,
    branchId: null as number | null,
    tick: 0,
    execMode: 'auto',
  }),
  actions: {
    setCursor(p: Partial<{ sceneId: number | null; branchId: number | null; tick: number; execMode: string }>) {
      Object.assign(this, p)
    },
    reset() { this.sceneId = null; this.branchId = null; this.tick = 0; this.execMode = 'auto' },
  },
})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/stores/__tests__/sandbox.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/stores/sandbox.ts frontend/src/stores/__tests__/sandbox.spec.ts
git commit -m "feat(sandbox): Pinia 游标 store useSandboxStore（sceneId/branchId/tick/execMode）"
```

---

## Task F5: 共享样式 `sandbox.css`（去 scoped，命名空间隔离）

**Files:**
- Create: `frontend/src/views/sandbox/sandbox.css`

**Interfaces:**
- Consumes: monolith `:727-918` 的 `<style scoped>`
- Produces: 同一份 CSS，但**去掉 scoped**、所有选择器加 `.sandbox-root` 前缀（`.sandbox-root .btn{...}`），供壳 `import` 一次、子组件复用普通 class。`.sandbox-root` 的 CSS 变量定义块保持原样。

- [ ] **Step 1: 迁移样式**

把 `SimulationSandbox.vue:727-918` 内容整体复制到 `sandbox.css`，删除 `<style scoped>` 包裹，每条**后代选择器**加 `.sandbox-root ` 前缀（例 `.btn{}` → `.sandbox-root .btn{}`；根块 `.sandbox-root{--accent...}` 保持）。`@keyframes sp/tin` 原样保留（全局名，唯一）。

- [ ] **Step 2: 校验无孤立选择器**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | Select-String "sandbox"`
Expected: 无 sandbox 相关报错（纯 CSS 不触发；此步仅确认可继续）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/sandbox/sandbox.css
git commit -m "refactor(sandbox): 共享样式抽到非 scoped sandbox.css（.sandbox-root 命名空间）"
```

---

## Task F6: 子组件 ContextBar + KpiModal + DeleteConfirmModal + NewSceneModal（F5 域）

**Files:**
- Create: `frontend/src/views/sandbox/components/ContextBar.vue`
- Create: `frontend/src/views/sandbox/components/KpiModal.vue`
- Create: `frontend/src/views/sandbox/components/DeleteConfirmModal.vue`
- Create: `frontend/src/views/sandbox/components/NewSceneModal.vue`
- Test: `frontend/src/views/sandbox/__tests__/panels.spec.ts`

**Interfaces:**
- Consumes: `SandboxScene`, `BranchSummary`（`@/api/sandbox`）；`deriveHealth`/`deriveControllability` 结果由父传入
- Produces（props/emits 契约）:
  - `ContextBar` props `{ sourceLabel:string, cloneScopeLabel:string, tick:number, maxTick:number, execMode:string, checkpointCount:number, hasScene:boolean }` emits `('save-checkpoint'|'refresh'|'open-kpi'|'open-create'|'open-delete'|'exec-mode', mode:string)`
  - `KpiModal` props `{ show:boolean, sceneName:string, tick:number, health:{label,color}, controllability:{label,color}, entityCount:number, branchName:string, observationCount:number, maxTick:number }` emits `('close')`
  - `DeleteConfirmModal` props `{ show:boolean, sceneName:string, checkpointCount:number, branchCount:number }` emits `('cancel')`,`('confirm')`
  - `NewSceneModal` props `{ show:boolean, ontologies:{id,code,name,current_version}[], busy:boolean }` + `v-model` 表单由内部 reactive 持有，emits `('cancel')`,`('create', {ontology_id,name,tick_max})`

- [ ] **Step 1: 写失败 render 测试**

`frontend/src/views/sandbox/__tests__/panels.spec.ts`：

```ts
import { describe, it, expect } from 'vitest'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import ContextBar from '../components/ContextBar.vue'
import KpiModal from '../components/KpiModal.vue'

describe('ContextBar', () => {
  it('渲染来源标签与检查点计数', async () => {
    const html = await renderToString(createSSRApp(ContextBar, {
      sourceLabel: '断供传导 · v1', cloneScopeLabel: '3 实体 / 0 关系',
      tick: 2, maxTick: 12, execMode: 'auto', checkpointCount: 1, hasScene: true,
    }))
    expect(html).toContain('断供传导 · v1')
    expect(html).toContain('检查点 1/5')
    expect(html).not.toContain('Step')  // Step 属 TickBar，ContextBar 不应有
  })
})

describe('KpiModal', () => {
  it('show=false 不渲染内容', async () => {
    const html = await renderToString(createSSRApp(KpiModal, {
      show: false, sceneName: 'X', tick: 1, health: { label: '健康 A', color: 'var(--ok)' },
      controllability: { label: 'high', color: 'var(--ok)' }, entityCount: 3,
      branchName: '基线', observationCount: 0, maxTick: 12,
    }))
    expect(html).not.toContain('场景 KPI')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/panels.spec.ts`
Expected: FAIL（组件文件不存在）

- [ ] **Step 3: 实现 4 个 SFC**

`ContextBar.vue` 模板 = monolith `:4-26` 原样（`.ctxbar` 块），把 `{{ sourceLabel }}` 等插值改为 props；按钮 click → `emit('save-checkpoint')` 等；`<select v-model>` 改为 `:value="execMode" @change="emit('exec-mode', ($event.target as HTMLSelectElement).value)"`；`<script setup>` 用 `defineProps<...>()` + `defineEmits<...>()`。`KpiModal.vue` = monolith `:287-304` 模态块，`.mask` 加 `v-if="show"`；`DeleteConfirmModal.vue` = `:276-284`；`NewSceneModal.vue` = `:307-324`（`ontologies` prop 驱动下拉；提交 `emit('create', {...form})`）。四件均**无 scoped style**（依赖 F5 `sandbox.css`）。

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/panels.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/sandbox/components/ContextBar.vue frontend/src/views/sandbox/components/KpiModal.vue frontend/src/views/sandbox/components/DeleteConfirmModal.vue frontend/src/views/sandbox/components/NewSceneModal.vue frontend/src/views/sandbox/__tests__/panels.spec.ts
git commit -m "refactor(sandbox): 拆出 ContextBar/KpiModal/DeleteConfirm/NewScene 组件"
```

---

## Task F7: TickBar 组件（F6 域）

**Files:**
- Create: `frontend/src/views/sandbox/components/TickBar.vue`
- Modify: `frontend/src/views/sandbox/__tests__/panels.spec.ts`（追加 describe）

**Interfaces:**
- Consumes: `RiskItem`（`deriveRiskTop3` 结果类型）
- Produces: props `{ tick, maxTick, scrubTicks:number[], cpTicks:Set<number>, canAdvance:boolean, autoOn:boolean, health:{label,color}, controllability:{label,color}, goalCount:number, riskTop3:{entity_code,score,name}[] }` emits `('toggle-auto')`,`('step',n)`,`('jump',t)`

- [ ] **Step 1: 追加失败测试**

```ts
import TickBar from '../components/TickBar.vue'
describe('TickBar', () => {
  it('渲染 Step 控件与风险 TOP3', async () => {
    const html = await renderToString(createSSRApp(TickBar, {
      tick: 3, maxTick: 12, scrubTicks: [0,1,2,3,4], cpTicks: new Set([0]),
      canAdvance: true, autoOn: false, health: { label: '关注 B', color: 'var(--amber)' },
      controllability: { label: 'high', color: 'var(--ok)' }, goalCount: 2,
      riskTop3: [{ entity_code: 'SUP006', score: 0.8, name: 'SUP006' }],
    }))
    expect(html).toContain('Step +1'); expect(html).toContain('SUP006'); expect(html).toContain('风险 TOP 3')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/panels.spec.ts`
Expected: FAIL（TickBar 不存在）

- [ ] **Step 3: 实现 `TickBar.vue`**

模板 = monolith `:29-62`（`.tickbar` 块）原样，控件 click → emits；`healthLabel/healthColor/controllability/riskTop3` 改 props 注入。无 scoped style。

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/views/sandbox/__tests__/panels.spec.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/sandbox/components/TickBar.vue frontend/src/views/sandbox/__tests__/panels.spec.ts
git commit -m "refactor(sandbox): 拆出 TickBar 组件"
```

---

## Task F8: ScenePanel 组件（F1 域：场景列表 + 主时间线 + 分支）

**Files:**
- Create: `frontend/src/views/sandbox/components/ScenePanel.vue`
- Modify: `panels.spec.ts`

**Interfaces:**
- Produces: props `{ scenes: SandboxScene[], currentSceneId:number|null, timeline: Observation[], branches, selectedBranchId:number|null, compareSet:Set<number> }` emits `('select-scene',id)`,`('open-create')`,`('jump',tick)`,`('pick-branch',id)`,`('toggle-compare',id)`,`('do-compare')`。内部用 `sandboxFormat.sceneStatusLabel/Class`、`sandboxFormat.truncate`。

- [ ] **Step 1: 追加失败测试**

```ts
import ScenePanel from '../components/ScenePanel.vue'
describe('ScenePanel', () => {
  it('空态与分支对比按钮', async () => {
    const html = await renderToString(createSSRApp(ScenePanel, {
      scenes: [], currentSceneId: null, timeline: [], branches: [], selectedBranchId: null, compareSet: new Set(),
    }))
    expect(html).toContain('暂无推演场景'); expect(html).toContain('对比所选分支')
  })
})
```

- [ ] **Step 2:** Run `cd frontend && npx vitest run src/views/sandbox/__tests__/panels.spec.ts` → FAIL（不存在）

- [ ] **Step 3: 实现 `ScenePanel.vue`** = monolith `:67-95`（col ①）原样，插值改 props、click 改 emits。

- [ ] **Step 4:** Run 同上 → PASS

- [ ] **Step 5:** `git add frontend/src/views/sandbox/components/ScenePanel.vue frontend/src/views/sandbox/__tests__/panels.spec.ts && git commit -m "refactor(sandbox): 拆出 ScenePanel 组件"`

---

## Task F9: CausalCanvas 组件（F2 域：四视图 + SVG + 节点详情浮层）

**Files:**
- Create: `frontend/src/views/sandbox/components/CausalCanvas.vue`
- Modify: `panels.spec.ts`

**Interfaces:**
- Consumes: `buildCanvasLayout`/`buildCanvasEdges`（`../sandboxView`）
- Produces: props `{ world: WorldView|null, tick:number, cview:'world'|'onto'|'causal'|'inst', zoomK:number, selectedEntity:string|null, detail: (WorldEntity & {name,isEvent,risk,riskColor,source_ref?,can_act?})|null }` emits `('set-view',v)`,`('zoom',dir)`,`('fit')`,`('pick',code)`,`('close-detail')`,`('open-action')`,`('open-action-for',code)`。SVG 内部由 `buildCanvasLayout(world.entities)` 与 `buildCanvasEdges(nodes, world.causal_edges, tick)` 计算 `canvasNodes/canvasEdges`（`inst` 视图渲染实体列表、`onto` 视图渲染 relations）。

- [ ] **Step 1: 追加失败测试**

```ts
import CausalCanvas from '../components/CausalCanvas.vue'
describe('CausalCanvas', () => {
  it('无世界时空渲染 + 视图 Tab', async () => {
    const html = await renderToString(createSSRApp(CausalCanvas, {
      world: null, tick: 0, cview: 'causal', zoomK: 1, selectedEntity: null, detail: null,
    }))
    expect(html).toContain('世界概览'); expect(html).toContain('因果传播'); expect(html).toContain('施加行动')
  })
})
```

- [ ] **Step 2:** Run `npx vitest run src/views/sandbox/__tests__/panels.spec.ts` → FAIL

- [ ] **Step 3: 实现 `CausalCanvas.vue`** = monolith `:98-156`（col ②）原样；`canvasNodes`/`canvasEdges` 改用 `buildCanvasLayout`/`buildCanvasEdges`（`props.world` 为入参），`detail` 由父传入（父在 `pick` 时调 `getEntity` 得 `can_act`/`source_ref` 再传下）。节点详情浮层 `:147-155` 增显示 `detail.source_ref`（「来源：数据资产 › …」）与 `can_act===false` 时禁用「施加行动」。

- [ ] **Step 4:** Run 同上 → PASS

- [ ] **Step 5:** `git add ... CausalCanvas.vue panels.spec.ts && git commit -m "refactor(sandbox): 拆出 CausalCanvas 组件（复用 sandboxView 布局）"`

---

## Task F10: TracePanel + AdvisorPanel + ActionModal + CompareView（F3/F4/F7 + 对比）

**Files:**
- Create: `frontend/src/views/sandbox/components/TracePanel.vue`
- Create: `frontend/src/views/sandbox/components/AdvisorPanel.vue`
- Create: `frontend/src/views/sandbox/components/ActionModal.vue`
- Create: `frontend/src/views/sandbox/components/CompareView.vue`
- Modify: `panels.spec.ts`

**Interfaces:**
- Produces:
  - `TracePanel` props `{ tview, goalElements, ruleElements, traceObs, futureItems, entityCount, relationCount, tick }` emits `('set-view',v)`（模板 = monolith `:160-203`）
  - `AdvisorPanel` props `{ aview, chat, chatInput, asking, actionLogs, recommendations, hasScene }` emits `('set-view')`,`('ask',q)`,`('send')`,`('update:chatInput',v)`（`:206-247`）
  - `ActionModal` props `{ show, entities: WorldEntity[], templates: ActionTemplate[], target, template, paramFields:{key,label,hint}[], params:Record<string,any>, note:string, noteLock:boolean }` emits `('cancel')`,`('submit')`,`('update:target',v)`,`('update:template',v)`,`('update:params',v)`（`:251-273`）
  - `CompareView` props `{ show, summary: BranchSummary[] }` emits `('close')`；渲染逐分支 `final_tick/final_health/health_delta/goal_reached_count/rule_fired_count/action_count` 表（新建表格，用 F1 的 `branch_summary`）

- [ ] **Step 1: 追加失败测试**

```ts
import TracePanel from '../components/TracePanel.vue'
import AdvisorPanel from '../components/AdvisorPanel.vue'
import CompareView from '../components/CompareView.vue'
describe('TracePanel/AdvisorPanel/CompareView', () => {
  it('TracePanel trace tab 计数框', async () => {
    const html = await renderToString(createSSRApp(TracePanel, {
      tview: 'trace', goalElements: [], ruleElements: [], traceObs: [], futureItems: [],
      entityCount: 3, relationCount: 0, tick: 2,
    }))
    expect(html).toContain('实体'); expect(html).toContain('传播过程')
  })
  it('AdvisorPanel chat tab 输入框', async () => {
    const html = await renderToString(createSSRApp(AdvisorPanel, {
      aview: 'chat', chat: [], chatInput: '', asking: false, actionLogs: [], recommendations: [], hasScene: true,
    }))
    expect(html).toContain('输入消息'); expect(html).toContain('发送')
  })
  it('CompareView 富差异表', async () => {
    const html = await renderToString(createSSRApp(CompareView, {
      show: true, summary: [{ branch_id: 1, name: '基线', final_tick: 2, final_health: '0.5', health_delta: '0.0000', goal_reached_count: 0, rule_fired_count: 2, action_count: 1 }],
    }))
    expect(html).toContain('基线'); expect(html).toContain('0.0000')
  })
})
```

- [ ] **Step 2:** Run `npx vitest run src/views/sandbox/__tests__/panels.spec.ts` → FAIL

- [ ] **Step 3: 实现四件**
  - `TracePanel.vue` = monolith `:160-203`，`obsSevClass/sevIcon/formatFutureSummary` 从 `../sandboxFormat` 引。
  - `AdvisorPanel.vue` = `:206-247`，chat 气泡 `escapeHtml` 已在父处理，此处渲染 `b.html`（`v-html`）。
  - `ActionModal.vue` = `:251-273`，参数控件由 `paramFields` prop 驱动（父用 `template.param_schema_json.properties` 生成，见 F12）。
  - `CompareView.vue`：新建 `<div class="mask" :class="{on:show}" v-if="show">` + `<table>` 渲染 `summary` 每行 8 列（分支名/末 Tick/末 health/health_delta/达成目标/命中规则/行动数），复用 `.modal/.mh/.mb/.mf` class。

- [ ] **Step 4:** Run 同上 → PASS

- [ ] **Step 5:** `git add <4 vue> panels.spec.ts && git commit -m "refactor(sandbox): 拆出 TracePanel/AdvisorPanel/ActionModal/CompareView"`

---

## Task F11: 重写 `SimulationSandbox.vue` 为编排壳

**Files:**
- Modify: `frontend/src/views/sandbox/SimulationSandbox.vue`（整文件重写）

**Interfaces:**
- Consumes: 全部子组件（F6–F10）、`useSandboxStore`（F4）、`sandboxView`（F2）、`sandboxFormat`（F3）、`@/api/sandbox`、`@/api/dataops.listOntologies`
- Produces: 默认导出 SFC `SimulationSandbox.vue`（`componentMap.ts`/`router` 已引用此路径，签名不变）

- [ ] **Step 1: 壳结构**

`<script setup>`：
1. `import '../sandbox/sandbox.css'`（副作用引样式；实际路径 `@/views/sandbox/sandbox.css`）。
2. `const store = useSandboxStore()`；世界数据仍用 `ref`（`scenes/currentScene/branches/world/checkpoints/observations/futureItems/kpis/elements/actionTemplates/actionLogs`）与 `ui` reactive（`show/veil/…`）持有——**不进 store**（store 仅游标）。
3. 游标读写走 `store.setCursor({sceneId,branchId,tick,execMode})`；`tick/maxTick/execMode` computed 从 store 与 currentScene 取。
4. 保留 monolith `:386-708` 的 computed（用 F2/F3 纯函数重写：`canvasNodes→buildCanvasLayout(world.entities)`、`canvasEdges→buildCanvasEdges(...)`、`healthNum/Label/Color→deriveHealth(...)` 等）与加载/推进/行动/顾问/创建/删除函数（逻辑不变，末尾把游标写回 store）。
5. 新增 `detailEntity` 拉取：`pick(code)` → `selectedEntity=code` + `sb.getEntity(sid,code,{branch_id})` 存 `detailData`（含 `can_act`/`source_ref`），传给 CausalCanvas `:detail`。
6. 新建场景轮询：`submitCreate` 后 `await pollSceneReady(scene_id)`（循环 `getScene` 至 `status==='running'||'failed'`，最多 ~30 次 × 600ms），再 `loadScenes`。

`<template>`：`.sandbox-root` > `<ContextBar>` + `<TickBar>` + `.main` 四列 `<ScenePanel>/<CausalCanvas>/<TracePanel>/<AdvisorPanel>` + `<ActionModal>/<CompareView>/<KpiModal>/<NewSceneModal>/<DeleteConfirmModal>`，用 props 下传、`@事件` 上抛调用壳内函数。

- [ ] **Step 2: 类型检查（本任务无 DOM 单测，vue-tsc 把关）**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | Select-String "sandbox|stores/sandbox"`
Expected: 无输出（本次触及文件零 TS 报错；仓库既有无关文件报错不在此列）

- [ ] **Step 3: 组件回归**

Run: `cd frontend && npx vitest run src/views/sandbox src/stores/__tests__/sandbox.spec.ts`
Expected: 全 PASS

- [ ] **Step 4: 后端联跑**

Run: `cd backend && python -m pytest tests/sandbox -q`
Expected: 全绿（≥63）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/sandbox/SimulationSandbox.vue
git commit -m "refactor(sandbox): SimulationSandbox 降级为编排壳，组合 §4.3 子组件 + Pinia 游标"
```

---

## Task F12: 端到端类型/测试收口与手工冒烟

**Files:**
- 无新增（验证任务）

- [ ] **Step 1: 前端全量 sandbox 测试**

Run: `cd frontend && npx vitest run src/views/sandbox src/stores/__tests__/sandbox.spec.ts src/api/__tests__`
Expected: PASS

- [ ] **Step 2: 前端类型**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | Select-String "views/sandbox|stores/sandbox|api/sandbox"`
Expected: 无输出

- [ ] **Step 3: 后端**

Run: `cd backend && python -m pytest tests/sandbox -q`
Expected: 全绿

- [ ] **Step 4: 手工冒烟（本地 dev）**

Run: `cd frontend && npm run dev` → 打开 `/admin?tab=simulation`（或 `/admin/simulation`）：验证四列布局对齐原型、Step+1 推进后因果边点亮、施加行动三态、检查点≤5、新建场景轮询至 running、CompareView 出富差异表、节点详情显示 source_ref/脱敏锁标。
Expected: 页面与 `docs/prototypes/ontology-simulation-sandbox-preview.html` 视觉一致，操作无控制台报错。

- [ ] **Step 5: 无独立提交**（前序 Task 已各自落提交）

---

## Self-Review

**1. Spec coverage：**
- F5 上下文栏 → F6 ContextBar + KpiModal + DeleteConfirm + NewScene ✓
- F6 Tick 控制条 → F7 TickBar ✓
- F1 场景探索 → F8 ScenePanel ✓
- F2 推演画布四视图（含 onto 复用 graph、节点详情 source_ref/masked/can_act）→ F9 CausalCanvas + B1 ✓
- F3 传播过程四 tab → F10 TracePanel ✓
- F4 AI 顾问三 tab → F10 AdvisorPanel ✓
- F7 施加行动三态 + stepwise 两段 → F10 ActionModal（时序在 F11 壳 submitAction）✓
- F8 四态 → F11 壳（veil/空态/错误由 request 拦截器/权限 canAdvance+can_act+replay）✓
- CompareView → F10 + B2 ✓；G1/G2 后端 → B1/B2 ✓
- **缺口**：本体结构视图「复用 `GET /ontologies/{id}/graph`」在 F9 用 relations 渲染占位，若接 graph 端点为增强，MVP 允许以 world.relations 呈现（原型②④本为入口复用，非核心）。已在 F9 注明，非阻塞。

**2. Placeholder scan：** 各步含真实测试代码/实现/命令；组件模板迁移以 monolith 精确行范围为源（具体存在文件，非「类似 Task N」）。无 TBD/TODO。

**3. 类型一致性：** `LayoutNode`/`BranchSummary`/`RiskItem` 跨任务命名统一；`branch_summary` 键名（后端 B2 / api F1 / CompareView F10）一致；`can_act`/`source_ref`（B1 / api F1 / CausalCanvas F9）一致；store action `setCursor/reset`（F4 / F11）一致；`buildCanvasEdges(nodes, edges, tick)` 签名（F2 / F9）一致。

---

## 执行交接

计划完成并保存到 `docs/superpowers/plans/2026-11-01-simulation-sandbox-frontend.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每任务派新 subagent，任务间双阶段评审，快速迭代
**2. Inline Execution** — 本会话内用 executing-plans 批量执行 + 检查点评审

选哪种？
