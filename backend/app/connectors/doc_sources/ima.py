"""腾讯 IMA 知识库文档源（``source_type=ima``）。

认证：**静态请求头** ``ima-openapi-clientid`` / ``ima-openapi-apikey``（无 OAuth 流程）。
接口形态：全部为 ``POST``，路径 ``/openapi/wiki/v1``（知识库与媒体）与
``/openapi/note/v1``（笔记正文）两个命名空间；响应统一 ``{code, msg, data}``，
部分接口兼容旧拼写 ``{retcode, errmsg}``。

列举：``get_addable_knowledge_base_list`` → ``get_knowledge_list``（``next_cursor`` 分页）
→ ``get_media_info``（拿下载 URL 或 ``notebook_ext_info.notebook_id``）。
正文：笔记走 ``note/v1/get_doc_content``；普通媒体走下载 URL（HTML 转 Markdown，
Office/PDF 走 ``binary.bytes_to_markdown``）。

**已知限制（平台侧，代码无法规避）**：IMA 不提供 per-item ``updated_at``，同名文件原地
编辑（media_id 不变）无法感知，只有重新导入才会刷新内容。

跳过类型：``media_type==12``（AI 会话，无正文读取入口）与 ``16``（视频，只能在 IMA
桌面端添加）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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
from app.connectors.doc_sources.binary import bytes_to_markdown, is_supported
from app.connectors.doc_sources.html import html_to_markdown

logger = logging.getLogger(__name__)

DEFAULT_HOST = "https://ima.qq.com"
API_BASE_PATH = "/openapi/wiki/v1"
NOTE_BASE_PATH = "/openapi/note/v1"

# 单次列举分页上限，避免超大知识库无限翻页
MAX_LIST_PAGES = 50
# 无正文读取入口 / 平台限制的类型
SKIP_MEDIA_TYPES = (12, 16)

ACTION_KB_LIST = "get_addable_knowledge_base_list"
ACTION_MEDIA_LIST = "get_knowledge_list"
ACTION_MEDIA_INFO = "get_media_info"
ACTION_NOTE_CONTENT = "get_doc_content"


def _encode_media(media_id: str) -> str:
    return f"media:{media_id}"


def _decode_media(doc_id: str) -> str:
    parts = (doc_id or "").split(":", 1)
    if len(parts) != 2 or parts[0] != "media":
        raise DocSourceError(f"无法解析的 IMA 资源标识：{doc_id}")
    return parts[1]


class IMADocSource(BaseDocSource):
    source_type = "ima"
    token_in = "none"   # 静态自定义头，见 _auth_headers
    # 响应体业务码：code=0 为成功；部分接口用 retcode/errmsg，故错误字段一并列出
    error_code_field = "code"
    error_msg_fields = ("msg", "message", "errmsg", "error")
    timeout = 30.0

    # ── 凭据与地址 ────────────────────────────────────────────
    @property
    def _host(self) -> str:
        return resolve_host(self.credentials.get("base_url") or "", default=DEFAULT_HOST)

    def _auth_headers(self) -> Dict[str, str]:
        client_id = (self.credentials.get("client_id") or "").strip()
        api_key = (self.credentials.get("api_key") or "").strip()
        if not client_id:
            raise DocSourceError("缺少 IMA Client ID")
        if not api_key:
            raise DocSourceError("缺少 IMA API Key")
        return {"ima-openapi-clientid": client_id, "ima-openapi-apikey": api_key}

    def _kb_id(self) -> str:
        return (self.credentials.get("knowledge_base_id") or "").strip()

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            kbs = await self._list_knowledge_bases()
            if not kbs:
                return DocConnResult(
                    ok=False,
                    message="凭据有效，但未获取到任何可用知识库：请确认该凭据已被授权访问"
                            "目标知识库（https://ima.qq.com/agent-interface）",
                )
            return DocConnResult(
                ok=True,
                message="连通成功：凭据有效",
                identity=f"可访问知识库 {len(kbs)} 个",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                if self._kb_id():
                    # 凭据里指定了知识库：直接列它的内容，省掉一次选择
                    return await self._list_media(self._kb_id())
                return await self._list_knowledge_bases()
            return await self._list_media(parent_id)
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            media_id = _decode_media(doc_id)
            info = await self._media_info(media_id)
            title = info.get("title") or info.get("name") or "IMA 文档"
            notebook_id = ((info.get("notebook_ext_info") or {}).get("notebook_id")
                           or info.get("notebook_id") or "")
            if notebook_id:
                return await self._fetch_note(notebook_id, media_id, title)
            url = ((info.get("url_info") or {}).get("url")
                   or info.get("url") or "")
            if not url:
                raise DocSourceError(f"IMA 未返回下载链接（media_id={media_id}）")
            return await self._fetch_by_url(url, title)
        finally:
            await self.aclose()

    # ── 平台调用 ──────────────────────────────────────────────
    async def _call(self, action: str, payload: Dict[str, Any],
                    *, base_path: str = API_BASE_PATH) -> Dict[str, Any]:
        """统一 POST 调用；兼容 ``{code,msg,data}`` 与 ``{retcode,errmsg}`` 两种拼写。"""
        body = await self._request_json(
            "POST",
            f"{self._host}{base_path}/{action}",
            headers=self._auth_headers(),
            json_body=dict(payload or {}),
        )
        data = (body or {}).get("data")
        if isinstance(data, dict):
            return data
        return body or {}

    async def _list_knowledge_bases(self) -> List[ExternalDocRef]:
        data = await self._call(ACTION_KB_LIST, {})
        items = data.get("knowledge_base_list") or data.get("list") or []
        refs: List[ExternalDocRef] = []
        for kb in items or []:
            kb_id = str(kb.get("knowledge_base_id") or kb.get("id") or "")
            if not kb_id:
                continue
            refs.append(
                ExternalDocRef(
                    doc_id=kb_id,
                    title=kb.get("name") or kb.get("title") or kb_id,
                    node_type="folder",
                )
            )
        return refs

    async def _list_media(self, kb_id: str) -> List[ExternalDocRef]:
        refs: List[ExternalDocRef] = []
        cursor = ""
        for _ in range(MAX_LIST_PAGES):
            data = await self._call(ACTION_MEDIA_LIST, {
                "knowledge_base_id": kb_id,
                "next_cursor": cursor,
            })
            for m in data.get("media_list") or data.get("list") or []:
                media_id = str(m.get("media_id") or m.get("id") or "")
                if not media_id:
                    continue
                if self._is_skippable(m.get("media_type")):
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=_encode_media(media_id),
                        title=m.get("title") or m.get("name") or media_id,
                        node_type="doc",
                        parent_id=kb_id,
                        updated_at=m.get("update_time") or m.get("create_time"),
                    )
                )
            cursor = data.get("next_cursor") or ""
            if not cursor:
                break
        return refs

    async def _media_info(self, media_id: str) -> Dict[str, Any]:
        return await self._call(ACTION_MEDIA_INFO, {"media_id": media_id})

    async def _fetch_note(
        self, notebook_id: str, media_id: str, title: str
    ) -> FetchDocResult:
        data = await self._call(
            ACTION_NOTE_CONTENT,
            {"notebook_id": notebook_id, "media_id": media_id},
            base_path=NOTE_BASE_PATH,
        )
        content = data.get("content") or data.get("doc_content") or ""
        if not content:
            # 空笔记：以标题兜底，保证映射与正文都存在（对齐平台行为）
            content = f"# {title}"
        if "<" in content and ">" in content:
            content = html_to_markdown(content)
        return FetchDocResult(title=title, markdown=content, updated_at=None)

    async def _fetch_by_url(self, url: str, title: str) -> FetchDocResult:
        resp = await self._request("GET", url, with_token=False)
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        content_type = (resp.headers.get("Content-Type") or "").lower()
        body = resp.content or b""
        if is_supported(title):
            return FetchDocResult(
                title=title, markdown=bytes_to_markdown(title, body), updated_at=None,
            )
        if "html" in content_type:
            return FetchDocResult(
                title=title, markdown=html_to_markdown(resp.text or ""), updated_at=None,
            )
        text = body.decode("utf-8", errors="ignore").strip()
        if not text:
            raise DocSourceError(f"IMA 文档 {title} 未返回任何正文内容")
        return FetchDocResult(title=title, markdown=text, updated_at=None)

    @staticmethod
    def _is_skippable(media_type: Any) -> bool:
        try:
            return int(media_type) in SKIP_MEDIA_TYPES
        except (TypeError, ValueError):
            return False


register_doc_source(
    "ima",
    IMADocSource,
    ProviderMeta(
        source_type="ima",
        name="腾讯 IMA",
        desc="IMA 知识库（文档 / 笔记）",
        host=DEFAULT_HOST,
        credential_fields=(
            CredField("client_id", "Client ID", required=True,
                      placeholder="在 https://ima.qq.com/agent-interface 申请"),
            CredField("api_key", "API Key", required=True, secret=True,
                      placeholder="与 Client ID 配套的 API Key"),
            CredField("base_url", "API 地址", placeholder="https://ima.qq.com",
                      hint="私有化 / 测试端点可填，留空使用官方地址"),
            CredField("knowledge_base_id", "知识库 ID", placeholder="留空则先列出知识库",
                      hint="填写后直接列出该知识库内容，跳过知识库选择"),
        ),
    ),
)
