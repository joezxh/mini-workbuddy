# P3 · 第三方知识库连接器实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入 Notion / 飞书 / 语雀 / 钉钉文档 四类专业文档平台，默认**只读直连**，可选**同步落库到 P1**（复用 MWB 的 embedding 做中文语义检索）。

**Architecture:** 移植 Yuxi 的 `ReadOnlyConnectors` 抽象——每个连接器声明 `get_create_params_config()` 表单 schema 与 `validate_additional_params()`，前端据此动态渲染，新增连接器零前端改动。同步模式复用 P1 的入库能力，按 `external_updated_at` / `content_hash` 增量，用清单比对做删除检测。

**Tech Stack:** Python 3.11 / FastAPI / httpx（已有）/ 复用 P1 的 `DATAOPS_ENCRYPTION_KEY`（Fernet）/ pytest + respx（HTTP mock）

**Spec:** `docs/superpowers/specs/2026-09-10-third-party-kb-connectors-design.md`
**依赖：** P1（同步落库目标）

> **边界**：AgentScope `app/channel/` 的飞书/钉钉是 **IM 对话通道**，不是知识库同步。本计划不使用它。

---

## 文件结构

| 路径 | 职责 |
|---|---|
| `backend/app/ai/knowledge/external/base.py` | `ReadOnlyConnectors` 抽象（移植 Yuxi） |
| `backend/app/ai/knowledge/external/http.py` | 统一 HTTP 客户端（重试 + Retry-After + 令牌桶） |
| `backend/app/ai/knowledge/external/notion.py` | Notion 连接器 |
| `backend/app/ai/knowledge/external/yuque.py` | 语雀连接器 |
| `backend/app/ai/knowledge/external/feishu.py` | 飞书连接器（含 token 刷新） |
| `backend/app/ai/knowledge/external/dingtalk.py` | 钉钉文档连接器 |
| `backend/app/ai/knowledge/external/registry.py` | `kb_type → 实现类` 注册表 |
| `backend/app/services/kb/external_service.py` | 实例管理、凭据注入、查询/同步编排 |
| `backend/app/models/kb/external.py` | `kb_external_instance` / `kb_external_doc_map` |
| `backend/app/routers/kb/external.py` | REST 端点 |
| `backend/tests/kb/external/*` | 测试 |

---

### Task 1: 连接器抽象 + HTTP 基础设施

**Files:**
- Create: `backend/app/ai/knowledge/external/base.py`
- Create: `backend/app/ai/knowledge/external/http.py`
- Test: `backend/tests/kb/external/test_http.py`

- [ ] **Step 1: 写失败测试**
```python
@pytest.mark.asyncio
async def test_retries_on_429_and_honors_retry_after(respx_mock):
    respx_mock.get("https://api.example.com/x").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    r = await HttpClient().get("https://api.example.com/x")
    assert r["ok"] is True

def test_rate_limiter_blocks_over_quota():
    limiter = TokenBucket(rate=3, per=1.0)
    assert limiter.try_acquire() and limiter.try_acquire() and limiter.try_acquire()
    assert limiter.try_acquire() is False
```
- [ ] **Step 2:** 运行确认失败
- [ ] **Step 3: 实现** —— `HttpClient`（429/500/502/503/504 指数退避 + 尊重 `Retry-After`）+ `TokenBucket` 限流
- [ ] **Step 4:** 运行确认通过
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): external connector base and resilient HTTP client"
```

- [ ] **Step 6:** 定义 `ReadOnlyConnectors` 抽象（移植自 Yuxi，含 `get_create_params_config` / `validate_additional_params` / `aquery` / `open_file_content` / `find_file_content` / `get_query_params_config`）
- [ ] **Step 7: Commit**

```bash
git commit -m "feat(kb): port ReadOnlyConnectors abstraction"
```

---

### Task 2: 实例与映射表、凭据加密、注册端点

**Files:**
- Create: `backend/app/models/kb/external.py` + Alembic 迁移
- Create: `backend/app/services/kb/external_service.py`
- Create: `backend/app/routers/kb/external.py`
- Test: `backend/tests/kb/external/test_instance.py`

- [ ] **Step 1: 写失败测试**
```python
def test_credentials_encrypted_and_never_returned(client, db_session):
    create_instance(client, {"kb_type": "notion", "token": "secret_abc"})
    assert KbExternalInstance.query.first().credentials_enc != "secret_abc"
    r = client.get("/api/v1/kb/external/instances")
    assert "secret_abc" not in r.text
    assert r.json()[0]["has_credentials"] is True
```
- [ ] **Step 2:** 运行确认失败
- [ ] **Step 3: 实现**（`credentials_enc` / `params_enc` 分别加密，复用 P1/P2 的 Fernet key；API 只回 `has_credentials`）
- [ ] **Step 4:** 运行确认通过
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): external instance CRUD with encrypted credentials"
```

---

### Task 3: Notion 连接器

**Files:**
- Create: `backend/app/ai/knowledge/external/notion.py`
- Test: `backend/tests/kb/external/test_notion.py`

- [ ] **Step 1: 写失败测试**（用 respx mock Notion API：search 分页、block 递归转 Markdown、字数/块数上限截断）
```python
def test_block_tree_to_markdown(respx_mock):
    mock_blocks(respx_mock, [heading1("标题"), paragraph("正文")])
    md = asyncio.run(conn._page_to_markdown(client, "page-1", page))
    assert "# 标题" in md["content"] and "正文" in md["content"]

def test_truncation_at_block_limit(respx_mock):
    mock_2000_plus_blocks(respx_mock)
    assert "[内容过长，已截断]" in md["content"]
```
- [ ] **Step 2:** 运行确认失败
- [ ] **Step 3: 实现**（Bearer + `Notion-Version` 头；游标分页；深度 8 / 块数 2000 上限；页面 markdown LRU+TTL 缓存）
- [ ] **Step 4:** 运行确认通过
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): Notion connector"
```

---

### Task 4: 语雀连接器

**Files:**
- Create: `backend/app/ai/knowledge/external/yuque.py`
- Test: `backend/tests/kb/external/test_yuque.py`

- [ ] **Step 1:** 写失败测试（Repo → Doc 两层遍历；`X-Auth-Token` 认证）
- [ ] **Step 2–4:** 实现并验证
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): Yuque connector"
```

---

### Task 5: 飞书连接器（含 token 刷新）

**Files:**
- Create: `backend/app/ai/knowledge/external/feishu.py`
- Test: `backend/tests/kb/external/test_feishu.py`

- [ ] **Step 1: 写失败测试** —— **两条必须有**：
```python
def test_token_refreshed_before_expiry(respx_mock):
    # 剩余有效期 < 5 分钟时提前刷新
    assert requests_made == ["GET /documents", "POST /auth/token", "GET /documents"]

def test_concurrent_refresh_deduplicated():
    # 10 个并发请求只触发 1 次刷新
    assert refresh_call_count == 1
```
- [ ] **Step 2:** 运行确认失败
- [ ] **Step 3: 实现**（`tenant_access_token` 缓存 + 提前 5 分钟刷新 + 并发去重；云文档 drive/files + docx block API；Wiki Space 节点树遍历）
- [ ] **Step 4:** 运行确认通过
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): Feishu connector with token refresh"
```

---

### Task 6: 钉钉文档可行性验证（**先验证再实现**）

**Files:**
- Create: `docs/superpowers/specs/2026-09-10-dingtalk-feasibility.md`（结论文档）
- Create: `backend/app/ai/knowledge/external/dingtalk.py`（**仅在验证通过后**）

- [ ] **Step 1:** 用真实企业账号申请权限，确认「钉钉文档」与「知识库」两类接口中哪一类可读、权限范围如何
- [ ] **Step 2:** 把结论写入可行性文档（可读取的接口、限流、字段样例）
- [ ] **Step 3:** 若不可用 → 从首批移除，改为 Confluence 或只交付前三个源，**并更新 P3 spec §3**
- [ ] **Step 4:** 若可用 → 实现连接器（同 Task 3–5 的测试结构）
- [ ] **Step 5: Commit**

```bash
git commit -m "docs(kb): DingTalk feasibility conclusion"
```

---

### Task 7: 同步落库到 P1

**Files:**
- Modify: `backend/app/services/kb/external_service.py`
- Test: `backend/tests/kb/external/test_sync.py`

- [ ] **Step 1: 写失败测试** —— **删除检测是重点**：
```python
def test_deleted_remote_doc_removed(db_session, fake_conn):
    sync(instance)                       # 首次：a, b
    fake_conn.set_docs(["a"])            # 远端删除 b
    sync(instance)
    assert doc_map["b"].deleted is True
    assert document_exists("b") is False

def test_resync_is_idempotent(db_session, fake_conn):
    sync(instance); n1 = count_segments(db_session)
    sync(instance); n2 = count_segments(db_session)
    assert n1 == n2                      # content_hash 不变则不重建
```
- [ ] **Step 2:** 运行确认失败
- [ ] **Step 3: 实现**（清单比对做删除检测；`content_hash` 判变更；单文档失败不影响整体；`uq_external_doc` 保证幂等）
- [ ] **Step 4:** 运行确认通过
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(kb): sync external docs into P1 with deletion detection"
```

---

### Task 8: 中文检索质量对比（验收前置）

- [ ] **Step 1:** 准备 20 条中文 query 测试集
- [ ] **Step 2:** 分别测量「只读直连词项打分」与「同步落库向量检索」的召回
- [ ] **Step 3:** 把量化结果写入 spec §10 测试章节；若向量侧无显著增益，需重新评估同步模式的价值
- [ ] **Step 4: Commit**

```bash
git commit -m "test(kb): chinese retrieval quality comparison for external KB"
```

---

## 验收标准

| 项 | 标准 |
|---|---|
| 契约 | 各连接器实现同一抽象，`get_create_params_config()` 结构合法 |
| 凭据 | 加密落库、API 不回显、环境变量兜底生效 |
| 同步 | 新增/变更/删除三种情况正确；重复同步幂等 |
| 限流 | 429 + Retry-After 场景退避并最终成功 |
| 飞书 | token 提前刷新 + 并发刷新去重 |
| 中文检索 | 有量化对比数据 |

## 风险与退路

| 风险 | 退路 |
|---|---|
| 钉钉文档开放度不足 | Task 6 验证不通过即从首批移除，更新 spec |
| 源平台 API 变更 | 连接器固定 API 版本（Notion 已用 `Notion-Version`） |
| 首次全量同步过慢 | 支持断点续传与进度展示 |
| 只读直连中文效果差 | 强制建议开启同步落库（前端配置页明确提示） |
