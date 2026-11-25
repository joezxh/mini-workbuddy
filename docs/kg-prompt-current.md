# KG 抽取当前生效提示词（Prompt 速查）

> 生成日期：2026-11-24。本文件是 `backend/app/services/kb/kg/kg_llm_extractor.py`
> `build_prompt()` 当前版本的快照，供评审与调参参考。
> **运行时以接口为准**：`GET /api/v1/kb/knowledges/{kid}/graph/prompt-preview`
> 返回按当前 KB 配置（含类型约束）拼装的最终生效提示词——构建服务调用的是同一份
> `build_prompt`，预览与生效不存在两套口径。

## 一、首轮抽取提示词（占位符版）

```text
你是知识图谱抽取器。阅读文本，抽取其中的实体与关系，只输出一个 JSON 对象。

输出结构：
{"entities": [{"name": "实体名", "label": "类型", "aliases": ["别名"], "properties": {"属性名": "属性值"}}], "relations": [{"source": "起点实体名", "target": "终点实体名", "relation_type": "关系", "text": "支撑该关系的原文片段"}]}

硬性要求：
1. 实体不超过 {max_entities} 个，关系不超过 {max_relations} 个；
2. name 必须是原文中出现的表述，不要改写、不要补全缩写、不要翻译；
3. relations 的 source 与 target 必须原样出现在 entities 的 name 中，否则会被丢弃；
4. relations 的 text 只保留支撑该关系的原文片段（不超过 60 字）；aliases 与 properties 没有内容时省略；
5. 数字、日期、金额、型号、单位等取值一律写入对应实体的 properties，不要单独建成实体；
6. 关系宁多勿漏：文本中明确成立的关系都要输出（包括低置信的）；不要输出 source == target 的自环关系；
7. 无法确定的字段填空字符串或空对象，不要编造；
8. 只输出 JSON，不要输出解释、前后缀或代码块围栏。

类型约束（实体与关系的类型只能取以下集合，不要自造类型；类型受约束但关系宁多勿漏，文本中明确成立的关系一条都不要漏）：
{schema_hint —— 按 KB 配置生成：
  · schema_source=none     → 本段整体省略
  · schema_source=free_text → 原样注入 KgBuildConfig 里粘贴的约束文本
  · schema_source=cdm      → 自动生成「实体类型: code(name)、…  关系类型: code(name)、…」}

文本：
"""
{切片正文，截到 max_text_chars 字}
"""
```

## 二、截断续抽提示词（首轮撞输出预算后触发）

```text
你是知识图谱抽取器。上一轮抽取的输出因长度限制被截断，排在后面的关系没有输出完整。
请继续阅读文本，只输出**上一轮遗漏**的实体与关系（已抽取的不要重复），只输出一个 JSON 对象。

输出结构（与上一轮相同）：{同上}

已抽取的实体名（不要重复输出）：["…", …]
已抽取的关系（起点|关系|终点，不要重复输出）：["起点|关系|终点", …]

硬性要求：
1. 新增实体不超过 {max_entities} 个，新增关系不超过 {max_relations} 个；
2. name 必须是原文中出现的表述，不要改写、不要翻译；
3. relations 的 source 与 target 必须出现在实体 name 中；
4. relations 的 text 只保留支撑该关系的原文片段（不超过 60 字）；aliases 与 properties 没有内容时省略；
5. 数字、日期、金额、型号等取值写入 properties，不要建成实体；不要输出自环关系；
6. 只输出 JSON，不要输出解释或代码块围栏。

类型约束：{同首轮}

文本：{同首轮}
```

## 三、可配置参数（`pipeline_config.graph`，配置页「构建配置」可改）

| 键 | 默认值 | 说明 |
|---|---|---|
| `max_output_tokens` | 4096 | 单次抽取输出预算上限（与模型行 max_tokens 取小）。小上下文引擎（LM Studio 8192 共享窗口）建议下调到 1024/512 |
| `max_text_chars` | 12000 | 送进 prompt 的正文上限（字符）。6000 时代 90% 切片静默丢尾 |
| `max_entities` | 60 | 单切片实体上限 |
| `max_relations` | 120 | 单切片关系上限 |
| `max_continuation_rounds` | 3 | 截断续抽轮数（1 = 旧行为只补一轮） |
| `concurrency_count` | 8 | 抽取并发 |
| `timeout_seconds` | 60 | 单次 LLM 调用超时 |
| `schema_source` / `schema` / `catalog_id` | free_text / "" | 类型约束来源 |

## 四、供应链场景推荐配置

- 模型：GPUStack qwen3-32b（`model_spec` 指向模型管理对应行）；小模型（0.5B/0.8B 级）实测会自造类型、把属性建成实体、echo 提示词占位文本，不建议用于抽取
- 类型约束：粘贴 `docs/prototypes/supply-chain-kg/free-text-schema-constraint.md` 第一节（10 实体类型 + 15 关系类型 + 抽取纪律）
- 输出预算 4096、正文上限 12000、续抽 3 轮为默认值即可

## 五、2026-11-24 修复前后的措辞差异（为何关系数量翻不起来）

| 位置 | 修复前 | 修复后 | 原因 |
|---|---|---|---|
| 硬性要求 | 实体≤40 关系≤60 | 实体≤60 关系≤120（可配置） | 实体在 JSON 前部，上限过低把关系挤出预算 |
| 类型约束尾缀 | 「不在集合内的类型宁可不标」 | 「类型受约束但关系宁多勿漏…一条都不要漏」 | 「宁可不标」被模型泛化成对关系本身的抑制 |
| 属性 | 无明确要求 | 明确要求数字/日期/金额/型号进 properties | 供应链库实测把「15~28℃」「120 台」建成实体的类型漂移 |
| 自环 | 无约束 | 明确禁止 source==target | 实测出现 华创制造→华创制造 |
| 续抽 | 只补一轮 | 最多 3 轮（无新增即停） | 第二轮续抽自身常又撞顶，遗漏关系丢失 |
| 输出预算 | 默认 1024 | 默认 4096（可下调） | 1024 时关系全在截断点之后 |
| 正文上限 | 6000 | 12000（可下调） | 274 切片 246 个触发 input_truncated |
