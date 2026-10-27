# 第三方知识库连接器接入 · 逐项核对表

> 依据：`D:\projects\github\WeKnora\docs\kms.md` 第 3 章「逐来源明细」+ 第 4 章「占位连接器清单」
> 落地仓库：MinWorkBuddy（`backend/app/connectors/doc_sources/`，沿用既有 `BaseDocSource` 规范）
> 完成日期：2026-10-27

## 一、清单项 → 实现对照

| # | 清单项（文档章节） | source_type | 实现文件 | 注册 | 单测 | 前端接线 |
|---|---|---|---|---|---|---|
| 1 | 飞书知识库（§3.1） | `feishu` | `feishu.py`（逻辑在 `feishu_core.py`） | ✅ | ✅ `test_doc_sources.py` / `test_doc_sources_feishu.py` | ✅ |
| 2 | Lark 知识库（§3.1） | `lark` | `lark.py`（`feishu_core.FeishuWikiSource`，区域 `open.larksuite.com`） | ✅ | ✅ `test_doc_sources_feishu.py::test_lark_wiki_uses_larksuite_domain` | ✅ |
| 3 | 飞书云盘（§3.2） | `feishu_drive` | `feishu_drive.py`（`FeishuDriveSource`，`folder_token` 必填） | ✅ | ✅ `test_doc_sources_feishu.py` | ✅ |
| 4 | Lark Drive（§3.2） | `lark_drive` | `lark_drive.py` | ✅ | ✅ `test_doc_sources_feishu.py::test_lark_drive_uses_larksuite_domain` | ✅ |
| 5 | Notion（§3.3） | `notion` | `notion.py`（本次补 Database 查询与表格渲染） | ✅ | ✅ `test_doc_sources.py` / `test_doc_sources_batch3.py` | ✅ |
| 6 | 语雀（§3.4） | `yuque` | `yuque.py`（本次补 `folder_mode` / `toc_only`） | ✅ | ✅ `test_doc_sources.py` / `test_doc_sources_batch3.py` | ✅ |
| 7 | 钉钉文档（§3.5） | `dingtalk` | `dingtalk.py`（本次补 `include_uploaded_files` / `preserve_folder_structure`） | ✅ | ✅ `test_doc_sources.py` / `test_doc_sources_batch3.py` | ✅ |
| 8 | GitLab（§3.6） | `gitlab` | `gitlab.py` | ✅ | ✅ `test_doc_sources_batch1.py` | ✅ |
| 9 | 腾讯 IMA（§3.7） | `ima` | `ima.py` | ✅ | ✅ `test_doc_sources_batch1.py` | ✅ |
| 10 | RSS / Atom（§3.8） | `rss` | `rss.py` | ✅ | ✅ `test_doc_sources_batch1.py` | ✅ |
| 11 | Confluence（§3.9） | `confluence` | `confluence.py` | ✅ | ✅ `test_doc_sources_batch1b.py` | ✅ |
| 12 | Seafile（§3.10） | `seafile` | `seafile.py` | ✅ | ✅ `test_doc_sources_batch1b.py` | ✅ |
| 13 | GitHub（§4.1） | `github` | `github.py` | ✅ | ✅ `test_doc_sources_batch2a.py` | ✅ |
| 14 | Google Drive（§4.1） | `google_drive` | `google_drive.py`（refresh_token 换票） | ✅ | ✅ `test_doc_sources_batch2a.py` | ✅ |
| 15 | OneDrive / SharePoint（§4.1） | `onedrive` | `onedrive.py`（client_credentials 换票 + Graph） | ✅ | ✅ `test_doc_sources_batch2a.py` | ✅ |
| 16 | Web Crawler (Sitemap)（§4.1） | `web_crawler` | `web_crawler.py`（**取代并删除 `web.py`**） | ✅ | ✅ `test_doc_sources_batch2b.py` | ✅ |
| 17 | Slack（§4.1） | `slack` | `slack.py` | ✅ | ✅ `test_doc_sources_batch2b.py` | ✅ |
| 18 | Email (IMAP)（§4.1） | `imap` | `imap.py` | ✅ | ✅ `test_doc_sources_batch2b.py` | ✅ |
| 19 | （文档外，工程自有）企业微信文档 | `wecom` | `wecom.py` | ✅ | ✅ `test_doc_sources.py` | ✅ |

注册表完整性由 `tests/connectors/test_doc_sources.py::test_all_providers_registered`
断言为上述 19 个，与 `supported_source_types()` 运行时结果一致。

## 二、占位 / 桩代码清理

| 项 | 处置 |
|---|---|
| `doc_sources/web.py`（种子 URL + 同域链接下钻的简化实现） | **已删除**，能力由 `web_crawler.py` 完整取代（sitemap / sitemapindex 递归、包含排除规则、页数上限） |
| `tests/unit/test_external_kb_binding.py` 对 `WebDocSource` 的用例 | 已改写为 `web_crawler` 用例，并新增「`web` 不再是合法平台」的防回归断言 |
| `app/core/security.py` 文档字符串中的 `doc_sources.web` | 已改为 `doc_sources.web_crawler` |
| `wiki_knowledge.py` / `external_doc_map.py` 的平台清单注释 | 已同步为 19 个 |
| `docs/guides/extract-setup.md` 指向 `doc_sources/web.py` | 已同步 |
| `alembic/versions/2026_10_18_0002_add_external_type.py` 说明文案 | 已同步（仅注释，revision 与 down_revision 未变） |

## 三、`web` → `web_crawler` 存量数据迁移

`external_type` 由 `web` 变为 `web_crawler`，不写兼容别名（避免保留桩代码）。升级时执行：

```sql
UPDATE wiki_knowledge       SET external_type  = 'web_crawler' WHERE external_type  = 'web';
UPDATE kb_external_doc_map  SET source_type    = 'web_crawler' WHERE source_type    = 'web';
UPDATE connector_instance   SET connector_type = 'web_crawler' WHERE connector_type = 'web';
```

未迁移的存量外部知识库会在创建/编辑时因 `validate_external_type` 报「不合法」，属预期行为。

## 四、与文档清单的两处有意差异（已写入实现注释）

1. **GitLab / GitHub 的扩展名白名单**不含图片与音频：WeKnora 把文件交给 docreader 处理，
   而本工程要求连接器直接输出 Markdown，图片 / 音频无法转成正文，故不列入白名单。
2. **Confluence 的「删除保护阈值」未实现**：该阈值服务于 WeKnora 的定时全量同步；
   本工程导入是手动幂等的（`kb_external_doc_map` 只做新建 / 覆盖 / 跳过，从不删除本地
   文档），阈值不适用；页面版本号仍回填为 `updated_at`。

## 五、共用基础层（本次新增）

| 文件 | 职责 |
|---|---|
| `doc_sources/_host.py` | 私有化地址的唯一 SSRF 放行通道：命中 `settings.SSRF_WHITELIST` 放行，否则强制 `is_safe_url`；SaaS 默认常量（如 `https://api.github.com`）直接可信 |
| `doc_sources/html.py` | HTML → Markdown（`markdownify` + 降级），供 web_crawler / rss / imap / confluence 复用 |
| `doc_sources/binary.py` | 字节流 → Markdown（惰性复用 `wiki/doc_converter.convert_document`）+ 文档扩展名白名单 |
| `doc_sources/feishu_core.py` | 飞书系共享核心：区域常量表 + 令牌换取 + wiki / drive 两套 ops |
| `config/_app.py::SSRF_WHITELIST` | 新增配置项（逗号分隔域名 / IP） |

## 六、验证命令

```powershell
cd d:\projects\MinWorkBuddy\backend
.\.venv\Scripts\python.exe -m pytest tests/connectors/test_doc_sources.py `
  tests/connectors/test_doc_sources_shared.py tests/connectors/test_doc_sources_feishu.py `
  tests/connectors/test_doc_sources_batch1.py tests/connectors/test_doc_sources_batch1b.py `
  tests/connectors/test_doc_sources_batch2a.py tests/connectors/test_doc_sources_batch2b.py `
  tests/connectors/test_doc_sources_batch3.py tests/unit/test_external_kb_binding.py -q
```
