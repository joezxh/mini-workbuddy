# 外部知识库接入配置指南（6 种平台）

本文说明在创建「外部知识库」时，如何为 6 种外部平台获取并配置 **AppID / AppSecret** 与**知识库空间 ID**，以及各平台凭据的获取路径、权限要求与常见故障排查。

> 适用版本：MinWorkBuddy 知识库工作台（`/admin/kg-knowledge-manager`）。
> 平台与字段定义以代码为准：`backend/app/connectors/doc_sources/*.py`。

---

## 1. 前置概念

在知识库工作台新建知识库时：

1. 「知识库类型」选择 **外部知识库**（后端 `type=3`）；
2. 在 **外部类型** Tab 中确认接入方式为「连接器拉取」（后端 `kb_format=connector`）；
3. 选择目标平台，填写该平台凭据；
4. 点击 **测试连接**，通过后保存。保存后会自动打开「文档导入向导」，挑选目录与文档入库。

> 「链接配置」Tab 对应的是另一种接入方式「检索代理」（`kb_format=proxy`），用于对接外部检索端点，**不需要** AppID/AppSecret。本文聚焦连接器拉取（6 种平台）。

---

## 2. 六平台凭据字段速查

| 平台 | `source_type` | 凭据字段（UI 名 / 代码名） | 必填 | 空间·范围字段 |
|---|---|---|---|---|
| 飞书 | `feishu` | App ID / `app_id`、App Secret / `app_secret` | 是 | 知识空间 ID / `space_id`（可选） |
| 钉钉文档 | `dingtalk` | AppKey / `app_key`、AppSecret / `app_secret` | 是 | 知识库 ID / `space_id`（可选） |
| 企业微信文档 | `wecom` | CorpID / `corp_id`、CorpSecret / `corp_secret` | 是 | 文档空间 / `space_id`（可选，填空间名） |
| 语雀 | `yuque` | 个人访问令牌 / `token`（`X-Auth-Token`） | 是 | 仓库 Namespace / `namespace`（**必填**） |
| Notion | `notion` | Integration Token / `secret` | 是 | 根页面 ID / `root_page`（可选） |
| web 网站 | `web` | 种子 URL 列表 / `seed_urls`（多行） | 是 | 爬取深度 / `crawl_depth`（可选） |

**重要说明：**

- 真正使用 **AppID + AppSecret 成对凭据** 的是：**飞书、钉钉、企业微信** 三家。
- **语雀**使用「个人访问令牌」单凭据（非 AppID/Secret 体系）。
- **Notion** 使用 Integration Token（等价于 Secret，单凭据）。
- **web 网站**不使用任何密钥，只需种子 URL。
- 「空间 ID」语义因平台而异：飞书=知识空间、钉钉=知识库(workspace)、企业微信=文档空间名、语雀=仓库 Namespace、Notion=根页面 ID、web=爬取深度。

---

## 3. 通用配置流程

```
工作台 → 新建知识库 → 类型=外部知识库
      → 外部类型 Tab → 选择平台
      → 填写 AppID / AppSecret（或对应凭据）+ 空间 ID
      → 测试连接（必须成功）
      → 保存 → 自动打开导入向导 → 勾选文档导入
```

- **测试连接是保存的前置条件**（新建时未测试通过会拦截提交）。
- 凭据为**只入不出**：明文不会回显，编辑时不显示原值；若修改平台或重填凭据，需再次测试连接。

---

## 4. 各平台获取方式

### 4.1 飞书（feishu）

**凭据获取**

1. 打开 [飞书开放平台](https://open.feishu.cn) → 开发者后台；
2. **创建企业自建应用**（企业内部应用）；
3. 进入应用 →「凭证与基础信息」，复制 **App ID**（形如 `cli_a1b2c3d4`）与 **App Secret**。

**权限与授权**

- 需为应用开通知识库 / 云文档权限（如 `wiki:wiki`、`docx:document:readonly`）；
- 应用需**发布版本并经管理员审批**；
- 需把该应用**添加为知识空间成员**，否则列表为空。

**知识空间 ID（`space_id`）获取（三选一）**

- **方式 A · URL 提取**：打开知识库首页，URL 形如
  `https://xxx.feishu.cn/wiki/<space_id>`，路径段即为空间 ID。
- **方式 B · 接口列举**（凭据填入后由系统自动列举）：
  `GET https://open.feishu.cn/open-apis/wiki/v2/spaces?page_size=50`
  从返回 `data.items[].id` 取。
- **方式 C**：**留空**，导入向导会列出该应用可见的全部空间。

**认证机制（代码依据）**

```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
body: { "app_id": ..., "app_secret": ... }  →  tenant_access_token（Bearer 注入）
```

---

### 4.2 钉钉文档（dingtalk）

**凭据获取**

1. 打开 [钉钉开放平台](https://open.dingtalk.com) → 应用开发 → 企业内部应用；
2. 创建应用后进入「基础信息」，复制 **AppKey**（形如 `dingxxxxxx`）与 **AppSecret**。

**权限与授权（关键，本节最易踩坑）**

钉钉文档接口按两套 API 系列划分权限点，开通时请**用中文名搜索**（英文代码在控制台搜不到）：

| API 系列 | 端点 | 所需权限（控制台中文名 / 权限点代码） |
|---|---|---|
| 旧版 doc v1.0（当前代码使用） | `GET /v1.0/doc/workspaces` | 知识库读权限 / `Document.Workspace.Read` |
| | `POST /v1.0/doc/nodes/query` | 知识库节点读权限 / `Document.Node.Read` |
| 新版 wiki v2.0 | `GET /v2.0/wiki/workspaces` | 知识库读权限 / `Wiki.Workspace.Read` |
| | `GET /v2.0/wiki/nodes` | 知识库节点读权限 / `Wiki.Node.Read` |

开通步骤：钉钉开放平台 → 目标应用 → **权限管理** → 搜索「知识库」→ 申请「**知识库读权限**」「**知识库节点读权限**」→ **发布应用版本** → 管理员审批。

> ⚠️ **重要**：官方文档已把旧版 `GET /v1.0/doc/workspaces`（查询用户有权限的知识库列表）移入「历史文档（不推荐）」，并注明**「接口不再支持新应用接入，已接入的应用可继续调用」**。
> 因此**新建的应用**可能无法申请到 `Document.Workspace.Read`，表现为 403 并提示「应用尚未开通所需的权限：[Document.Workspace.Read]」。
> 此时有两条路：
> 1. 直接打开报错信息里的申请链接（形如
>    `https://open-dev.dingtalk.com/appscope/apply?content=<appKey>%23Document.Workspace.Read`），
>    按页提示申请；
> 2. 若确认无法开通（新应用受限），则需迁移到**新版 wiki v2.0 接口**
>    （`Wiki.Workspace.Read` / `Wiki.Node.Read`）——注意新版列表接口**必填 `operatorId`**
>    （操作人 unionId），届时需要额外提供该标识。

**知识库 ID（`space_id`）获取（三选一）**

- **方式 A · 接口列举**：
  1. 先取令牌：`GET https://oapi.dingtalk.com/gettoken?appkey=<AppKey>&appsecret=<AppSecret>`
  2. 再列举：`GET https://api.dingtalk.com/v1.0/doc/workspaces?maxResults=50`
  3. 从返回中取 `workspaceId`。
- **方式 B**：**留空**，导入向导列出全部知识库后点选。
- **方式 C**：在钉钉文档端进入目标知识库，从地址/分享信息中定位知识库标识。

> 注意：钉钉文档 OpenAPI 的列表/取正文端点随版本变动较快，若列举失败优先检查应用权限与接口版本。

---

### 4.3 企业微信文档（wecom）

**凭据获取**

1. 企业微信管理后台 →「我的企业」→ 底部复制 **企业ID（CorpID）**，形如 `wwxxxxxxxxxxxx`；
2. 「应用管理」→ 自建应用 → 创建/选择应用，复制 **Secret（CorpSecret）**。

**权限与授权**

- 需配置应用**可信 IP / 可信域名**（服务器出口 IP 需加入白名单）；
- 需开通**文档（WeDoc）接口权限**。

**文档空间（`space_id`）**

- 语义为**空间名**，**可留空**；留空则由系统按可见文档列举。

**认证机制（代码依据）**

```
GET https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=<CorpID>&corpsecret=<CorpSecret>
→ access_token（以查询参数注入）
```

---

### 4.4 语雀（yuque）

**凭据获取**

1. 登录语雀 → 账户设置 → 开发者 / 访问令牌；
2. 生成 **个人访问令牌**（`X-Auth-Token`），复制填入 `token` 字段。

**仓库 Namespace（`namespace`，必填）**

- 格式：`用户/仓库` 或 `团队/仓库`，例如 `joezxh/handbook`；
- 从仓库 URL 直接取：`https://www.yuque.com/<namespace>`，域名后的两段路径即 Namespace；
- 填写后导入向导**默认直接进入该仓库**；若未填写，则先列出全部可见仓库。

---

### 4.5 Notion（notion）

**凭据获取**

1. 打开 <https://www.notion.so/my-integrations> → **New integration**；
2. 类型选 Internal，复制 **Internal Integration Token**（形如 `ntn_xxxx`），填入 `secret`。

**授权（易漏步骤）**

- 必须在目标页面执行 **Share → 邀请该 integration**，否则无权访问任何页面（表现为列表为空或 403）。

**根页面 ID（`root_page`，可选）**

- 从页面 URL 取 `https://www.notion.so/<PageID>` 中的标识段；
- 留空则从全部可访问页面搜索。

---

### 4.6 web 网站（web）

无需 AppID / AppSecret，配置项为：

- **种子 URL 列表（`seed_urls`，必填）**：每行一个 URL，可填站点首页或具体文档页；
  留空协议时自动补 `https`。
- **爬取深度（`crawl_depth`，可选）**：默认 `1`；`0`=仅种子页，`1`=种子页同域链接，最大 `2`。

---

## 5. 知识空间 / 范围 ID 的通用获取方法

各平台「空间 ID」获取可归纳为三类：

1. **URL 提取**：在平台端打开目标知识库/仓库/页面，取 URL 中的标识段（飞书 `space_id`、语雀 `namespace`、Notion `root_page`）。
2. **接口列举**：填入 AppID/AppSecret 后，由系统调平台接口自动列举，在导入向导中直接点选（飞书 `wiki/v2/spaces`、钉钉 `v1.0/doc/workspaces`）。
3. **留空由向导列举**：绝大多数平台允许留空，导入向导会列出凭据可见的全部空间，最省事且不易填错。

> 建议：**首次配置优先留空**，用「测试连接 + 导入向导列举」确认凭据与权限正确，再回填具体空间 ID 以固定默认入口。

---

## 6. 常见问题排查

| 现象 | 常见原因 | 处理 |
|---|---|---|
| 测试连接失败 | AppID/AppSecret 填错、应用未发布或未审批 | 核对凭证页、发布应用版本并请管理员审批 |
| 连接成功但列表为空 | 应用未加入知识空间 / 未邀请 integration | 飞书：把应用加为知识空间成员；Notion：页面 Share 邀请 integration |
| 401 / 403 | 权限范围不足、可信 IP 未配置 | 开通文档接口权限；企业微信配置可信 IP/域名 |
| 提示「请先选择外部平台」 | 未选平台 | 在外部类型 Tab 选择平台（`externalTypeRequired`） |
| 提示「请填写访问凭据」 | 必填凭据为空 | 补全 AppID/AppSecret 或令牌（`externalCredRequired`） |
| 提示需先测试连接 | 未点测试连接或改了凭据未重测 | 点击「测试连接」通过后再保存（`needTest`） |
| 编辑时不显示原凭据 | 明文凭据只入不出（安全设计） | 属预期行为；如需变更请重填并重新测试 |
| 选了外部类型但配置面板不出现 | 接入方式 Tab 未落在「连接器拉取」 | 切到「外部类型（连接器拉取）」Tab；确认类型=外部知识库 |

---

## 7. 代码位置索引

| 内容 | 位置 |
|---|---|
| 平台注册与字段定义 | `backend/app/connectors/doc_sources/{feishu,dingtalk,wecom,yuque,notion,web}.py` |
| 字段模型 `CredField` / `ProviderMeta` | `backend/app/connectors/doc_sources/base.py` |
| 平台清单接口 | `supported_source_types()`（`doc_sources/__init__.py`） |
| 前端配置入口（外部类型 Tab） | `frontend/src/views/kms/KnowledgeBaseManager.vue` |
| 文档导入向导 | `frontend/src/views/kms/kb/ExternalSourceWizard.vue` |
| 外部相关接口 | `frontend/src/api/kbExternalSource.ts`（`listExternalProviders` / `testExternalSource` / `saveExternalCredentials` / `getExternalConfig`） |
