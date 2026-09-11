# P3 · 第三方知识库连接器设计

> 状态：待评审
> 日期：2026-09-10
> 依赖：P1（同步落库模式需要 P1 的 `kb_dataset` / `kb_document` / `kb_segment`）
> 前端（管理台）设计：见 `2026-09-10-knowledge-governance-frontend-design.md` §9（菜单项：知识治理 → 外部知识库）
> 首批接入：**Notion · 飞书（Feishu/Lark）· 语雀（Yuque）· 钉钉文档**
> 设计原则：移植 Yuxi 的只读连接器抽象 + 充分利用 AgentScope 原生能力

---

## 1. 参考实现：Yuxi `ReadOnlyConnectors`

已完整阅读 `d:\projects\github\Yuxi\backend\package\yuxi\knowledge\implementations\notion.py`（764 行）与 `dify.py`。其抽象设计干净，值得原样移植：

```python
class ReadOnlyConnectors(ABC):
    kb_type: str          # 'notion' | 'feishu' | ...
    name: str             # 'Notion'
    description: str

    @classmethod
    def get_create_params_config(cls) -> dict:
        """声明式表单：options[{key,label,type(password|text|select|number),required,
                                default,placeholder,description,min,max}]"""
    @classmethod
    def validate_additional_params(cls, params: dict | None) -> dict:
        """校验并规范化参数；缺失时读环境变量兜底"""
    async def aquery(self, query_text, kb_id, *, config, agent_call=False, **kw) -> list[dict]:
        """返回 [{content, score, metadata{source, file_id, chunk_id, ...}}]"""
    async def open_file_content(self, kb_id, file_id, offset, limit, *, additional_params) -> dict:
    async def find_file_content(self, kb_id, file_id, patterns, *, use_regex, case_sensitive,
                                max_windows, window_size, additional_params) -> dict:
    def get_query_params_config(self, kb_id, **kw) -> dict:
        """检索参数表单（检索模式 / top_k / 扫描上限 / 片段窗口等）"""
```

**核心价值**：`get_create_params_config()` + `get_query_params_config()` 让**前端零改动**——新增一个连接器只需后端加一个实现类。

**Yuxi 的两个已知短板**（本设计要改）：
1. **检索是纯词项打分、无 embedding**：`_score_page()` 用 title 5.0 / property 3.0 / 行匹配 1.0 的加权，**中文效果差**
2. **只有只读直连，不支持落库建索引**

---

## 2. 核心决策：双模

| 模式 | 行为 | 适用 |
|---|---|---|
| **只读直连**（默认） | live query，不落库、不建索引 | 实时性要求高、数据敏感不宜落地、临时接入 |
| **同步落库**（可选开关） | 定时/手动同步到 P1，走 MWB 的 Qwen3-Embedding 建向量索引 | 需要语义检索、需要跨源统一检索、中文场景 |

**为什么必须支持同步落库**：Yuxi 那套词项打分在中文上效果很差；同步到 P1 后复用 `EMBEDDING_PROVIDER`（GPUStack Qwen3-Embedding-4B / DashScope text-embedding-v3），中文语义检索质量显著更好。

---

## 3. 首批接入源

> 各平台 API 细节（确切端点、分页参数、权限模型）**实施时以官方最新文档为准**，下表为接入前的调研基线。

| 平台 | 认证方式 | 内容模型要点 | 备注 |
|---|---|---|---|
| **Notion** | Integration token（`Bearer` + `Notion-Version` 头；支持 `NOTION_TOKEN` 环境变量兜底） | Data Source / Database → Page → Block 树；`search` API + `data_sources/{id}/query` 双路召回 | Yuxi 已实现，可直接参考其块递归转 Markdown（深度 8 / 块数 2000 上限）与页面缓存 |
| **飞书（Lark）** | `tenant_access_token` 或 `user_access_token`（app_id/app_secret 换取，需缓存与续期） | 云文档 `drive/v1/files` + `docx` Block API；Wiki Space 需单独遍历节点树 | 权限模型较细（需申请文档权限），token 有 2h 有效期需刷新 |
| **语雀（Yuque）** | `X-Auth-Token` 头（个人 Token）或 OAuth；企业版另有域名 | Repo → Doc 两层；`/api/v2/repos/{repo}/docs` | 结构简单，是四个里最好接的 |
| **钉钉文档** | `access_token`（appKey/appSecret 换取） | 文档 / 知识库（wiki）接口；相比前三个开放度较低 | **风险最高**：需先确认目标版本（钉钉文档 vs 知识库）可用接口与权限范围，建议排最后 |

**实施顺序建议**：Notion（有参考实现）→ 语雀（最简单）→ 飞书（token 刷新复杂）→ 钉钉（风险高，先做可行性验证）。

### 3.1 与 AgentScope Channel 的边界（v2 新增，务必区分）

本地 `agentscope 2.0.7.post1` 的 `agentscope/app/channel/` 已内置 **Feishu** 与 **DingTalk** 通道，容易与本子项目混淆。**两者不是一回事**：

| | AgentScope Channel | 本子项目 P3 |
|---|---|---|
| 定位 | **IM 消息通道** —— 让用户在飞书/钉钉里跟智能体对话 | **知识库同步** —— 把飞书/钉钉里的文档内容拉进知识库 |
| 数据方向 | 双向消息流 | 单向拉取（外部 → MWB） |
| 产出 | 会话消息 | `kb_document` / `kb_segment` |
| 能否替代 | 否 | 否 |

**结论**：P3 的飞书/钉钉连接器**仍需自研**（走文档 OpenAPI 拉取内容，而非 IM 通道）。
仅当未来需求变为"在飞书里跟 MWB 智能体聊天"时，才复用 AgentScope Channel —— 那是另一个需求，不在本 spec 范围。

---

## 4. 架构

```
┌────────────────────────────────────────────────────────────┐
│ API 层  /api/v1/kb/external/*                               │
│   connectors（可用连接器元数据）· instances（实例 CRUD）·      │
│   query · sync · sync-jobs                                  │
└──────────────┬─────────────────────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────┐
│ ExternalKBRegistry  连接器注册表（kb_type → 实现类）          │
│ ExternalKBService   实例管理、凭据注入、查询/同步编排          │
└──────────────┬─────────────────────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────┐
│ 连接器实现（每个一个文件）                                     │
│   NotionConnector(ReadOnlyConnectors)                       │
│   FeishuConnector / YuqueConnector / DingTalkConnector      │
│   统一：HTTP 客户端 + 重试退避 + 限流 + 内容转 Markdown        │
└──────────────┬─────────────────────────────────────────────┘
               │ 同步模式
┌──────────────▼─────────────────────────────────────────────┐
│ P1 知识库（kb_document / kb_segment + AgentScope 入库）       │
└────────────────────────────────────────────────────────────┘
```

---

## 5. 数据模型

| 表 | 用途 | 关键字段 |
|---|---|---|
| `kb_external_instance` | 外部知识库实例（继承 `TenantMixin`） | `name · kb_type(String) · credentials_enc(Text, Fernet) · params_enc(Text, Fernet) · sync_enabled(Boolean) · sync_interval_min(Integer) · target_dataset_id(FK → kb_dataset, 同步模式) · last_synced_at · status` |

> 凭据与非凭据参数**分别加密存储**，统一复用 P2 引入的 `DATAOPS_ENCRYPTION_KEY`（Fernet），避免第二套密钥体系。

同步映射另需记录外部文档 ↔ 本地文档的对应关系，用于增量与删除检测：

| 表 | 字段 |
|---|---|
| `kb_external_doc_map`（同样继承 `TenantMixin`，租户隔离做双重保险） | `instance_id · external_doc_id · external_updated_at · document_id(FK → kb_document) · content_hash · deleted(Boolean)` |

唯一约束 `uq_external_doc (instance_id, external_doc_id)`。

---

## 6. 认证与凭据

- **存储**：Fernet 加密（`DATAOPS_ENCRYPTION_KEY`），API 永不返回明文，只回 `has_credentials: bool`
- **参数来源优先级**（沿用 Yuxi）：实例配置 > 环境变量兜底
- **Token 刷新**：飞书 `tenant_access_token`、钉钉 `access_token` 均有有效期 →
  连接器内部维护 token 缓存与提前刷新（剩余有效期 < 5 分钟即刷新），刷新结果**不落库**（避免写放大）
- **权限最小化**：接入时只申请只读权限；飞书/钉钉需在平台上显式授权文档范围

---

## 7. 同步策略（同步落库模式）

```
触发：手动 / 定时（sync_interval_min）
  ├─ 拉取外部文档清单（分页 + 限流）
  ├─ 按 external_updated_at 或 content_hash 判断变更
  │    ├─ 新增 / 变更 → 转 Markdown → 调 P1 入库（幂等 upsert）
  │    └─ 本地有、外部已删 → 标记 deleted 并删除对应 kb_document
  ├─ 更新 last_synced_at 与 kb_external_doc_map
  └─ 失败重试：429 / 5xx 指数退避（尊重 Retry-After），单文档失败不影响整体
```

- **幂等**：`uq_external_doc` + `content_hash` 双保险，重复同步不产生重复切片
- **限流**：各平台 QPS 不同（Notion 约 3 req/s）→ 连接器内令牌桶，可配
- **删除检测**：清单比对，不能只依赖增量时间戳（删除的文档不会出现在增量里）
- **大文档**：单文档大小上限（可配，默认 5MB Markdown），超限截断并记录 warning

---

## 8. 检索

| 模式 | 实现 |
|---|---|
| 只读直连 | 调各源原生搜索 API（Notion `search` / 语雀搜索 / 飞书云文档搜索）→ 本地打分（沿用 Yuxi 加权：`source` 来源加基础分 + 标题/属性/正文词项匹配） |
| 同步落库 | 直接走 P1 的 `PGVectorVDB` 混合检索（向量 + `pg_trgm` + RRF） |

**注意**：只读直连模式的检索质量受限于源平台搜索 API 与本地词项打分，**中文场景建议强制开启同步落库**。这一点需在前端配置界面明确提示。

---

## 9. AgentScope 集成

- 注册为 Tool：`external_kb_search`（指定实例检索）、`external_kb_open`（读取文档正文）、`external_kb_sync`（触发同步）
- 同步落库的实例，其数据在 P1 中，智能体通过 `kb_search` 即可检索，**无需区分来源**
- 若某平台已有 MCP Server，也可经 AgentScope 的 `mcp` 模块接入——但首批四个源建议**原生实现**（MCP Server 可用性与维护质量参差）

---

## 10. 测试

- **契约测试**：四个连接器实现同一 `ReadOnlyConnectors` 接口，`get_create_params_config()` 结构合法（必填项、min/max）
- **凭据**：加密落库、API 不返回明文、环境变量兜底生效
- **同步**：新增 / 变更 / **删除**三种情况均正确；重复同步幂等
- **限流退避**：模拟 429 与 Retry-After，验证退避与最终成功
- **中文检索对比**（关键）：同一中文 query 在"只读直连词项打分"与"同步落库向量检索"下的召回对比，量化增益
- **租户隔离**：租户 A 无法读取租户 B 的实例

##### 10.1 中文检索质量对比基线（P3 Task 8，2026-09-12）

> 基线脚本：`backend/scripts/kb_external_retrieval_bench.py`（确定性伪向量，可复现；
> `scripts/__init__.py` 使测试可复用；回归测试 `tests/kb/test_external_retrieval_bench.py`）。

| 指标 | Mode A 只读直连(词项打分) | Mode B 同步落库(混合向量) |
|---|---|---|
| Recall@1 | 1.0 | 1.0 |
| Recall@5 | 1.0 | 1.0 |
| MRR | 1.0 | 1.0 |

语料 12 篇文档、20 条中文 query（字面/关键词类）。**结论**：在字面对齐信号下两路持平
（差值 0.0）。伪向量（字符/二元组哈希）仅刻画字面字符共现，与 Mode A 共享同一特征，
故**无法度量真实 embedding（如 Qwen3-Embedding）的语义泛化增益**——同义改写、缩写展开等
场景才是同步落库模式的价值所在。要真正验证「同步落库价值」，需在生产 embedding 下重跑
脚本（将 `fake_embed_fn` 替换为 `app.services.kb.ingest_service.build_embed_fn`）并补充
同义/改写类 query 对比召回。原始逐条结果见
`docs/superpowers/specs/2026-09-10-external-kb-retrieval-bench.json`。

---

## 11. 影响面与风险

| 项 | 说明 |
|---|---|
| 新增表 | 2 张，同步 `docs/sql/init.sql` + `app/db/init_models.py` |
| 新增依赖 | 无（`httpx` / `requests` 已有；Fernet 随 `python-jose[cryptography]` 已有） |
| 路由 | `/api/v1/kb/external` |

**风险**：
1. **钉钉文档开放度不确定** —— 建议排最后并先做可行性验证；若不可用则从首批移除，改为 Confluence 或直接只接前三个
2. **飞书/钉钉 token 刷新** —— 实现不当会导致大面积 401；必须做提前刷新 + 并发刷新去重
3. **源平台 API 变更** —— 四个源都是外部 SaaS，接口可能变；连接器需做好版本固定（Notion 已用 `Notion-Version` 固定版本，飞书/钉钉需注意）
4. **同步大库耗时** —— 首次全量同步可能很长；需支持断点续传与进度展示
