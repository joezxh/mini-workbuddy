"""GitHub 仓库文档源（``source_type=github``）。

认证：Personal Access Token（fine-grained 或 classic），请求头
``Authorization: Bearer <token>`` + ``Accept: application/vnd.github+json`` +
``X-GitHub-Api-Version: 2022-11-28``（版本固定，避免平台默认版本漂移）。
枚举：``GET /user/repos``（或 ``/users/{owner}/repos``、``/orgs/{owner}/repos``）→
``GET /repos/{owner}/{repo}/git/trees/{ref}?recursive=1``。
正文：``GET /repos/{owner}/{repo}/contents/{path}?ref=``（``Accept: ...raw`` 取原始字节）。

地址默认 ``https://api.github.com``；GitHub Enterprise 可填 ``base_url`` → 经
``_host.resolve_host`` 校验（内网需先加入 ``SSRF_WHITELIST``）。

**空文件特判**：文件被 commit 清空后仍存在于 tree 中但正文为空；若直接跳过，旧正文会
滞留。此处把「文件路径」本身作为正文发出，覆盖上一次导入的旧内容。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

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
    bytes_to_markdown,
    bytes_to_text,
    is_doc_file,
    is_supported,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_PATH = "/user"
USER_REPOS_PATH = "/user/repos"
OWNER_REPOS_PATH = "/users/{owner}/repos"
ORG_REPOS_PATH = "/orgs/{owner}/repos"
TREE_PATH = "/repos/{full_name}/git/trees/{ref}"
CONTENTS_PATH = "/repos/{full_name}/contents/{path}"

# 单次列举上限
REPO_PAGE_LIMIT = 100
MAX_REPO_PAGES = 5


def _encode_repo(full_name: str, ref: str) -> str:
    return f"repo:{full_name}:{ref}"


def _encode_file(full_name: str, ref: str, path: str) -> str:
    return f"file:{full_name}:{ref}:{path}"


def _decode(doc_id: str) -> Tuple[str, ...]:
    parts = (doc_id or "").split(":")
    if len(parts) == 3 and parts[0] == "repo":
        return "repo", parts[1], parts[2]
    if len(parts) == 4 and parts[0] == "file":
        return "file", parts[1], parts[2], parts[3]
    raise DocSourceError(f"无法解析的 GitHub 标识：{doc_id}")


class GitHubDocSource(BaseDocSource):
    source_type = "github"
    token_in = "none"   # Bearer + 固定 API 版本头，见 _auth_headers
    # GitHub 只用 HTTP 状态码 + body.message 表达错误
    error_code_field = None
    timeout = 30.0

    # ── 凭据 ──────────────────────────────────────────────────
    @property
    def _host(self) -> str:
        return resolve_host(self.credentials.get("base_url") or "", default=DEFAULT_HOST)

    def _auth_headers(self, raw: bool = False) -> Dict[str, str]:
        token = (self.credentials.get("token") or "").strip()
        if not token:
            raise DocSourceError("缺少 GitHub Personal Access Token")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
        }
        # 取文件内容时用 raw 媒体类型，直接拿到字节流而非 base64 JSON
        headers["Accept"] = "application/vnd.github.raw" if raw else "application/vnd.github+json"
        return headers

    def _owner(self) -> str:
        return (self.credentials.get("owner") or "").strip()

    def _repo(self) -> str:
        return (self.credentials.get("repo") or "").strip()

    def _ref(self) -> str:
        return (self.credentials.get("ref") or "").strip()

    def _paths(self) -> List[str]:
        raw = self.credentials.get("paths") or ""
        return [p.strip() for p in raw.replace(",", "\n").splitlines() if p.strip()]

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            data = await self._request_json(
                "GET", f"{self._host}{USER_PATH}", headers=self._auth_headers()
            )
            login = (data or {}).get("login") or "未知账号"
            identity = f"GitHub 账号 {login}"
            if self._repo():
                # 指定了仓库：顺带探活，尽早暴露仓库名写错 / 无权限
                full_name = self._full_name()
                await self._request_json(
                    "GET", f"{self._host}/repos/{full_name}", headers=self._auth_headers()
                )
                identity = f"{login} · 仓库 {full_name}"
            return DocConnResult(ok=True, message="连通成功：凭据有效", identity=identity)
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                if self._repo():
                    return [
                        ExternalDocRef(
                            doc_id=_encode_repo(self._full_name(), self._ref()),
                            title=self._full_name(),
                            node_type="folder",
                        )
                    ]
                return await self._list_repos()
            parts = _decode(parent_id)
            if parts[0] != "repo":
                return []
            return await self._list_tree(parts[1], parts[2])
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            parts = _decode(doc_id)
            if parts[0] != "file":
                raise DocSourceError(f"{doc_id} 不是可导入的文件")
            full_name, ref, path = parts[1], parts[2], parts[3]
            url = f"{self._host}{CONTENTS_PATH}".format(
                full_name=full_name, path=path.strip("/"),
            )
            resp = await self._request(
                "GET", url, headers=self._auth_headers(raw=True),
                params={"ref": ref} if ref else None,
            )
            if resp.status_code >= 400:
                raise DocSourceError(self._http_error_message(resp))
            name = path.rsplit("/", 1)[-1]
            content = resp.content or b""
            if not content.strip():
                # 空文件：以路径占位，覆盖上一次导入的旧正文
                logger.info("github 空文件已按路径占位导入 path=%s", path)
                return FetchDocResult(
                    title=name,
                    markdown=f"# {name}\n\n（文件 {path} 当前为空）\n",
                    updated_at=None,
                )
            if is_supported(name):
                return FetchDocResult(
                    title=name, markdown=bytes_to_markdown(name, content), updated_at=None,
                )
            text = bytes_to_text(content).strip()
            if not text:
                logger.info("github 无正文文件已按路径占位导入 path=%s", path)
                text = f"# {name}\n\n（文件 {path} 无可提取文本）\n"
            return FetchDocResult(title=name, markdown=text, updated_at=None)
        finally:
            await self.aclose()

    # ── 私有辅助 ──────────────────────────────────────────────
    def _full_name(self) -> str:
        repo = self._repo()
        owner = self._owner()
        if "/" in repo:
            return repo
        if not repo:
            raise DocSourceError("缺少仓库名（repo）")
        if not owner:
            raise DocSourceError("仅填仓库名时必须同时填写 owner")
        return f"{owner}/{repo}"

    async def _list_repos(self) -> List[ExternalDocRef]:
        owner = self._owner()
        if owner:
            # 可能是组织也可能是个人：先按组织试，失败再按个人
            urls = [OWNER_REPOS_PATH.format(owner=owner), ORG_REPOS_PATH.format(owner=owner)]
        else:
            urls = [USER_REPOS_PATH]
        refs: List[ExternalDocRef] = []
        for url in urls:
            try:
                data = await self._request_json(
                    "GET", f"{self._host}{url}",
                    headers=self._auth_headers(),
                    params={"per_page": REPO_PAGE_LIMIT, "sort": "updated"},
                )
            except DocSourceError:
                continue
            for r in data or []:
                full_name = r.get("full_name") or ""
                if not full_name:
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=_encode_repo(full_name, self._ref()),
                        title=full_name,
                        node_type="folder",
                        updated_at=r.get("updated_at") or r.get("pushed_at"),
                        url=r.get("html_url"),
                    )
                )
            if refs:
                break
        return refs

    async def _list_tree(self, full_name: str, ref: str) -> List[ExternalDocRef]:
        tree_ref = ref or "HEAD"
        data = await self._request_json(
            "GET", f"{self._host}{TREE_PATH}".format(full_name=full_name, ref=tree_ref),
            headers=self._auth_headers(), params={"recursive": "1"},
        )
        if data.get("truncated"):
            logger.warning("github 文件树被截断 repo=%s，仅返回前 10 万条目", full_name)
        paths = self._paths()
        refs: List[ExternalDocRef] = []
        for entry in (data or {}).get("tree") or []:
            if entry.get("type") != "blob":
                continue
            path = entry.get("path") or ""
            if not path or not is_doc_file(path):
                continue
            if paths and not any(
                path == p.strip("/") or path.startswith(p.strip("/") + "/") for p in paths
            ):
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=_encode_file(full_name, ref, path),
                    title=path.rsplit("/", 1)[-1],
                    node_type="doc",
                    parent_id=_encode_repo(full_name, ref),
                )
            )
        return refs


register_doc_source(
    "github",
    GitHubDocSource,
    ProviderMeta(
        source_type="github",
        name="GitHub",
        desc="仓库内的文档文件（Markdown / Office / PDF）",
        host=DEFAULT_HOST,
        credential_fields=(
            CredField("token", "Personal Access Token", required=True, secret=True,
                      placeholder="ghp_xxxxxxxxxxxx",
                      hint="需具备目标仓库的读取权限（fine-grained：Contents=Read）"),
            CredField("owner", "组织 / 用户", placeholder="octocat",
                      hint="填写后只列该组织或用户的仓库；留空则列出当前令牌可见仓库"),
            CredField("repo", "仓库名", placeholder="handbook",
                      hint="可填 owner/repo 全名；填写后直接定位到该仓库"),
            CredField("ref", "分支 / 标签", placeholder="留空用默认分支",
                      hint="如 main、v1.0.0；留空时文件树用 HEAD"),
            CredField("paths", "路径范围（可选）", multiline=True, placeholder="docs/",
                      hint="每行一个路径前缀（也可用逗号分隔），留空=整个仓库"),
            CredField("base_url", "API 地址", placeholder="https://api.github.com",
                      hint="GitHub Enterprise 可填企业实例地址；内网需先加入 SSRF_WHITELIST"),
        ),
    ),
)
