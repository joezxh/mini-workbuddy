# 外部知识库接入配置指南（19 种平台）

本文说明在创建「外部知识库」时，如何为 **19 种外部平台**获取并配置凭据与范围（空间 / 仓库 / 目录 / 订阅源等），以及各平台的权限要求、可选能力开关与常见故障排查。

> 适用版本：MinWorkBuddy 知识库工作台（`/admin/kg-knowledge-manager`）。
> 平台与字段定义**以代码为准**：`backend/app/connectors/doc_sources/*.py`，
> 运行时清单由 `supported_source_types()` 暴露（即 `GET /api/v1/kb/external-sources/providers`）。

---

## 1. 前置概念

在知识库工作台新建知识库时：

1. 「知识库类型」选择 **外部知识库**（后端 `type=3`）；
2. 在 **外部类型** Tab 中确认接入方式为「连接器拉取」（后端 `kb_format=connector`）；
3. 选择目标平台，填写该平台凭据；
4. 点击 **测试连接**，通过后保存。保存后会自动打开「文档导入向导」，挑选目录与文档入库。

> 「链接配置」Tab 对应另一种接入方式「检索代理」（`kb_format=proxy`），用于对接外部检索端点，**不需要**平台凭据。本文聚焦连接器拉取（19 种平台）。

凭据表单由后端 `ProviderMeta.credential_fields` 动态驱动（含是否必填、是否密钥、是否多行），前端不硬编码平台字段；新增平台只需后端注册即可出现。

---

## 2. 十九平台凭据字段速查

| 平台 | `source_type` | 凭据字段（UI 名 / 代码名） | 必填 | 范围 / 可选字段 |
|---|---|---|---|---|
| 飞书知识库 | `feishu` | App ID / `app_id`、App Secret / `app_secret` | 是 | 知识空间 ID / `space_id`（可选，填了走直连） |
| Lark 知识库 | `lark` | 同上（Lark 应用，凭据与飞书**不通用**） | 是 | 同上 |
| 飞书云盘 | `feishu_drive` | `app_id`、`app_secret`、**云盘文件夹 token / `folder_token`** | 是 | `folder_token` 必填，不能留空 |
| Lark 云盘 | `lark_drive` | 同上（Lark 应用） | 是 | 同上 |
| 钉钉文档 | `dingtalk` | AppKey / `app_key`、AppSecret / `app_secret` | 是 | 知识库 ID / `space_id`、操作人 UnionId / `operator_id`（直连必填）；可选 `include_uploaded_files`、`preserve_folder_structure`、`space_name` |
| 企业微信文档 | `wecom` | CorpID / `corp_id`、CorpSecret / `corp_secret` | 是 | 文档空间 / `space_id`（可选，填空间名） |
| 语雀 | `yuque` | 个人访问令牌 / `token`（`X-Auth-Token`） | 是 | 仓库 Namespace / `namespace`（必填）；可选 `folder_mode`、`toc_only` |
| Notion | `notion` | Integration Token / `secret` | 是 | 根页面 ID / `root_page`、导入数据库 / `include_databases`（默认开） |
| GitLab | `gitlab` | 访问令牌 / `access_token`（`PRIVATE-TOKEN`） | 是 | `base_url`（留空=gitlab.com）、同步范围 / `projects` |
| 腾讯 IMA | `ima` | Client ID / `client_id`、API Key / `api_key` | 是 | `base_url`（留空=ima.qq.com）、知识库 ID / `knowledge_base_id` |
| RSS / Atom | `rss` | 订阅源地址 / `feed_urls`（多行） | 是 | 订阅源请求头 / `auth_headers`（私有源）、每源最多条目 / `max_items` |
| Confluence | `confluence` | `base_url` + 三选一：`token`（PAT）/ `username`+`password` / `username`+`api_token` | 是 | 版本 / `edition`（server \| cloud） |
| Seafile | `seafile` | `base_url`、API Token / `api_token` | 是 | 资料库 ID / `repo_id`、资料库内路径 / `path` |
| GitHub | `github` | Personal Access Token / `token` | 是 | `owner`、`repo`、`ref`、路径范围 / `paths`、`base_url`（GHE） |
| Google Drive | `google_drive` | `client_id`、`client_secret`、`refresh_token` | 是 | 根目录 ID / `folder_id`、共享盘 ID / `drive_id` |
| OneDrive / SharePoint | `onedrive` | `tenant_id`、`client_id`、`client_secret` | 是 | Drive ID / `drive_id`、站点 ID / `site_id`、起始目录 / `folder_path` |
| Web Crawler（Sitemap） | `web_crawler` | Sitemap 地址 / `sitemap_url`（多行） | 是 | `include_patterns`、`exclude_patterns`、`max_pages`、`max_depth` |
| Slack | `slack` | Bot / User Token / `token`（`xoxb-` / `xoxp-`） | 是 | 每频道拉取消息数 / `history_limit` |
| 邮件（IMAP） | `imap` | `host`、`username`、`password` | 是 | `port`（993）、`use_ssl`（true）、`mailbox`（INBOX）、`since_days`、`max_messages` |

**凭据形态归纳：**

- **AppID + AppSecret 成对**：飞书 / Lark（含云盘）、钉钉、企业微信、Google Drive、OneDrive；
- **单令牌**：语雀、Notion、GitLab、GitHub、Slack、Seafile；
- **静态双头**：腾讯 IMA（`ima-openapi-clientid` + `-apikey`，无 OAuth）；
- **用户名 + 密码**：IMAP、Confluence（Server Basic）；
- **无密钥**：RSS（可配请求头）、Web Crawler（sitemap 地址）。

---

## 3. 通用配置流程

```
工作台 → 新建知识库 → 类型=外部知识库
      → 外部类型 Tab → 选择平台
      → 填写凭据 + 范围字段
      → 测试连接（必须成功）
      → 保存 → 自动打开导入向导 → 勾选文档导入
```

- **测试连接是保存的前置条件**（新建时未测试通过会拦截提交）。
- 凭据为**只入不出**：明文不会回显，编辑时不显示原值；若修改平台或重填凭据，需再次测试连接。
- 凭据以 Fernet 加密落库（`DATAOPS_ENCRYPTION_KEY`），接口永不返回明文。
- **私有化部署平台**（GitLab / Confluence / Seafile / GitHub Enterprise / IMAP / 内网 RSS 与 sitemap）
  的地址需先加入 `SSRF_WHITELIST`，详见 [第 5 节](#5-私有化部署与-ssrf-白名单)。

---

## 4. 各平台获取方式

### 4.1 飞书系（feishu / lark / feishu_drive / lark_drive）

飞书与 Lark 是**两朵隔离云**：`open.feishu.cn` 创建的应用读不到 Lark 租户的数据，凭据不通用，
因此是 4 个独立平台；API 路径与权限标识符完全相同。

**凭据获取**

1. 打开 [飞书开放平台](https://open.feishu.cn)（Lark 用 <https://open.larksuite.com>）→ 开发者后台；
2. **创建企业自建应用**；
3. 「凭证与基础信息」复制 **App ID**（形如 `cli_a1b2c3d4`）与 **App Secret**。

**权限与授权（两层检查）**

- API 权限：知识库 `wiki:wiki:readonly` / `docx:document:readonly`；云盘 `drive:drive:readonly` /
  `drive:export:readonly`（**云盘不需要 wiki 权限**）；
- 应用需**发布版本并经管理员审批**；
- 资源授权：知识库需把应用**加为知识空间成员**；云盘需把目标文件夹**分享给应用**（或应用所在群）。
  只给 API 权限不授权资源，表现为「测试通过但列表为空」或 403。

**范围字段**

| 平台 | 范围字段 | 说明 |
|---|---|---|
| `feishu` / `lark` | `space_id`（可选） | 知识空间 ID。留空→列举全部可见空间；填写→走「知识空间直连」 |
| `feishu_drive` / `lark_drive` | `folder_token`（**必填**） | 打开云盘目标文件夹，URL 形如 `https://xxx.feishu.cn/drive/folder/<token>`，取该段。云盘无「列出根空间」接口，**不能留空** |

**认证机制（代码依据）**

```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
body: { "app_id": ..., "app_secret": ... }  →  tenant_access_token（Bearer 注入，TTL 缓存）
```

---

### 4.2 钉钉文档（dingtalk）

**凭据获取**

1. 打开 [钉钉开放平台](https://open.dingtalk.com) → 应用开发 → 企业内部应用；
2. 「基础信息」复制 **AppKey**（形如 `dingxxxxxx`）与 **AppSecret**。

**权限与授权（关键，本节最易踩坑）**

钉钉文档接口按两套 API 系列划分权限点，开通时请**用中文名搜索**（英文代码在控制台搜不到）：

| API 系列 | 端点 | 所需权限（控制台中文名 / 权限点代码） |
|---|---|---|
| 旧版 doc v1.0（当前代码使用） | `GET /v1.0/doc/workspaces` | 知识库读权限 / `Document.Workspace.Read`（**已下线**） |
| | `POST /v1.0/doc/nodes/query` | 知识库文档读权限 / `Document.WorkspaceDocument.Read` |
| 新版 wiki v2.0 | `GET /v2.0/wiki/workspaces` | 知识库读权限 / `Wiki.Workspace.Read` |
| | `GET /v2.0/wiki/nodes` | 知识库节点读权限 / `Wiki.Node.Read` |

> ⚠️ **重要**：`Document.Workspace.Read`（知识库列表）已被钉钉官方下线，新版开发者后台**没有申请入口**
> （报错里的申请链接是死循环）。`POST /v1.0/doc/nodes/query`（目录树）只需
> `Document.WorkspaceDocument.Read`，可正常开通。
> **因此新应用必须走「知识库直连」**：填写 `space_id` + `operator_id`，
> 连通测试与目录浏览直接基于目录树接口，不再依赖知识库列表。

**字段说明**

- `space_id`：知识库 ID，取自 `https://alidocs.dingtalk.com/i/spaces/<ID>/overview`；
- `operator_id`：**操作人 UnionId**，必须是对该知识库至少有「仅可查看」权限的成员。
  目录树与正文接口必传，缺失会报 400；可在开发者后台 API Studio 或「查询用户详情」接口获取；
- `include_uploaded_files`：默认 `false`。开启后导入钉盘里的 docx / pptx / xlsx / pdf 附件
  （需额外开通 `Storage.File.Read`，并产生额外存储与向量化成本）；
- `preserve_folder_structure`：默认 `false`。开启后文件名编码为
  `<工作区名>/<子目录>/…/<标题>`，需重新导入一次才会给已入库文档归位；
- `space_name`：仅在开启目录结构保留时用作路径首段。

**认证机制（代码依据）**

```
GET https://oapi.dingtalk.com/gettoken?appkey=<AppKey>&appsecret=<AppSecret>
→ access_token，以请求头 x-acs-dingtalk-access-token 注入（无 Bearer 前缀）
```

---

### 4.3 企业微信文档（wecom）

1. 企业微信管理后台 →「我的企业」→ 底部复制 **企业ID（CorpID）**，形如 `wwxxxxxxxxxxxx`；
2. 「应用管理」→ 自建应用 → 复制 **Secret（CorpSecret）**。

- 需配置应用**可信 IP / 可信域名**；需开通**文档（WeDoc）接口权限**；
- `space_id` 语义为**空间名**，可留空（留空按可见文档列举）。

```
GET https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=<CorpID>&corpsecret=<CorpSecret>
→ access_token（以查询参数注入）
```

---

### 4.4 语雀（yuque）

1. 登录语雀 → 账户设置 → 开发者 / 访问令牌；
2. 生成 **个人访问令牌**（`X-Auth-Token`），填入 `token`。

- `namespace`（**必填**）：格式 `用户/仓库` 或 `团队/仓库`，如 `joezxh/handbook`；
  从 `https://www.yuque.com/<namespace>` 直接取。填写后默认直接进入该仓库。
- `folder_mode`（可选）：
  - `none`（默认）：平铺，文档标题即文件名；
  - `toc`：按语雀目录层级拼文件名（`书名/分组/标题`）。切换后需重新导入一次才会归位。
- `toc_only`（可选）：**仅在 `folder_mode=toc` 时生效**，只导入目录中出现的文档。
  它是「准入过滤器」——已导入的副本不会因取消勾选而删除。

> 语雀仅导入 `type=Doc` 且已发布的文档（Sheet / Table / 草稿跳过）；个人令牌有限流，
> 连接器在逐篇拉取正文时做了间隔控制。

---

### 4.5 Notion（notion）

1. 打开 <https://www.notion.so/my-integrations> → **New integration**（Internal）；
2. 复制 **Internal Integration Token**（形如 `ntn_xxxx`），填入 `secret`。

**授权（易漏步骤）**：必须在目标页面 / 数据库执行 **Share → 邀请该 integration**，
否则无权访问任何内容（表现为列表为空或 403）。Notion 没有 scope 概念，权限是资源级的。

- `root_page`（可选）：根页面 ID，留空则从全部可访问对象搜索；
- `include_databases`（默认 `true`）：把数据库作为可导入节点，整表渲染成 Markdown 表格。
  数据库任一记录变更即整表重建；填 `false` 则只列页面。

---

### 4.6 GitLab（gitlab）

1. GitLab → 头像 → Preferences → Access Tokens（或项目 / 群组级 Settings → Access Tokens）；
2. 勾选 `read_repository`（如需 compare/diff，`read_api` 亦可覆盖）→ 创建 → 复制 `access_token`。

- `base_url`：实例根地址（**不要带 `/api/v4`**），留空使用 `https://gitlab.com`；
- `projects`（可选）：同步范围，支持两种写法
  - 每行一条：`123:main:docs/,README.md`（`project_id:ref:路径`，ref 与路径可省）
  - JSON 数组：`[{"project_id":"123","ref":"main","paths":["docs/"]}]`
  - 留空则列出令牌可见的全部项目（`membership=true`）。

扩展名白名单：Markdown / 文本 / Office / PDF / CSV / JSON / YAML；
**图片与音频不在白名单**（无法转成正文）。文件被清空时会以路径占位导入，覆盖旧正文。

---

### 4.7 腾讯 IMA（ima）

1. 打开 <https://ima.qq.com/agent-interface> 申请凭据；
2. 取得 `client_id` 与 `api_key`（对应请求头 `ima-openapi-clientid` / `ima-openapi-apikey`，**无 OAuth 流程**）。

- `knowledge_base_id`（可选）：填写后直接列出该知识库内容，跳过知识库选择；
- `base_url`：私有化 / 测试端点可填，留空使用 `https://ima.qq.com`；
- 跳过 `media_type=12`（AI 会话）与 `16`（视频）；笔记走独立 note 命名空间读正文；
- **平台侧限制**：IMA 不提供 per-item 更新时间，同名文件原地编辑不会自动感知，需重新导入。

---

### 4.8 RSS / Atom（rss）

- `feed_urls`（必填，可多行或逗号分隔）：RSS2.0 / Atom / JSON Feed 均支持；
- `auth_headers`（可选，密钥字段）：每行一条 `Name: Value`，用于私有订阅源，例如
  `Authorization: Bearer <token>` 或 `Cookie: session=xxx`。
  **这些请求头只发给订阅源，绝不发给文章正文页**；
- `max_items`（可选）：每个源最多条目数，默认 50、上限 500；
- **不支持删除同步**：feed 天然滚动淘汰旧条目，无法区分「下架」与「滚出窗口」。

---

### 4.9 Confluence（confluence）

`base_url` 必填（Cloud 填 `https://<site>.atlassian.net`，代码自动补 `/wiki`）。认证三选一：

| 场景 | 字段 | 认证方式 |
|---|---|---|
| Server / DC（推荐） | `token` | PAT → `Authorization: Bearer <token>`（7.9+，个人设置 → Personal access tokens） |
| Server / DC | `username` + `password` | Basic |
| Cloud | `username`（Atlassian 账号邮箱）+ `api_token` | Basic，token 在 <https://id.atlassian.com/manage-profile/security/api-tokens> 创建 |

- `edition`：`server`（默认）或 `cloud`；
- 只导入 `type=page`，**不导入附件与博客文章**；页面版本号回填为更新时间。

---

### 4.10 Seafile（seafile）

1. Seafile 账号 → 设置 → 生成**用户 API Token**（不允许含空白字符）；
2. `base_url` 填部署地址（支持路径前缀，如 `https://seafile.corp.com/seafile`）；
3. `repo_id` / `path`（可选）：填写后直接列出该资料库目录，留空则列出全部资料库。

下载是**两步**的：先由 API 取 fileserver 临时链接，再请求该链接取内容（第二步不带令牌）。
加密资料库无法读取，列举时跳过；只导入可转 Markdown 的文档格式。

---

### 4.11 GitHub（github）

1. GitHub → Settings → Developer settings → Personal access tokens（fine-grained 或 classic）；
2. 授予目标仓库 `Contents: Read`（classic 用 `repo` 的只读子集）→ 复制 `token`。

- `owner`（可选）：组织或用户名，填写后只列其仓库；
- `repo`（可选）：仓库名，也可填 `owner/repo` 全名，填写后直接定位；
- `ref`（可选）：分支 / 标签，留空用默认分支（文件树用 `HEAD`）；
- `paths`（可选，多行或逗号分隔）：路径前缀，留空=整个仓库；
- `base_url`：GitHub Enterprise 可填，留空使用 `https://api.github.com`。

---

### 4.12 Google Drive（google_drive）

1. Google Cloud 控制台 → APIs & Services → 创建 OAuth 客户端（Desktop 或 Web）；
2. 走 OAuth 授权取得 **refresh_token**，配合 `client_id` / `client_secret` 填入；
   系统会在每次导入时用 refresh_token 自动换取 access_token 并缓存，**无需手工换票**。

- `folder_id`（可选）：根目录 ID，取自 `https://drive.google.com/drive/folders/<id>`，留空为 `root`；
- `drive_id`（可选）：**访问共享盘（Team Drive）时必填**，否则列举不到共享盘内容；
- 权限是**资源级**的：目标文件 / 文件夹必须共享给该 OAuth 客户端对应账号；
- Google 原生文档走 `export?mimeType=text/markdown`（失败降级 `text/plain`），
  上传型文件下载后本地转换（PDF / Office / 文本）。

---

### 4.13 OneDrive / SharePoint（onedrive）

1. Azure 门户 → App registrations → 创建应用，取 `tenant_id` 与 `client_id`，新建 `client_secret`；
2. API 权限授予 **`Files.Read.All` / `Sites.Read.All`**（应用权限），并**完成管理员同意**；
3. 三个字段填入即可，系统用 `client_credentials` 自动换取 Graph 访问令牌并缓存。

- `drive_id`：指定驱动（文档库），留空用 `/me/drive`（个人盘）；
- `site_id`：SharePoint 站点 ID，填写后走 `/sites/{id}/drive`（与 `drive_id` 二选一，优先 `site_id`）；
- `folder_path`（可选）：起始目录名，用于缩小列举范围；
- Office / PDF 下载后本地转换为 Markdown。

> 注：`/me/drive` 在纯应用权限（无用户上下文）场景下可能不可用，
> 生产环境建议使用 `drive_id` 或 `site_id` 明确指定文档库。

---

### 4.14 Web Crawler（web_crawler）

> **本平台取代了早期的「web 网站（web）」**：早期实现只能从种子页抽同域链接下钻两层，
> 覆盖面依赖页面链接；现改为以 sitemap 为入口，能拿到站点声明的完整页面清单。
> 存量知识库需迁移（见本节末尾）。

- `sitemap_url`（必填，可多行）：如 `https://example.com/sitemap.xml`；支持 `sitemapindex` 递归；
- `include_patterns` / `exclude_patterns`（可选，正则）：先用包含规则过滤，再用排除规则过滤；
- `max_pages`（默认 200、上限 1000）、`max_depth`（sitemapindex 递归层数，默认 2、上限 5）；
- 每一跳 URL 都要过 SSRF 校验（内网站点需加白名单）。

**存量数据迁移（`web` → `web_crawler`）**：

```sql
UPDATE wiki_knowledge      SET external_type  = 'web_crawler' WHERE external_type  = 'web';
UPDATE kb_external_doc_map SET source_type    = 'web_crawler' WHERE source_type    = 'web';
UPDATE connector_instance  SET connector_type = 'web_crawler' WHERE connector_type = 'web';
```

---

### 4.15 Slack（slack）

1. Slack API 站点创建 App → OAuth & Permissions → 安装到工作区；
2. 复制 **Bot User OAuth Token**（`xoxb-`）或 User Token（`xoxp-`）填入 `token`。

- 需要 scopes：`channels:read` / `groups:read` / `channels:history` / `groups:history`；
- **私有频道需把机器人邀请进频道**，否则 `channel_not_found`；
- 频道为目录，**只有带回复的消息（讨论串）才作为可导入文档**（单条消息信息量过低）；
- `history_limit`（可选）：每个频道拉取的消息数，默认 200、上限 1000。

---

### 4.16 邮件（IMAP，imap）

1. 在邮箱设置中开启 IMAP/SMTP 服务；
2. 取得客户端专用**授权码**（多数邮箱不使用登录密码），填入 `password`。

| 字段 | 说明 |
|---|---|
| `host` | 邮箱服务器域名（如 `imap.example.com`），**内网服务器需先加 SSRF 白名单** |
| `port` / `use_ssl` | 默认 `993` / `true`；非 SSL 用 `143` 并把 `use_ssl` 置 `false` |
| `username` / `password` | 邮箱账号与授权码 |
| `mailbox` | 默认 `INBOX`；可在「选择文档」时切换其它文件夹 |
| `since_days` / `max_messages` | 按收件时间与数量限制列举（默认不限 / 200，上限 2000） |

正文优先取 `text/plain`，其次 `text/html` 转 Markdown；附件不导入；单封超过 8MB 跳过。
文档 ID 为 `{mailbox}:{uidvalidity}:{uid}`，避免邮箱重建后 UID 复用导致覆盖错文档。

---

## 5. 私有化部署与 SSRF 白名单

连接器默认**不接受任意地址**：公共 SaaS 平台的域名是模块级常量（如 `https://api.github.com`），
从根上消除 SSRF。只有**必须由用户填写地址**的私有化平台才走统一校验通道
（`doc_sources/_host.py`）：

1. 命中 `settings.SSRF_WHITELIST`（逗号分隔域名 / IP，大小写不敏感）→ **放行**；
2. 否则必须过 `app.core.security.is_safe_url` → 拒绝内网 / 环回 / 链路本地 / 保留网段。

因此接入**内网自托管平台**时，需先在后端配置（环境变量或 `.env`）追加白名单：

```env
SSRF_WHITELIST=wiki.corp.local,git.corp.local,192.168.10.20,mail.corp.local
```

适用平台：GitLab、Confluence、Seafile、GitHub Enterprise、IMAP，以及内网部署的 RSS 订阅源与 sitemap。
配置后重启服务生效；未加白名单时测试连接会明确提示「请先把域名加入 SSRF_WHITELIST」。

---

## 6. 常见问题排查

| 现象 | 常见原因 | 处理 |
|---|---|---|
| 测试连接失败 | 凭据填错、应用未发布或未审批 | 核对凭证页、发布应用版本并请管理员审批 |
| 连接成功但列表为空 | 资源未授权给应用 | 飞书：把应用加为知识空间成员 / 云盘文件夹分享给应用；Notion：页面 Share 邀请 integration；钉钉：填写 `space_id` + `operator_id` 走直连 |
| 401 / 403 | 权限范围不足、可信 IP 未配置 | 开通文档接口权限；企业微信配置可信 IP/域名；Google/微软检查管理员同意 |
| 提示「缺少云盘文件夹 token」 | 飞书 / Lark 云盘未提供根目录 | 从 `/drive/folder/<token>` 复制 `folder_token`（云盘不能留空） |
| 提示「请先把域名加入 SSRF_WHITELIST」 | 填了内网私有化地址 | 按[第 5 节](#5-私有化部署与-ssrf-白名单)配置白名单后重启 |
| 钉钉提示 `Document.Workspace.Read` 缺权限 | 该权限点已下线 | 改用「知识库直连」：`space_id` + `operator_id` |
| GitHub / GitLab 看不到目标文件 | 不在扩展名白名单或路径范围外 | 调整 `paths`，或确认文件是 Markdown / Office / PDF（图片与音频不支持） |
| Notion 数据库未出现 | `include_databases` 关闭或未 Share 数据库 | 开启开关并把数据库 Share 给 integration |
| Slack 列不出频道内容 | 机器人未进私有频道 / 无回复的消息 | 邀请机器人进频道；只有讨论串会作为文档 |
| IMAP 连接超时 | 端口或 SSL 设置不符 | SSL 用 993；明文用 143 且 `use_ssl=false` |
| 提示「请先选择外部平台」 | 未选平台 | 在外部类型 Tab 选择平台（`externalTypeRequired`） |
| 提示「请填写访问凭据」 | 必填凭据为空 | 补全凭据字段（`externalCredRequired`） |
| 提示需先测试连接 | 未点测试连接或改了凭据未重测 | 点击「测试连接」通过后再保存（`needTest`） |
| 编辑时不显示原凭据 | 明文凭据只入不出（安全设计） | 属预期行为；如需变更请重填并重新测试 |
| 选了外部类型但配置面板不出现 | 接入方式 Tab 未落在「连接器拉取」 | 切到「外部类型（连接器拉取）」Tab；确认类型=外部知识库 |

---

## 7. 代码位置索引

| 内容 | 位置 |
|---|---|
| 平台实现（19 个，各文件末尾 `register_doc_source`） | `backend/app/connectors/doc_sources/`：`feishu.py`、`lark.py`、`feishu_drive.py`、`lark_drive.py`、`dingtalk.py`、`wecom.py`、`yuque.py`、`notion.py`、`gitlab.py`、`ima.py`、`rss.py`、`confluence.py`、`seafile.py`、`github.py`、`google_drive.py`、`onedrive.py`、`web_crawler.py`、`slack.py`、`imap.py` |
| 飞书系共享核心 | `backend/app/connectors/doc_sources/feishu_core.py`（区域常量表 + 令牌 + wiki/drive ops） |
| 抽象与注册表 `BaseDocSource` / `CredField` / `ProviderMeta` | `backend/app/connectors/doc_sources/base.py` |
| 私有化地址 SSRF 通道 | `backend/app/connectors/doc_sources/_host.py` |
| HTML → Markdown / 字节流 → Markdown | `doc_sources/html.py` / `doc_sources/binary.py` |
| SSRF 防护与白名单配置 | `backend/app/core/security.py`、`backend/app/config/_app.py::SSRF_WHITELIST` |
| 平台清单接口 | `supported_source_types()`（`doc_sources/__init__.py`）→ `GET /api/v1/kb/external-sources/providers` |
| 外部类型校验 | `backend/app/services/kb/kb_format.py::validate_external_type` |
| 导入服务（幂等：新建 / 覆盖 / 跳过） | `backend/app/services/kb/external_import_service.py` |
| 前端配置入口（外部类型 Tab） | `frontend/src/views/kms/KnowledgeBaseManager.vue` |
| 文档导入向导 | `frontend/src/views/kms/kb/ExternalSourceWizard.vue` |
| 外部相关接口 | `frontend/src/api/kbExternalSource.ts`（`listExternalProviders` / `testExternalSource` / `saveExternalCredentials` / `getExternalConfig`） |
| 逐项核对表（`kms.md` 清单 ↔ 实现） | `docs/superpowers/specs/2026-10-27-kb-third-party-connectors-checklist.md` |
