"""企业微信文档源。

认证：``GET /cgi-bin/gettoken?corpid&corpsecret`` 取 access_token，以查询参数
注入（沿用既有 ``app/connectors/types/wecom.py`` 的约定）。
枚举：WeDoc 空间 → 文档列表；正文：按 docid 取内容。

⚠️ 注意：企业微信 WeDoc 的开放接口覆盖面有限且随版本调整，
本文件把路径抽成模块级常量（见下方 *_PATH）；若线上报 404/参数错误，
按最新官方文档校正常量即可，不必改动调用逻辑。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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

HOST = "https://qyapi.weixin.qq.com"
TOKEN_PATH = "/cgi-bin/gettoken"
DOC_LIST_PATH = "/cgi-bin/wedoc/spi_list"
DOC_INFO_PATH = "/cgi-bin/wedoc/get_doc_base_info"
DOC_CONTENT_PATH = "/cgi-bin/wedoc/document"


class WecomDocSource(BaseDocSource):
    source_type = "wecom"
    token_in = "query"
    token_query_name = "access_token"

    async def _fetch_token(self) -> Optional[str]:
        corp_id = self.credentials.get("corp_id") or ""
        corp_secret = self.credentials.get("corp_secret") or ""
        if not (corp_id and corp_secret):
            raise DocSourceError("缺少 CorpID 或 CorpSecret")
        data = await self._request_json(
            "GET", f"{HOST}{TOKEN_PATH}",
            params={"corpid": corp_id, "corpsecret": corp_secret},
            with_token=False,
        )
        token = (data or {}).get("access_token")
        if not token:
            raise DocSourceError(f"获取 access_token 失败：{(data or {}).get('errmsg') or '未知错误'}")
        return token

    async def test_connection(self) -> DocConnResult:
        try:
            await self._access_token()
            return DocConnResult(ok=True, message="连通成功：凭据有效",
                                 identity="CorpSecret 有效")
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            # WeDoc 暂未提供稳定的目录树接口：空间下直接列文档
            if parent_id:
                return []
            data = await self._request_json(
                "POST", f"{HOST}{DOC_LIST_PATH}", json_body={"limit": 100}
            )
            payload = (data or {}).get("data") or data or {}
            items = (
                payload.get("doc_list")
                or payload.get("doclist")
                or payload.get("list")
                or []
            )
            refs: List[ExternalDocRef] = []
            for d in items:
                doc_id = d.get("docid") or d.get("doc_id") or d.get("id")
                if not doc_id:
                    continue
                refs.append(
                    ExternalDocRef(
                        doc_id=str(doc_id),
                        title=d.get("doc_name") or d.get("name") or "未命名文档",
                        node_type="doc",
                        updated_at=d.get("update_time") or d.get("updateTime"),
                    )
                )
            return refs
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            data = await self._request_json(
                "POST", f"{HOST}{DOC_CONTENT_PATH}",
                json_body={"docid": doc_id},
            )
            payload = (data or {}).get("data") or data or {}
            content = (
                payload.get("markdown")
                or payload.get("content")
                or payload.get("text")
                or ""
            )
            if not content:
                raise DocSourceError("该文档未返回可导入的文本内容（可能为非文本类型）")
            return FetchDocResult(
                title=payload.get("doc_name") or payload.get("name") or "企业微信文档",
                markdown=content if content.endswith("\n") else content + "\n",
                updated_at=payload.get("update_time") or payload.get("updateTime"),
            )
        finally:
            await self.aclose()


register_doc_source(
    "wecom",
    WecomDocSource,
    ProviderMeta(
        source_type="wecom",
        name="企业微信文档",
        desc="WeDoc 空间",
        host=HOST,
        credential_fields=(
            CredField("corp_id", "CorpID", required=True, placeholder="wwxxxxxxxxxxxx"),
            CredField("corp_secret", "CorpSecret", required=True, secret=True,
                      placeholder="应用 Secret"),
            CredField("space_id", "文档空间", placeholder="空间名（可选）"),
        ),
    ),
)
