# SkillHub 接入 MinWorkBuddy 技能管理设计文档

- **状态**：设计稿（待评审）
- **日期**：2026-09-07
- **范围**：将 SkillHub 云市场（及选定的其他 Skill Hub）接入 `frontend/src/views/admin/ai/skill` 技能管理后台
- **负责人**：待定

---

## 1. 背景与目标

MinWorkBuddy 已在 `frontend/src/views/admin/ai/skill` 提供「技能包管理」与「技能仓库」两套视图，后端通过 `SkillHubAdapter` 抽象 + `registry` 注册表支持多来源拉取（当前仅 `git` 一种实现）。`ai_skill_hub_service` 负责仓库 CRUD、列表/检索/分页、一键安装（安装复用 `AiSkillAdminService.import_zip` 落盘）。

目标：把外部 Skill Hub 市场接入此能力，使管理员可在后台**检索、浏览、分类筛选并一键安装**外部技能，无需手动 clone / 复制 SKILL.md。

### 1.1 决策（已确认）

| 项 | 决策 |
|---|---|
| 接入方式 | 后端适配器 + 复用现有技能仓库 UI |
| 鉴权 | 配置项注入 `X-API-Key`（环境变量 `SKILLHUB_API_KEY`），生产可用 |
| UI 呈现 | 初始化时自动种入「官方云市场」仓库（类似现有官方仓库，不可删除） |

---

## 2. 调研结论

### 2.1 SkillHub 开放 API（已确认存在）

- 官方站点：`https://skillhub.cloud.tencent.com/`
- 开放 API 文档仓库：`Tencent/skillhub`（MIT），收录 13 万+ skills
- Base URL：`https://api.skillhub.cn`（环境变量 `SKILLHUB_BASE_URL`）
- 协议：HTTP + JSON，**公开 API 可直接接入**，但 `X-API-Key` 官方称将强制

**核心端点（来自 `docs/api/README.md`）**

| 用途 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 列表 / 检索 | GET | `/api/skills?keyword=&pageSize=&page` | 返回信封 `{code,message,data:{total,skills}}` |
| 一级分类 | GET | `/api/v1/categories` | 平台分类 |
| 排行榜 | GET | `/api/skills/top` | 下载/上新热榜 |
| 技能详情 | GET | `/api/v1/skills/{slug}` | 直出业务对象 |
| 下载（zip） | GET | `/api/v1/download?slug=` | **302 重定向**到对象存储，需 `curl -L` 跟随 |
| 文件清单 | GET | `/api/v1/skills/{slug}/files` | 列表 |
| 单文件 | GET | `/api/v1/skills/{slug}/file` | 302 重定向 |

**调用约定**
- 推荐头：`X-API-Key: <team-key>`（服务端）、`X-Client-User-Id: <hashed>`（哈希用户 ID）
- 时间戳：Unix 毫秒（13 位）
- 错误：`{error:"..."}`，状态码 400/404/413/429/500/503
- 非公开资源统一返回 404

> 注：CLI 安装（`npx`/脚本）底层即调用上述 API；我们走服务端 API，避免在前端/容器执行远程脚本。

### 2.2 候选 Hub 选型评估

| 平台 | 接入方式 | 适配性 | 说明 |
|---|---|---|---|
| **SkillHub** | API 适配器 | ✅ 首选 | 开放 API 已确认，需 `X-API-Key` |
| **vercel-labs/skills** | Git 适配器（零新代码） | ✅ 推荐 | 真实仓库 `github.com/vercel-labs/skills`，标准 `SKILL.md` |
| **trailofbits/skills** | Git 适配器 | ✅ 推荐（安全向） | 真实仓库 `github.com/trailofbits/skills`，安全研究技能 |
| **ClawHub** | API 适配器 | ⚠️ 待验证 | 站点存在、`npx claw install` 可用，但 `/api/docs` 404，接口需确认 |
| **shadcn** | Git/Registry | ⚠️ 待核实 | 官方仓库路径不明确，先用社区镜像或延后 |
| Anthropic Skills | — | ❌ | Claude Code 内置，无独立可拉取 registry |
| Docker Agent Skills | — | ❌ | 镜像交付（`docker skill install`），不匹配 zip 导入流 |
| Jupyter | — | ❌ | 绑定 JupyterLab 扩展 |
| awesome-agent-skills | — | ❌ | 仅索引列表，非托管源 |

**首期接入集合（Tier 1）**
1. `SkillHub`（API 适配器，本方案核心）
2. `vercel-labs/skills`（Git 适配器，仅种入官方仓库 URL）
3. `trailofbits/skills`（Git 适配器，仅种入官方仓库 URL）

**Phase 3 候选**：`ClawHub`（确认 API 后补一个 `ClawHubAdapter`，与 `SkillHubCloudAdapter` 同构）。

---

## 3. 架构设计

### 3.1 现有接缝（复用）

```
SkillHubAdapter (ABC)            # base.py
  ├─ list_remote() -> [SkillHubEntry]
  ├─ fetch(entry) -> bytes (zip)  # 返回与 import_zip 兼容的 zip
  ├─ get_readme(entry) -> str     # 可选：详情/文档
  └─ get_versions(entry) -> [...] # 可选：版本

registry.py                      # register_adapter(cls)，get_adapter(name)
GitHubAdapter(name="git")        # git_hub.py：clone + 扫 SKILL.md + 打包 zip
WorkbuddyHubAdapter(name="workbuddy")  # 占位骨架

AiSkillHubService                # 仓库 CRUD + _build_adapter + list_skills + install_skill
  └─ _build_adapter(repo) 当前写死返回 GitHubAdapter
```

### 3.2 目标结构

```
SkillHubAdapter (ABC)            # 不变
  ├─ GitHubAdapter("git")        # 不变
  ├─ SkillHubCloudAdapter("skillhub")   # 新增：代理 api.skillhub.cn
  └─ (ClawHubAdapter("clawhub")  # Phase 3，同构)

AiSkillHubService
  └─ _build_adapter(repo): 按 repo.source_type 选择适配器
  └─ ensure_official_repos(): 种入 SkillHub 云市场 + vercel-labs + trailofbits
```

`SkillHubCloudAdapter` 与 `GitHubAdapter` 实现同一接口，`fetch()` 均返回 zip 字节流，`AiSkillAdminService.import_zip` 落盘逻辑完全复用——这是改动量最小的根本原因。

---

## 4. 后端改动

### 4.1 模型：`ai_skill_hub_repo.py`

在 `AiSkillHubRepo` 增加：

- `source_type`：`String(20)`，默认 `"git"`，可选值 `git | skillhub`（索引/校验用）
- `url` 改为**可空**（云市场源不依赖 Git 地址）；保留 `branch/username/password` 对云源无效

```python
source_type = Column(String(20), nullable=False, server_default="git",
                     comment="来源类型：git=Git仓库, skillhub=SkillHub云市场")
# url 字段保留但允许为空（云市场源无 Git 地址）
```

> 兼容迁移：旧数据 `source_type` 默认 `git`，行为不变；`url` 唯一约束对云源（`url=""`）需调整——云市场官方仓库用固定 `source_type` 保护而非 `url` 唯一性。

### 4.2 新增适配器：`app/ai/skills/hub/skillhub.py`

```python
@register_adapter
class SkillHubCloudAdapter(SkillHubAdapter):
    name = "skillhub"

    def __init__(self, api_key: str = "", base_url: str = "https://api.skillhub.cn"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or settings.SKILLHUB_API_KEY or ""

    def _headers(self) -> dict:
        h = {}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def list_remote(self) -> list[SkillHubEntry]:
        # 分页拉取 /api/skills?keyword=&pageSize=&page，合并去重
        # 每个 skill 映射为 SkillHubEntry(
        #   id=slug, name=name, version=version, description=description,
        #   meta={category, category_name, tags, slug, remote_url, readme_url})
        ...

    def fetch(self, entry: SkillHubEntry) -> bytes:
        # GET /api/v1/download?slug=<slug> 跟随 302，返回 zip 字节
        # 直接交给 import_zip（SkillHub 下载即标准 skill zip）
        ...

    def get_readme(self, entry: SkillHubEntry) -> str:
        # GET /api/v1/skills/{slug} 详情 -> 渲染 markdown
        ...
```

要点：
- **检索**：`list_remote` 支持 `keyword` 透传；后端 `list_skills` 已有本地 `q` 过滤，二者可并存（优先用 SkillHub 服务端检索）。
- **分类**：额外调用 `/api/v1/categories` 得到一级分类；`list_categories` 服务方法对云源返回该结果。
- **下载**：`fetch` 用 `requests`/`httpx` 带 `X-API-Key` 并 `allow_redirects=True` 取 zip。
- **超时**：安装接口已在 `src/api/skillHub.ts` 放宽到 120s；后端 `fetch` 同样需放宽（zip 可能较大）。

### 4.3 注册：`registry.py`

`SkillHubCloudAdapter` 经 `@register_adapter` 自动注册为 `"skillhub"`。

### 4.4 服务：`ai_skill_hub_service.py`

```python
def _build_adapter(self, repo) -> SkillHubAdapter:
    if repo.source_type == "skillhub":
        return SkillHubCloudAdapter(api_key=settings.SKILLHUB_API_KEY)
    # 默认 git
    return GitHubAdapter(repo.id, repo.url, repo.branch, username, password)

def ensure_official_repos(self) -> None:
    # 若不存在则种入：
    #   1) SkillHub 云市场  source_type=skillhub, url="", official=True
    #   2) vercel-labs/skills  source_type=git, url="https://github.com/vercel-labs/skills"
    #   3) trailofbits/skills  source_type=git, url="https://github.com/trailofbits/skills"
    ...
```

- `refresh_repo`：云源改为「刷新分类/列表缓存」而非 `ensure_cloned(force=True)`（Git 源保持原逻辑）。
- `list_skills` / `install_skill`：对云源直接调用适配器，无本地 clone。

### 4.5 配置：环境变量

`backend/app/core/config.py` 增加：

```python
SKILLHUB_API_KEY: str = os.getenv("SKILLHUB_API_KEY", "")
SKILLHUB_BASE_URL: str = os.getenv("SKILLHUB_BASE_URL", "https://api.skillhub.cn")
```

`.env.example` 标注：`SKILLHUB_API_KEY=`（留空则仅能在官方未强制前试公共接口）。

---

## 5. 前端改动

文件：`frontend/src/views/admin/ai/skill/SkillManagement.vue`、`frontend/src/api/skillHub.ts`

改动极小（现有仓库/分类/检索/安装接口全可复用）：

1. **仓库列表**：展示 `source_type` 徽标（「云市场」/「Git」）；SkillHub 官方仓库标记蓝色「官方」。
2. **刷新按钮**：`source_type=="skillhub"` 时按钮文案改为「更新分类」，调用 `refreshHubRepo` 但后端走缓存刷新（无 clone）。
3. **未配置 Key 提示**：若后端返回 401/特定错误，列表区显示提示条「未配置 SKILLHUB_API_KEY，部分技能可能无法下载」。
4. **分类**：云源分类来自 `/api/v1/categories`，`listHubCategories` 已支持，无需新增字段。
5. **安装**：`handleInstallHubSkill` 已存在，逻辑不变（后端代理下载 + `import_zip`）。

> 现有「技能市场 / 仓库」Tab 已能列出多仓库技能；SkillHub 云市场作为其中一个官方仓库自动出现，无需新增独立 Tab。

---

## 6. 数据流（端到端）

```
管理员打开「技能仓库」
  └─ 前端 listHubRepos() -> 后端 list_repos()
        ├─ ensure_official_repos() 自动种入 SkillHub 云市场 + vercel-labs + trailofbits
  └─ 选择「SkillHub 云市场」
        └─ listHubCategories(repoId) -> 后端 list_categories() -> SkillHubCloudAdapter(SkillHub)
              └─ GET /api/v1/categories
        └─ listHubSkills(repoId, {q, category, page}) -> 后端 list_skills()
              └─ SkillHubCloudAdapter.list_remote()
                    └─ GET /api/skills?keyword=&pageSize=&page
  └─ 点击「安装」
        └─ installHubSkill(repoId, slug) -> 后端 install_skill()
              └─ SkillHubCloudAdapter.fetch(entry)
                    └─ GET /api/v1/download?slug=  (跟随 302)
              └─ AiSkillAdminService.import_zip(db, zip_bytes)  -> 落盘 backend/data/skills/
        └─ 前端 loadPackages() 刷新本地技能包列表
```

---

## 7. 分类与字段映射

| SkillHub 字段 | 内部 HubSkillItem | 说明 |
|---|---|---|
| `slug` | `id` | 安装 URL 路径参数 |
| `name` / `title` | `name` | |
| `description` | `description` | |
| `category` | `category` / `category_name` | 一级分类 |
| `tags` | `tags` | |
| `version` | `version` | |
| `readme_url` / 详情 | `meta.readme_url` | 详情预览 |

> vercel-labs / trailofbits 走 `GitHubAdapter`，沿用现有 `category_index.json` 或 `SKILL.md` frontmatter 解析，无需额外映射。

---

## 8. 安全与错误处理

- **Key 安全**：`SKILLHUB_API_KEY` 仅存于后端环境变量/配置，绝不下发前端；日志脱敏。
- **重定向安全**：`fetch` 跟随 302 时校验跳转域名属于可信对象存储域（避免开放重定向到内网/恶意地址）。
- **降级**：`list_remote` 失败（网络/限流）时返回空列表而非 500（现有 `list_skills` 已有 `RuntimeError` 降级逻辑，云源需同样包裹）。
- **限流**：429 时后端退避重试一次并提示「SkillHub 限流，请稍后重试」。
- **大小限制**：`fetch` 对 zip 大小设上限（如 50MB），超限拒绝并提示。
- **官方仓库保护**：`is_official=True` 不可删除/改地址（现有约束沿用）。

---

## 9. 实施阶段与任务拆解

### Phase 1（核心，必做）
- [ ] 模型加 `source_type`，`url` 可空 + 迁移脚本
- [ ] 新增 `skillhub.py`：`SkillHubCloudAdapter`（list/fetch/get_readme + 分类）
- [ ] `registry.py` 注册；`ai_skill_hub_service` 改为按 `source_type` 选适配器 + `ensure_official_repos`
- [ ] `config.py` 加 `SKILLHUB_API_KEY` / `SKILLHUB_BASE_URL`，更新 `.env.example`
- [ ] 前端仓库徽标、云源刷新文案、Key 缺失提示
- [ ] 联调：检索 / 分类 / 安装 / 落盘

### Phase 2（零成本）
- [ ] `ensure_official_repos` 种入 `vercel-labs/skills`、`trailofbits/skills`（Git 适配器，无需新代码）
- [ ] 联调两个 Git 源的列表/安装

### Phase 3（待定）
- [ ] 确认 ClawHub API 后新增 `ClawHubAdapter`（与 `SkillHubCloudAdapter` 同构），种入官方仓库

---

## 10. 验收标准

1. 后台「技能仓库」自动出现「SkillHub 云市场」「vercel-labs/skills」「trailofbits/skills」三个官方仓库。
2. 在 SkillHub 云市场可输入关键词检索、按分类筛选、分页浏览，结果与 `api.skillhub.cn` 一致。
3. 点击「安装」可将 SkillHub 技能下载并落盘为本地技能包，出现在「技能包管理」。
4. 未配置 `SKILLHUB_API_KEY` 时有明确提示；配置后下载正常。
5. Git 源（vercel-labs / trailofbits）检索/安装行为与现有官方 Git 仓库一致。
6. 网络异常/限流时界面不白屏，有明确错误提示。

---

## 11. 风险与已知问题

- **SkillHub API 强制 Key 时间线未知**：当前为 recommended，未来可能强制；设计已预留 `SKILLHUB_API_KEY`。
- **下载端点细节**：`/api/v1/download` 的精确 query 参数（slug 名称）以官方 `docs/api/README.md` 为准，实现时若字段名有出入需微调。
- **分类体系不一致**：SkillHub 一级分类与内部 `skill_category` 字典不完全对齐，首期直接透传 SkillHub 分类名（不做硬映射），后续可加映射表。
- **ClawHub / shadcn**：接口与官方仓库待确认，不在首期范围。

---

## 附录 A：SkillHub API 速查

```
Base: https://api.skillhub.cn
列表:   GET /api/skills?keyword=<kw>&pageSize=<n>&page=<n>
分类:   GET /api/v1/categories
详情:   GET /api/v1/skills/{slug}
下载:   GET /api/v1/download?slug=<slug>   # 302 -> 对象存储
文件:   GET /api/v1/skills/{slug}/files
单文件: GET /api/v1/skills/{slug}/file
Header: X-API-Key: <key>   (X-Client-User-Id: <hashed>)
列表响应: { code:0, message:"success", data:{ total, skills:[...] } }
```

## 附录 B：关键文件清单

```
backend/app/ai/skills/hub/base.py              # SkillHubAdapter ABC（接口契约）
backend/app/ai/skills/hub/registry.py          # 适配器注册表
backend/app/ai/skills/hub/git_hub.py           # GitHubAdapter（参考实现）
backend/app/ai/skills/hub/skillhub.py          # 【新增】SkillHubCloudAdapter
backend/app/services/ai/ai_skill_hub_service.py# 仓库服务 + _build_adapter
backend/app/models/ai/ai_skill_hub_repo.py     # 仓库模型（加 source_type）
backend/app/core/config.py                     # SKILLHUB_API_KEY / BASE_URL
frontend/src/api/skillHub.ts                   # 前端 API 封装
frontend/src/views/admin/ai/skill/SkillManagement.vue  # 技能管理视图
```
