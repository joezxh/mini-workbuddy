"""GitLab 仓库文档源（``source_type=gitlab``）。

认证：``PRIVATE-TOKEN`` 请求头（Personal / Project / Group Access Token，需
``read_repository``；增量比对用到的 compare 接口可由 ``read_api`` 覆盖）。
枚举：``GET /api/v4/projects`` → ``GET /api/v4/projects/{id}/repository/tree``（递归）。
正文：``GET /api/v4/projects/{id}/repository/files/{path}/raw``。

地址：GitLab 常见自建部署，``base_url`` 由用户填写 → 经 ``_host.resolve_host`` 校验
（内网地址需先加入 ``SSRF_WHITELIST``）；留空回退官方云 ``https://gitlab.com``。

**与 WeKnora 清单的一处差异**：WeKnora 的扩展名白名单含图片与音频，但它的连接器直接
把文件交给 docreader；本工程要求连接器输出 Markdown，图片 / 音频无法转成正文，故
白名单只保留「可转 Markdown」的文本与 Office/PDF 类型，并在日志中说明跳过原因。

**空文件特判**：文件被 commit 清空后仍存在于 tree 中，但正文为空；若直接跳过，旧正文
会滞留。此处按 WeKnora 的做法把「文件路径」本身作为正文发出，覆盖旧内容。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from app.connectors.doc_sources._host import resolve_host
from app.connectors.doc_sources.base import (
    BaseDocSource,
    CredField,
    DocConnResult,
    DocSourceError,
    ExternalDocRef,
    FetchDocResult,
    ProviderMeta,
    register_doc_source,
)
from app.connectors.doc_sources.binary import (
    DOC_EXTS,
    bytes_to_markdown,
    bytes_to_text,
    is_doc_file,
    is_supported,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST = "https://gitlab.com"
API_PREFIX = "/api/v4"
VERSION_PATH = "/version"
PROJECTS_PATH = "/projects"
PROJECT_PATH = "/projects/{project_id}"
TREE_PATH = "/projects/{project_id}/repository/tree"
RAW_PATH = "/projects/{project_id}/repository/files/{file_path}/raw"

# 单文件分页 / 目录列举上限，避免超大仓库拖垮一次导入
MAX_TREE_PAGES = 20
PAGE_SIZE = 100

# 复用 binary 的文档白名单（图片 / 音频无法转为 Markdown，不在其内）
SUPPORTED_EXTS = DOC_EXTS


def is_supported_file(path: str) -> bool:
    """文档文件白名单。"""
    return is_doc_file(path)


def _split_project_ref(doc_id: str) -> Tuple[str, str]:
    """项目节点 doc_id 形如 ``proj:<id>:<ref>``。"""
    parts = (doc_id or "").split(":", 2)
    if len(parts) < 2 or parts[0] != "proj":
        raise DocSourceError(f"无法解析的项目标识：{doc_id}")
    return parts[1], (parts[2] if len(parts) > 2 else "")


def parse_projects(raw: str) -> List[Dict[str, Any]]:
    """解析同步范围配置。

    支持两种写法（与文档 ``settings.projects[]`` 等价）：
    - JSON 数组：``[{"project_id":"123","ref":"main","paths":["docs/"]}]``
    - 每行一条：``123:main:docs/,README.md``（ref 与 paths 均可省略）
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise DocSourceError(f"项目范围 JSON 解析失败：{exc}") from exc
        out: List[Dict[str, Any]] = []
        for item in data or []:
            pid = str((item or {}).get("project_id") or "").strip()
            if not pid:
                continue
            paths = (item or {}).get("paths") or []
            out.append({
                "project_id": pid,
                "ref": str((item or {}).get("ref") or "").strip(),
                "paths": [str(p).strip() for p in paths if str(p).strip()],
            })
        return out
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        seg = [s.strip() for s in line.split(":", 2)]
        pid = seg[0]
        if not pid:
            continue
        ref = seg[1] if len(seg) > 1 else ""
        paths = [p for p in (seg[2].split(",") if len(seg) > 2 else []) if p]
        out.append({"project_id": pid, "ref": ref, "paths": paths})
    return out


def _within(paths: List[str], file_path: str) -> bool:
    """路径前缀过滤：paths 为空表示整仓库。"""
    if not paths:
        return True
    return any(
        file_path == p.rstrip("/") or file_path.startswith(p.rstrip("/") + "/")
        for p in paths
    )


class GitLabDocSource(BaseDocSource):
    source_type = "gitlab"
    token_in = "none"   # 走 PRIVATE-TOKEN 自定义头（见 _auth_headers）
    # GitLab 只用 HTTP 状态码 + body.message 表达错误，无数值业务码
    error_code_field = None
    timeout = 30.0

    # ── 凭据 ──────────────────────────────────────────────────
    @property
    def _host(self) -> str:
        return resolve_host(self.credentials.get("base_url") or "", default=DEFAULT_HOST)

    def _auth_headers(self) -> Dict[str, str]:
        token = (self.credentials.get("access_token") or "").strip()
        if not token:
            raise DocSourceError("缺少 GitLab Access Token")
        return {"PRIVATE-TOKEN": token}

    def _selection(self) -> List[Dict[str, Any]]:
        return parse_projects(self.credentials.get("projects") or "")

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            data = await self._request_json(
                "GET", f"{self._host}{API_PREFIX}{VERSION_PATH}",
                headers=self._auth_headers(),
            )
            version = (data or {}).get("version") or "未知版本"
            selection = self._selection()
            if selection:
                # 配置了同步范围：逐个探活，尽早暴露 project_id 写错 / 无权限
                for item in selection[:5]:
                    await self._request_json(
                        "GET",
                        f"{self._host}{API_PREFIX}{PROJECT_PATH}".format(
                            project_id=quote(item["project_id"], safe="")
                        ),
                        headers=self._auth_headers(),
                    )
                return DocConnResult(
                    ok=True,
                    message="连通成功：凭据有效，指定项目均可访问",
                    identity=f"GitLab {version} · {len(selection)} 个项目",
                )
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效",
                identity=f"GitLab {version}",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                selection = self._selection()
                if selection:
                    return await self._list_selected_projects(selection)
                return await self._list_projects()
            project_id, ref = _split_project_ref(parent_id)
            return await self._list_tree(project_id, ref)
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            parts = (doc_id or "").split(":", 3)
            if len(parts) != 4 or parts[0] != "file":
                raise DocSourceError(f"无法解析的文件标识：{doc_id}")
            project_id, ref, path = parts[1], parts[2], parts[3]
            resp = await self._request(
                "GET",
                f"{self._host}{API_PREFIX}{RAW_PATH}".format(
                    project_id=quote(project_id, safe=""),
                    file_path=quote(path, safe=""),
                ),
                headers=self._auth_headers(),
                params={"ref": ref} if ref else None,
            )
            if resp.status_code >= 400:
                raise DocSourceError(self._http_error_message(resp))
            content = resp.content or b""
            name = path.rsplit("/", 1)[-1]
            if not content.strip():
                # 空文件：把路径本身作为正文发出，以覆盖上一次导入的旧内容
                logger.info("gitlab 空文件已按路径占位导入 path=%s", path)
                return FetchDocResult(
                    title=name,
                    markdown=f"# {name}\n\n（文件 {path} 当前为空）\n",
                    updated_at=None,
                )
            if is_supported(name):
                return FetchDocResult(
                    title=name,
                    markdown=bytes_to_markdown(name, content),
                    updated_at=None,
                )
            text = bytes_to_text(content).strip()
            if not text:
                logger.info("gitlab 无正文文件已按路径占位导入 path=%s", path)
                text = f"# {name}\n\n（文件 {path} 无可提取文本）\n"
            return FetchDocResult(title=name, markdown=text, updated_at=None)
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    async def _list_projects(self) -> List[ExternalDocRef]:
        """未配置范围时列出令牌可见项目（membership=true，避免全实例扫描）。"""
        refs: List[ExternalDocRef] = []
        for page in range(1, 6):  # 最多 500 个项目
            data = await self._request_json(
                "GET", f"{self._host}{API_PREFIX}{PROJECTS_PATH}",
                headers=self._auth_headers(),
                params={"membership": "true", "per_page": PAGE_SIZE, "page": page},
            )
            items = data or []
            if not items:
                break
            for p in items:
                pid = str(p.get("id") or "")
                if not pid:
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=f"proj:{pid}:",
                        title=p.get("name_with_namespace") or p.get("name") or pid,
                        node_type="folder",
                        url=p.get("web_url"),
                    )
                )
            if len(items) < PAGE_SIZE:
                break
        return refs

    async def _list_selected_projects(
        self, selection: List[Dict[str, Any]]
    ) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        for item in selection:
            try:
                data = await self._request_json(
                    "GET",
                    f"{self._host}{API_PREFIX}{PROJECT_PATH}".format(
                        project_id=quote(item["project_id"], safe="")
                    ),
                    headers=self._auth_headers(),
                )
            except DocSourceError:
                # 单个项目不可见不阻断其它项目（失败隔离）
                logger.warning("gitlab 项目不可见 project_id=%s", item["project_id"])
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=f"proj:{item['project_id']}:{item['ref']}",
                    title=(data or {}).get("name_with_namespace") or item["project_id"],
                    node_type="folder",
                    url=(data or {}).get("web_url"),
                )
            )
        return refs

    async def _list_tree(self, project_id: str, ref: str) -> List[ExternalDocRef]:
        """递归列文件树，按白名单与路径范围过滤，返回 doc 节点。"""
        paths = self._paths_of(project_id, ref)
        url = f"{self._host}{API_PREFIX}{TREE_PATH}".format(
            project_id=quote(project_id, safe="")
        )
        refs: List[ExternalDocRef] = []
        for page in range(1, MAX_TREE_PAGES + 1):
            params: Dict[str, Any] = {
                "recursive": "true", "per_page": PAGE_SIZE, "page": page,
            }
            if ref:
                params["ref"] = ref
            data = await self._request_json(
                "GET", url, headers=self._auth_headers(), params=params
            )
            entries = data or []
            for entry in entries:
                if entry.get("type") != "blob":
                    continue
                path = entry.get("path") or ""
                if not path or not is_supported_file(path):
                    continue
                if not _within(paths, path):
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=f"file:{project_id}:{ref}:{path}",
                        title=path.rsplit("/", 1)[-1],
                        node_type="doc",
                        parent_id=f"proj:{project_id}:{ref}",
                    )
                )
            if len(entries) < PAGE_SIZE:
                break
        return refs

    def _paths_of(self, project_id: str, ref: str) -> List[str]:
        for item in self._selection():
            if item["project_id"] == project_id and (item["ref"] or "") == (ref or ""):
                return item["paths"]
        return []


register_doc_source(
    "gitlab",
    GitLabDocSource,
    ProviderMeta(
        source_type="gitlab",
        name="GitLab",
        desc="仓库内的文档文件（Markdown / Office / PDF）",
        host=DEFAULT_HOST,
        credential_fields=(
            CredField("base_url", "GitLab 地址", placeholder="https://gitlab.example.com",
                      hint="留空使用 gitlab.com；不要带 /api/v4。内网私有化部署需先把域名"
                           "加入 SSRF_WHITELIST"),
            CredField("access_token", "Access Token", required=True, secret=True,
                      placeholder="glpat-xxxxxxxx",
                      hint="Personal / Project / Group Token，需 read_repository 权限"),
            CredField("projects", "同步范围（可选）", multiline=True,
                      placeholder='123:main:docs/,README.md',
                      hint="每行一条 project_id:ref:路径（逗号分隔，留空=整仓库）；"
                           "也可填 JSON 数组 [{\"project_id\":\"123\",\"ref\":\"main\","
                           "\"paths\":[\"docs/\"]}]。留空则列出令牌可见的全部项目"),
        ),
    ),
)
