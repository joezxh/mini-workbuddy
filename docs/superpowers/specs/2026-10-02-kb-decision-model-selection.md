# 知识库「类 Jev 决策模型」技术选型方案

- 日期：2026-10-02
- 范围：`MinWorkBuddy` 知识库（KMS/RAG）子系统
- 参考项目：<https://github.com/jaredpalmer/kev>（Kev）
- 状态：**调研结论 + 选型建议**，未进入实施

---

## 1. 项目背景

### 1.1 什么是「Jev 类」决策模型

2026-09-15，TypeSafe AI（创始人为前 OpenAI 研究员 Diogo Almeida）发布了 **Jev**，提出 "Decisions, not strings"：

- 不做文本生成，只输出**类型化决策 + 校准概率**；
- 三种原语：`noul`（是/否，返回 P(true)）、`choice`（多选一，返回各选项概率）、`score`（有序等级打分，返回期望等级 + 分布）；
- 一次前向传播完成，不采样任何答案 token，因此没有 JSON 解析失败、没有幻觉文本、输出天然 schema-safe；
- 训练上用 **RLCD**（对严格 proper scoring rule 做强化学习）得到校准置信度；
- 定价输入约 \$0.042 / 1M tokens，输出不收费（因为没有输出 token）。

Jev 是**闭源托管 API + 等待名单**，权重、架构细节、训练数据都不公开。这直接触发了开源社区的复现潮——两周内出现 20+ 个同类项目。本文件的目标就是在这些开源实现中，为 MinWorkBuddy 知识库选出可私有化落地的方案。

### 1.2 为什么知识库需要决策模型

知识库（RAG）链路里存在大量**「有边界的小判断」**，目前要么由规则硬编码、要么交给通用 LLM 生成一段 JSON/文本再解析：

| 现状做法 | 问题 |
|---|---|
| 阈值硬编码（余弦相似度 / RRF 分数） | 分数不是概率，跨集合、跨 embedding 模型不可比，阈值无法迁移 |
| 让 LLM 输出 "是否相关：yes/no" | 一次自回归生成几百毫秒到数秒，还要解析、还可能输出多余文本 |
| rerank（目前**只落库未接线**） | 需要额外 cross-encoder 模型，且输出仍是无概率语义的分数 |

决策模型把这些判断统一成**一次前向 + 校准概率**，天然支持「置信度门控 + 人工兜底」的自动化策略（这正是 Kev README 强调的用法：*"your code can route the confident cases and send the rest to a person"*）。

---

## 2. 需求分析

### 2.1 MinWorkBuddy 知识库现状（代码事实）

**数据模型**（`backend/app/models/kb/`、`backend/app/models/wiki/wiki_knowledge.py`）

- 一级容器 `kms_knowledge`：`type` = 1 llm-wiki / 2 general-kb / 3 external-kb
- 二级形态 `kb_format`：`document | table | qa | connector | proxy`
- 集合 `kms_collection`：`name=kb_{knowledge_id}`、`dimensions`、`schema_config`、`retrieval_settings`
- 文档 `kms_document`：状态机 `pending→processing→completed|failed`
- 分段 `kms_segment`：`chunk_type = text|qa|table_row|image|parent|child`，父子分段、本体过滤列 `class_uris`
- 附件 `kms_segment_asset`（≤2MB、单段 ≤10 张）

**检索与索引**（`backend/app/services/kb/`）

- 向量库为 **pgvector**（无 Milvus）：余弦距离 + HNSW
- `pgvector_store.hybrid_search()` = 向量召回 + **中文子串 LIKE 关键词召回** → **RRF 融合（k=60）**；注释明确指出 pg_trgm 对 CJK 恒返回 0，故用子串召回替代
- Embedding：`rag/embedding_factory.py` → AgentScope `DashScopeEmbeddingModel` 或 OpenAI 兼容端点（GPUStack），维度 768
- `index_mode`：`high_quality`（向量+全文）/ `economy`（仅关键词，零 embedding 消耗），支持升级回填 / 降级保留向量 / 换模型重灌
- **`rerank_provider` / `rerank_model` 只存在于 `kb_collection.retrieval_settings` 配置层，检索链路中未见实际调用** → 这是一个明确的空位

**摄取流水线**：`pipeline_runner.py` 固定三步 `parse → clean → chunk`，由 `pipeline_config` 驱动，与 `POST /kb/pipelines/dry-run` 共用入口；Parser 为 AgentScope 原生 `PDF/Word/Excel/Image/Text`；清洗算子注册表 4 个；Chunker 三种 `ApproxTokenChunker` / `QaChunker` / `ParentChildChunker`；后台由 `job_runner` 托管独立 Session。

**多模态**：`kb_segment_asset` + `multimodal_enabled` 已建模，但 AgentScope 2.0.8 `supports_multimodal` 恒为 False → **「图搜图」不支持，目前只能文搜图**（`2026-09-27-knowledge-unification-design.md` §10.1）。

**前端**：`frontend/src/views/kms/KnowledgeBaseManager.vue`（创建向导按 `kb_format` 分支）、`kms/kb/KbDocumentPane.vue`、`SegmentDetail.vue`、`QaRecordList.vue`、`TableRecordList.vue`。

### 2.2 知识库中的决策点（Decision Points）

| ID | 决策点 | 原语 | 现状 | 收益 |
|---|---|---|---|---|
| D1 | 查询应命中哪个集合 / 哪种形态（document/table/qa/proxy） | `choice` | 全量检索或人工指定 | 减少无效召回、支持跨库路由 |
| D2 | 该查询是否需要检索（打招呼 / 闲聊 / 纯指令） | `noul` | 一律检索 | 省掉 embedding + 向量检索 + LLM |
| D3 | 召回分段是否真正包含答案（证据充分度） | `noul` + `score` | 余弦阈值 / RRF 阈值 | **补上未接线的 rerank 位**，且输出是概率 |
| D4 | 生成答案是否被上下文支持（幻觉风险） | `noul` | 无 | 低置信转人工 / 拒答 |
| D5 | 摄取期分段质量（正文 / 页眉页脚 / 目录 / 噪声） | `choice` | 固定清洗算子 | 降低索引噪声、提升召回质量 |
| D6 | 是否含敏感信息（PII / 密钥 / 涉密） | `noul` | 无 | 与 `kb_permissions` 联动、脱敏 |
| D7 | 是否需要多跳 / 需要向用户追问 | `noul` | 无 | 减少无效多轮 |
| D8 | 该文档值得高质量索引还是经济索引 | `score` | 全库统一 `index_mode` | 省 embedding 成本 |

### 2.3 硬约束（一票否决项）

1. **数据不出网**：禁用任何托管 API（Jev 官方 API、Telnyx 兼容端点），也禁止把语料上传到 Modal 等公共算力做训练。
2. **中文为主**：语料、查询、界面均为中文，英文-only checkpoint 直接出局（除非证明可微调补救）。
3. **私有化可自托管 + 商用友好许可**。
4. **在线延迟预算**：现有 `hybrid_search` 在几十毫秒量级，决策模型增量应 ≤ 50 ms（单请求），批量场景按条摊销。
5. **校准可用**：要能在本项目自己的标注数据上拟合温度并产出可信阈值。
6. **选项基数风险**：集合数量可能 > 20，高基数 `choice` 退化是红旗（Laya 在 Banking77 上 0.425 vs Jev 0.870）。
7. **硬件**：现有 GPU 经 GPUStack 调度（已跑 embedding / LLM），新增模型应控制在 4B BF16（约 8 GB 显存）以内，或可降级到 0.8B。

---

## 3. 候选模型全景比较表

> 数据口径说明：各项目自带基准互不兼容（suite、prompt、选项数都不同），下表**不可横向直接比较分数**，只能看同一张表内的相对位次。凡二手来源均标注「待核」。

| # | 项目名称 | 官方仓库 / 文档链接 | 主要特性与优势 | 适用场景与典型用例 |
|---|---|---|---|---|
| 0 | **Jev**（闭源参照系） | <https://docs.typesafe.ai/api> · <https://docs.typesafe.ai/concepts/system-one> | 首个 System One 模型；`noul/choice/score` 三原语 + 校准概率；RLCD 训练；单次决策 p50 236–276 ms（第三方实测）；无输出 token，成本极低。**闭源、仅托管 API、需等待名单** | 作为**接口事实标准**与性能上界参照；不适合私有化落地 |
| 1 | **Kev** | <https://github.com/jaredpalmer/kev> · HF `jaredpalmer/kev-{0.8b,4b,9b,27b}` | Apache-2.0；Qwen3.5-0.8B/4B/9B-Base + Qwen3.8-27B；LoRA r16 + pointer head；**出厂自带拟合温度**（校准开箱即用）；`kev.serve` 提供 **`POST /v1/systemone`，TypeSafe 官方 SDK 改 base_url 即用**；server 接受 **65,536 token state**、`choice` 最多 **255 选项**；`kev-finetune` skill（Modal H100，一次约 \$1）与 `--init_from` 增量微调；`kev.benchmark` 可对**任意** System One 端点（含 Jev）打分；`kev.compare` 成对 bootstrap；8.2k stars / 326 commits，工程资产最完整 | 需要标准化协议 + 长 state + 高基数选项的场景；工单路由、策略判定、长文档判定；**作为协议层与替换基线** |
| 2 | **Laya** | <https://github.com/NandhaKishorM/laya> · HF `convaiinnovations/laya`(-multilingual / -typed-decisions) · 文档 <https://nandhakishorm.github.io/laya/> | Apache-2.0；**非自回归编码器**（ModernBERT-large 421M 英文 / mmBERT-base 322M 多语言）；**T4 上 32.8–39.5 ms**，批量低至 6.8 ms/question、吞吐 103–332 q/s；内建 `Router` 按文字/语言自动选 checkpoint，**100+ 语言**；生态集成最丰富：`laya[serve\|mcp\|langchain\|llamaindex\|crewai\|onnx\|fast]`、`laya-ts`（浏览器 ONNX）、NixOS 模块、Docker Compose；`min_confidence` 弃权门控、`predict_batch` / `decide_batch`（批量 1.4–3.6×）、`predict_long`（8192 长文档）、`predict_shortlist`（高基数先用 embedding 缩候选）；29.7k stars | 高并发在线路由、多语言意图分类、批量离线打分（摄取期全量分段质检）、边缘/CPU 部署、Agent 框架内嵌（LangGraph 条件边、MCP 工具） |
| 3 | **Intern-Decision（书生·明决）** | <https://github.com/InternLM/Intern-Decision> · HF `internlm/intern-decision` 集合 · 中文 README 见仓库 | Apache-2.0；Qwen3.5 **多模态**微调（冻结视觉塔与投影），0.8B / 2B / 4B（配置支持到 9B）；**七套基准均分 90.02**（同表 Jev 88.74 / SemIf 84.23 / Kev 79.56 / Laya 57.77）；**RTX 4090 单请求均值 44.16 ms**（0.8B 33.98 ms）；Brier **0.3468** / ECE **0.0653**（同表 Jev 0.3584 / 0.0947）；发布**训练（XTuner）、两套推理后端（HF + XTuner）、七套评测、温度拟合脚本**与 96 例分布校准基准；`POST /v1/decisions`（别名 `/v1/jev`）+ Gradio demo；自回归掩码语言建模目标（`<decision>` token 前一位置 logits） | **中文语料**、多模态（图文混合）决策、需要自己训练/校准并留证据链的团队；游戏/机器人/浏览器操作等高频决策 |
| 4 | **SemIf**（原 OpenJev） | <https://github.com/TheoLeeCJ/SemIf-OpenJev> · <https://openjev.com> | MIT（代码）；**冻结开源因果 LM 直读选项 logits**，零训练；支持 Qwen3.5-4B / Qwen3.8-27B EXL3 / llama.cpp GGUF / MLX / MPS；21 个决策直读 **1.023 s** vs 自回归 JSON **5.332 s**（5.21×）；共享 state 前缀复用把 777 决策从 333 s 压到 38.8 s（20.03 decisions/s）；**自带检索类证据**：code retrieval Recall@1 = 1.000、company knowledge Recall@1 = 0.929；per-workload 温度校准（WANLI ECE 0.208→0.069）；TypeSafe 子集一致率 0.845（Jev 0.883） | 研究/基线对照；已有自有模型、不想再训一条权重；CPU/GGUF 或 Apple Silicon 本地跑；**检索排序对照** |
| 5 | **Deem** | <https://github.com/Libertai/deem> · HF `LibertAI/deem-{0.8b,9b}-v1`（许可待核） | Qwen3.5-9B-Base LoRA 合并；**0.8B 权重约 1.4 GB，可常驻内存 / CPU**；9B 在 JevBench public hard 上 **65.8（置信门控）/ 68.9（extended reasoning）**，官方称「最强开源决策模型」；短决策 P50 约 100 ms；服务端为**纯标准库 HTTP**，依赖只有 torch + transformers | 无 GPU 或显存极紧张环境；边缘/笔记本；离线批量 |
| 6 | **OpenDecider** | GitHub `opendecider`（HF blog 2026-09-27）· Apache-2.0（待核） | `nano` ≈ 400M、`small` = Qwen3-4B + LoRA；typed-decisions（2000 决策）**0.796**，对照 Laya 微调 checkpoint 0.766、Jev 1.13 走 API 0.754（成对 bootstrap 95% CI +0.014~+0.044）；`small` 在 200 条未见通用决策上 0.735 | 小体积 + 有界选择题；typed 工作流（客服/发票/安全事件/Agent trace） |
| 7 | **AutoTrust JEV-27B** | HF（AutoTrust AI，2026-09-27/28）· Apache-2.0（待核） | 冻结 Qwen3.8 底座，只训约 1.089 亿参数决策块；六项均分 **84.07**（对照闭源 83.85、开源 4B 约 77.70） | 追求上限、有 80 GB 级单卡；Agent 工作流中的复杂规则判断 |
| 8 | **Jeff** | 见 OSCHINA 报道 <https://www.oschina.net/news/502796>（仓库与许可待核） | Qwen3.5 / Gemma 4 微调的 **zero-shot 分类器**；0.8B–2B；RTX PRO 6000 约 **22 ms** / 次决策，Apple M4 Max 二十多毫秒；一次前向返回校准概率，无生成、无解析 | 本地零样本分类、意图路由、工单分流等轻量嵌入 |
| 9 | **JevK5** | <https://github.com/allebee/jevk5> | 在 Intern-Decision 同表七套基准上均分 **85.16**，**ECE 0.0467（全表最低）**，Brier 0.3662 | 校准质量优先的场景；值得持续关注 |
| — | 其他（生态长尾） | Bespoke Nimble（Qwen3.5-9B LoRA，据称 66%→90%）、NanoJev、simple-jev、Jevlike（约 40 KB）、OpenJev-Diffusion（DiffusionGemma 26B-A4B，choice ≤128）、StartLux-Decision、Instinct（ZooWork，4B 开源 + 27B 免费预览）、Naive-N0.5-Flash（用于训练类 Jev 多模态模型）、`receptron/laya`（Node/TS ONNX 运行时） | 多数为单人或短期项目，证据链弱 | 仅作技术路线参考，不建议生产依赖 |
| — | **JevBench**（评测基准） | <https://github.com/fstandhartinger/jevbench> · <https://benchmarkheaven.com/jev-models> | 面向 Jev 类模型的第三方基准（534 题 / 52 个系统版本），同时评 intelligence / calibration / speed / cost；被 Intern-Decision 直接用作评测套件 | **选型与回归的统一标尺**，见 §6.4 |

---

## 4. 适配度评估

### 4.1 评分矩阵（1–5，5 为最佳）

| 维度（权重） | Intern-Decision-4B | Kev-4B | Laya-multilingual | SemIf-4B | Deem-9B |
|---|---|---|---|---|---|
| 中文能力（20%） | **5** | 2 | 4 | 3 | 3 |
| 私有化 + 商用许可（15%） | **5** | **5** | **5** | 5（MIT 仅代码） | 3（待核） |
| 在线延迟（10%） | 4（44 ms @4090） | 4（18 ms @H100 / 41.5 ms @L40S） | **5**（32.8 ms @T4） | 2（研究级 CLI） | 3（~100 ms） |
| 校准质量（15%） | **5**（ECE 0.065，含拟合脚本） | 4（出厂自带温度） | 2（出厂无温度、必须自拟合） | 3（有脚本） | 3 |
| 零样本可用性（10%） | **4** | **4** | 1（base 接近随机 0.362） | **4** | 3 |
| 高基数选项（>20）（5%） | 3（未公开上限） | **5**（255 选项） | 1（Banking77 0.425） | 3 | 3 |
| 长上下文（5%） | 4（Qwen3.5 原生） | **5**（server 65,536） | 3（默认 1024，需 `max_len=8192`，长文掉点） | 3 | 3 |
| 多模态（5%） | **5**（图像输入） | 1 | 1 | 1（可用多模态基座） | 1 |
| 可微调 / 自建证据链（10%） | **5**（训练+评测+温度脚本齐全） | **5**（`--init_from` 保能力） | 4（Kaggle/MPS notebook） | 1 | 2 |
| 工程集成度（10%） | 3（HF/XTuner 双后端，无 SDK） | 4（`POST /v1/systemone` + 官方 SDK） | **5**（serve/mcp/langchain/onnx/ts 全家桶） | 1 | 3 |
| 社区与可持续性（5%） | 2（391 stars / 4 commits） | **4**（8.2k stars / 326 commits） | **5**（29.7k stars / 1.1k commits） | 2（4.6k stars） | 2 |
| **加权总分** | **4.30** | **3.85** | **3.70** | **2.60** | **2.75** |

### 4.2 逐项结论

- **Intern-Decision-4B**：唯一同时满足「中文原生 + 多模态 + 自带温度拟合 + 可自训 + 45 ms 内 + Apache-2.0」的组合。MinWorkBuddy 的已列痛点（中文检索、图搜图不支持、rerank 未接线）恰好落在它的强项上。最大短板是项目极新（4 commits、391 stars）、**不使用 System One 协议**（`POST /v1/decisions`，字段口径需自建适配）、XTuner 训练环境较重（需 torch 2.6 + flash-attn 2.8.3，与 HF 推理环境必须隔离）。
- **Kev-4B**：工程资产与协议标准化最强，长期最稳。**中文是硬伤**——训练语料是十个英文公开数据集 + 生成策略样例，README 明确建议"另一种语言需要一次短微调"。且 0.8B/4B/9B 主要训练在 ≤384 token 的 state 上，长文档弱（65,536 是 server 上限，不是能力上限）。
- **Laya-multilingual**：延迟、吞吐、多语言、生态集成全部第一，但**零样本近乎随机**（typed-decisions 上 base 0.362 vs 随机 0.318、多数类基线 0.461），高基数 `choice` 崩塌，英文 checkpoint 的 `noul` 会被 `true/false` 标签带偏，多语言 checkpoint 出厂**完全没有温度**。它正确的用法是「微调底座 + 批量打分」，不是开箱即用的决策引擎。
- **SemIf**：价值在方法论与检索侧证据（Recall@1），但只有 CLI scorer，没有服务端、没有标准协议，作为生产组件风险过高；适合作为「零训练对照基线」。
- **Deem / OpenDecider / Jeff / AutoTrust**：数据多为厂商自测或二手报道，中文能力未经验证，社区规模小。Deem-0.8B（1.4 GB、可 CPU）值得作为**无 GPU 环境的降级选项**保留。

---

## 5. 最终选择

### 5.1 推荐方案

> **主选：`Intern-Decision-4B`（书生·明决）**
> **协议兼容备选：`Kev-4B`**（承担 System One 语义契约与长 state 场景）
> **离线批量 / 降级：`Laya-multilingual`（批量）与 `Deem-0.8B`（无 GPU 降级）**
> 三者统一藏在自建的 `DecisionGateway` 抽象层后面，MinWorkBuddy 代码只依赖内部契约（§6.1）。

### 5.2 选择理由

1. **中文是决定性因素。** 知识库的 state 是中文分段 + 中文查询，label 描述也是中文。Kev 的训练语料基本全英文，Laya 英文 checkpoint 在非拉丁文字上直接崩（README：Khmer 0.000 准确率而置信度 0.952）。Intern-Decision 出自上海 AI 实验室、基于 Qwen3.5，中文是主场。
2. **唯一能覆盖「图搜图」缺口。** 现有多模态受限于 AgentScope 2.0.8 `supports_multimodal=False`，只能文搜图。Intern-Decision 是候选里**唯一原生支持图像输入**的开放权重决策模型，可以直接对「图片分段 ↔ 查询」做 typed 判断，把 §2.1 的已知痛点变成可选项。
3. **校准可交付。** 置信门控是本方案的核心价值，阈值必须可信。Intern-Decision 在同表内 Brier 0.3468 / ECE 0.0653 均优于 Jev，且**把温度拟合脚本（`src.eval.collect/fit/replay`）和 96 例分布校准基准一并开源**——这意味着我们可以在自己的 QA 对上复现同一条链路，而不是猜一个阈值。Laya 的多语言 checkpoint 出厂无温度，Kev 的温度是在英文 held-out 上拟合的。
4. **准确率与延迟同时达标。** 七套基准均分 90.02（同表 Jev 88.74），RTX 4090 单请求 44.16 ms（0.8B 33.98 ms），落在 §2.3 的 ≤50 ms 预算内；若延迟吃紧可退到 2B（33.28 ms，均分 84.68）。
5. **许可与私有化干净。** 仓库 Apache-2.0，权重在 HF 开放，可完全内网部署，满足数据不出网约束。
6. **保留 Kev 不是为了"两个都要"，而是为了对冲。** 这个生态只有两周历史，SemIf 已经改过一次名（OpenJev → SemIf）。Kev 的价值在于它把 System One 的 `POST /v1/systemone` 做成了事实标准（TypeSafe 官方 SDK 直接可用、Jev 官方也用同一路由），把它作为内部契约的语义锚点，将来换实现只换 adapter，不动业务代码。

### 5.3 明确不推荐

- **Jev 托管 API**：违反数据不出网。
- **Kev 的 `kev-finetune` skill 默认路径**：它把训练跑在 Modal 上，会把语料上传到公共算力。**必须改为本地/内网 GPU 训练**（`uv run python -m kev.train` 的本地路径是可用的）。
- **Laya 英文 checkpoint 直上生产**：非拉丁文字崩塌、`noul` 标签偏置、高基数退化三个已知缺陷全中知识库场景。

---

## 6. 集成建议

### 6.1 内部契约（与具体模型解耦）

在 `backend/app/services/kb/decision/` 下新增模块，对外只暴露一套语义（对齐 System One，因为它是事实标准）：

```python
# questions.py —— 三种原语
{"<id>": {"type": "noul"|"choice"|"score",
          "instructions": "...",
          "criteria": ...}}          # noul: {true?,false?}  choice: {opt: desc|null}  score: [level,...]

# gateway.py —— 统一返回
DecisionAnswer(type=..., value=..., probabilities={...}, confidence=float)
```

- `state` 支持 `str | dict | list`（结构化分段送进去比拼字符串更省 token、也更可控）。
- **统一在网关层固定置信度口径**：`confidence` 一律取 `answer_confidence = max(p)`（概率口径，不受选项数影响）。Laya 的 `confidence` 是 1 − 归一化熵、Jev 的 `(p_max − 1/K)/(1 − 1/K)` 是另一套口径，**阈值不可跨实现迁移**，必须在网关归一化。
- 配置项：`KB_DECISION_ENABLED`（默认 false）、`KB_DECISION_PROVIDER=intern|kev|laya`、`KB_DECISION_BASE_URL`、`KB_DECISION_MODEL`、`KB_DECISION_TIMEOUT_MS`、`KB_DECISION_FALLBACK=skip`（超时/失败一律放行检索，绝不阻断主链路）。

### 6.2 接线点（按优先级）

| 优先级 | 位置 | 决策点 | 说明 |
|---|---|---|---|
| P0 | `retrieval_service.retrieve()` 召回后、`class_uris` 过滤后 | D3 | 对 top-N 分段批量问「该分段是否包含回答该查询所需信息」（`noul`）+「证据充分度」（`score`），按校准概率重排/截断。**这正是目前 rerank 空位**，且输出带概率，可直接做门控 |
| P0 | `rag_middleware` 的 `rerank_candidate_k` 位置 | D3 | 与 AgentScope RAG 链路对齐，避免两套重排逻辑 |
| P1 | `kb.py` 的 `/kb/retrieve` 入口 | D1、D2 | 先用 `noul`（是否需要检索）短路，再用 `choice` 选集合/形态。**注意**：集合数 > 20 时走「先用向量/关键词粗排缩到 k，再对 k 打分」的两段式，不要一次把全部集合塞进一个 `choice` |
| P2 | `pipeline_runner` 的 `chunk` 之后 | D5、D6 | 摄取期对分段批量打质量标签与敏感标签（可走离线批量，对延迟不敏感 → 此时用 Laya `predict_batch` 或 Deem-0.8B 更划算） |
| P3 | 集合设置面板 | D8 | 按文档打分决定 `index_mode`，省 embedding 成本 |
| P4 | 生成后校验 | D4、D7 | 答案可支持性 / 是否需要追问 |

### 6.3 部署形态

- 新增一个独立容器 `kb-decision`（不要塞进 GPUStack：GPUStack 是 OpenAI 兼容的 LLM 服务平台，托管不了非自回归直接读 logits 的模型）。
- 起步用 **Intern-Decision-2B**（33.28 ms / 均分 84.68 / 显存占用约为 4B 的一半），验证通过后按集合灰度切 4B。
- 服务端：仓库自带的 `scripts/demo.sh` 起的是 Gradio + `POST /v1/decisions`；生产建议只用 HTTP 端点并**自行加鉴权与请求体大小限制**（README 明确提示：默认 loopback、无认证、暴露公网前必须加固）。
- 权重与模型缓存挂卷，避免每次重建容器重新下载。

### 6.4 评测与校准（上线前置条件）

1. **用项目自己的数据建评测集**：`kms_segment` 的 `qa` 形态 + `qa-records` 导入导出能力天然提供「问题 ↔ 标准分段」配对，可作为 D3 的 ground truth；再人工标注 300–500 条覆盖 D1/D2/D5/D6。
2. **必须自己拟合温度**：照搬 Intern-Decision 仓库的 `collect → fit → replay` 三步，`replay` 会校验"零决策翻转"，确保校准不改变 argmax。绝不使用别的 checkpoint 的温度值。
3. **产出阈值表**：对每个决策点，在 held-out 上画出「覆盖率 vs 错误率」曲线，选定错误预算（建议先取 5%）对应的阈值，写进配置而非代码。
4. **回归基准**：接入 <https://github.com/fstandhartinger/jevbench> 作为跨版本回归的统一标尺，避免被厂商自测口径带偏。
5. **负向测试**：每个新门控都要有一个能复现目标缺陷、并在正确原因上失败的测试（例如：注入一段高相似度但无关的分段，断言 D3 门控必须把它拦掉）。

### 6.5 分阶段落地

| 阶段 | 目标 | 验收 |
|---|---|---|
| M0（1 周） | 起容器 + `DecisionGateway` 抽象 + 本地评测集 300 条 + 温度拟合 | 网关可被 `intern` / `kev` 两个 provider 驱动，同一份评测集跑通 |
| M1（2 周） | P0 接线：D3 证据门控，默认关闭，按集合灰度 | 线上召回的无关分段占比下降，且有负向测试 |
| M2（2 周） | P1 接线：D1/D2 路由短路 | 无效检索（无需检索却检索）比例下降，p95 延迟不劣化 |
| M3 | P2 摄取期批量质检 + D6 敏感标注 | 索引噪声下降，与 `kb_permissions` 联动 |
| M4 | 评估 Intern-Decision 多模态能否补上图搜图 | 有对照实验结论，不成则记录为已知限制 |

---

## 7. 潜在风险分析

| # | 风险 | 等级 | 说明与缓解 |
|---|---|---|---|
| R1 | **生态极新，项目可能弃坑或改名** | 高 | 整个 Jev 生态只有两周历史，SemIf 已从 OpenJev 更名，Laya/Kev 都在高频迭代。缓解：业务代码只依赖 §6.1 的内部契约与 `DecisionGateway`，provider 可替换；主选与备选使用**同一份**评测集与阈值产出流程 |
| R2 | **厂商自测口径不可比** | 高 | Intern-Decision 的 90.02 是发布方自报（第三方复现"仍在路上"）；Laya 的 Jev 对比是二手（无 API 访问权）。缓解：一律以本项目自建评测集 + JevBench 为准，不把厂商分数写进验收标准 |
| R3 | **校准漂移** | 高 | 温度必须用自己的 held-out 拟合且定期重拟合（换分段策略、换 embedding、换语料都要重来）。Laya-multilingual 出厂无温度、Kev 的温度拟合于英文数据。缓解：`replay` 校验零翻转 + 每季度重拟合 + 阈值进配置 |
| R4 | **高基数 `choice` 退化** | 中 | Laya 在 77 选项上 0.425（Jev 0.870），根因是选项共享 `head_max_len` token 预算。缓解：集合路由一律走「粗排 → 缩到 k（建议 k ≤ 20）→ typed 决策」两段式；需要大选项集时优先 Kev（支持 255） |
| R5 | **选项顺序 / 标签敏感性** | 中 | Laya 英文 checkpoint 的 `noul` 会被 `true/false` 标签带偏（正例也答 no，issue #156）；Kev 也承认选项顺序会影响答案；Laya 建议用 `option_order` 轮换取平均缓解。缓解：标签用中性语义词或 `A/B` 等不透明标签，并在评测集中固定顺序做回归 |
| R6 | **阈值误用** | 中 | 置信度不是准确率。Kev 在 5% 错误预算下可自动化 0.52–0.69，仍低于 Jev 0.70；Laya 明确要求阈值必须在自己的 held-out 上重新拟合。缓解：门控只做「放行/转人工」，不做「静默丢弃」；低置信一律走保守路径 |
| R7 | **延迟叠加** | 中 | 每个请求加约 40 ms；若逐条调用会在 top-N 上线性放大。缓解：必须用批量接口（Intern-Decision 一次前向多字段；Laya `predict_batch`）并设超时熔断 + 失败放行 |
| R8 | **显存争抢** | 中 | 4B BF16 约 8 GB，与 embedding / LLM 共用 GPU 可能 OOM。缓解：起步 2B；独立容器 + 显式 `CUDA_VISIBLE_DEVICES`；监控显存 |
| R9 | **许可合规** | 中 | Intern-Decision 权重 Apache-2.0，但模型卡保留上游 **Qwen 许可文件**（Qwen 系列为 Tongyi 协议）；SemIf 代码 MIT 但上游模型保留各自许可。缓解：法务复核后再商用；记录每份权重的许可来源 |
| R10 | **训练数据外流** | 高 | Kev 的 `kev-finetune` skill 默认把训练跑在 Modal；任何"用 LLM 帮你造标注"的流程也可能把语料发到公网。缓解：禁用默认路径，训练与标注造数据全部在内网 GPU / 内网模型上完成 |
| R11 | **非 System One 协议的适配成本** | 中 | Intern-Decision 用 `POST /v1/decisions`，字段命名与 TypeSafe 不同。缓解：适配逻辑只在 `client_intern.py` 一处，网关层吸收差异 |
| R12 | **多模态预期落空** | 中 | Intern-Decision 支持图像输入，但 MinWorkBuddy 侧多模态还受 AgentScope 限制、且 HTTP 只接受上传字节（不接受服务器路径/远程 URL）。缓解：M4 阶段做独立对照实验，不成则明确记录为限制，不阻塞 M0–M3 |
| R13 | **服务端安全默认值** | 中 | Intern-Decision 与 Laya 的服务默认 loopback、无鉴权、无请求体大小限制，README 均提示暴露公网前需自行加固。缓解：只监听内网、前置网关鉴权、限制 body 大小与 state token 上限 |

---

## 8. 未验证范围（诚实声明）

以下内容**尚未在本项目环境中实测**，进入 M0 前需补齐：

1. Intern-Decision 权重在 MinWorkBuddy 现有 GPU（驱动 / CUDA 版本）上的实际加载与延迟，以及 XTuner 后端是否必须（HF 后端可用则可省掉 torch 2.6 + flash-attn 的依赖地狱）。
2. Intern-Decision 的 `choice` 选项上限与长 state 行为（README 未公开），直接决定 D1 是否需要两段式路由。
3. Deem / OpenDecider / Jeff / AutoTrust 的许可与中文能力（均为二手来源）。
4. 4B 模型与现有 embedding / LLM 共处同一 GPU 的显存实测。
5. 自建评测集（300+ 条中文标注）的建立与基线数字——**这是所有阈值的前提**。

---

## 9. 参考链接

- Kev：<https://github.com/jaredpalmer/kev>
- Laya：<https://github.com/NandhaKishorM/laya> · <https://huggingface.co/convaiinnovations/laya>
- Intern-Decision：<https://github.com/InternLM/Intern-Decision> · <https://huggingface.co/collections/internlm/intern-decision>
- SemIf：<https://github.com/TheoLeeCJ/SemIf-OpenJev>
- Deem：<https://github.com/Libertai/deem>
- JevK5：<https://github.com/allebee/jevk5>
- JevBench：<https://github.com/fstandhartinger/jevbench> · <https://benchmarkheaven.com/jev-models>
- TypeSafe System One 协议：<https://docs.typesafe.ai/api> · <https://docs.typesafe.ai/primitives>
- Jev 架构分析（Kev 的方法来源）：<https://archerhume.com/posts/jevs-architecture-unmasked>
- 本项目相关：`docs/superpowers/specs/2026-09-27-knowledge-unification-design.md`（§9.6 / §10.1 / §10.8）
