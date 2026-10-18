"""外部文档源抽象（与既有 records 型 connectors 并列）。

既有 ``app.connectors.base.BaseConnector`` 面向「记录流」（``pull() -> List[dict]``
+ 字段映射 + 影子表 ``meta_connector_ingest``），无法表达「目录树 / 文档正文」。
本模块另建一套同构抽象，专门负责：

    test_connection()  → 连通性探测
    list_nodes()       → 列举目录与文档（懒加载，只取当前层级）
    fetch_doc()        → 拉取单篇正文并转成 Markdown

安全约束：具体平台的域名必须写成模块级常量（见各实现文件的 ``HOST``），
**不接受调用方传入任意 base_url**，从根上消除 SSRF 风险。

令牌：需要 OAuth2/access_token 的平台重载 ``_fetch_token()``，基类负责
惰性获取与 TTL 缓存（一次导入会话内不会重复取令牌）。
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

# 默认请求超时（秒）；大文档分页拉取时子类可适当放大
DEFAULT_TIMEOUT = 20.0
# 令牌缓存 TTL（秒），到期前 60s 提前刷新，避免临界失效
TOKEN_TTL = 300
TOKEN_REFRESH_MARGIN = 60


class DocSourceError(Exception):
    """文档源调用失败；message 直接回显给前端（已做可读性映射）。"""


@dataclass(frozen=True)
class ExternalDocRef:
    """外部文档/目录引用。

    ``doc_id`` 必须是平台内稳定唯一的标识——它是「覆盖 or 新建」判定的外部键，
    写入 ``kb_external_doc_map.external_doc_id``。
    """

    doc_id: str
    title: str
    node_type: str                 # space | folder | doc
    parent_id: Optional[str] = None
    updated_at: Optional[str] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class DocConnResult:
    """连通性测试结果。message 为可直接展示的中文说明。"""

    ok: bool
    message: str = ""
    identity: str = ""             # 探测到的账号/空间等标识，便于用户确认连对了


@dataclass(frozen=True)
class FetchDocResult:
    """单篇文档正文。content_hash 由导入服务计算后写入映射表。"""

    title: str
    markdown: str
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class CredField:
    """凭据字段 schema：驱动前端动态表单，避免前后端各硬编码一份。"""

    name: str
    label: str
    secret: bool = False
    required: bool = False
    placeholder: str = ""
    hint: str = ""
    # 多行文本（前端据此渲染 textarea）：web 连接器的种子 URL 列表等场景
    multiline: bool = False


@dataclass(frozen=True)
class ProviderMeta:
    """平台元数据。"""

    source_type: str
    name: str
    desc: str
    host: str
    credential_fields: tuple = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "name": self.name,
            "desc": self.desc,
            "host": self.host,
            "credential_fields": [
                {
                    "name": f.name,
                    "label": f.label,
                    "secret": f.secret,
                    "required": f.required,
                    "placeholder": f.placeholder,
                    "hint": f.hint,
                    "multiline": f.multiline,
                }
                for f in self.credential_fields
            ],
        }


class BaseDocSource(ABC):
    """外部文档源基类。

    子类只需声明 ``source_type``、实现三个抽象方法，并在需要令牌时重载
    ``_fetch_token()``；HTTP 与令牌缓存由基类统一提供。
    """

    source_type: str = ""
    # 令牌注入方式：header(Authorization: Bearer) | header_raw(自定义头名，值即令牌，
    # 无 Bearer 前缀，如钉钉 x-acs-dingtalk-access-token) | query(查询参数) | none
    token_in: str = "none"
    token_query_name: str = "access_token"
    # header_raw 模式使用的请求头名（子类按需覆盖）
    token_header_name: str = "Authorization"
    timeout: float = DEFAULT_TIMEOUT

    def __init__(self, credentials: Dict[str, Any]) -> None:
        self.credentials = credentials or {}
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ── 子类必须实现 ──────────────────────────────────────────────
    @abstractmethod
    async def test_connection(self) -> DocConnResult:
        """连通性探测。不得抛出：失败时返回 ok=False + 可读 message。"""

    @abstractmethod
    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        """列举下一层节点（目录可下钻、文档可勾选）。"""

    @abstractmethod
    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        """拉取单篇文档正文并转成 Markdown。"""

    # ── 令牌（可选） ─────────────────────────────────────────────
    async def _fetch_token(self) -> Optional[str]:
        """获取访问令牌；不需要令牌的平台（语雀/Notion）保持默认返回 None。"""
        return None

    async def _access_token(self) -> Optional[str]:
        """惰性获取 + TTL 缓存，避免 test/list/fetch 各取一次令牌。"""
        if self.token_in == "none":
            return None
        now = time.time()
        if self._token and now < self._token_expiry - TOKEN_REFRESH_MARGIN:
            return self._token
        self._token = await self._fetch_token()
        self._token_expiry = now + TOKEN_TTL
        return self._token

    # ── HTTP ─────────────────────────────────────────────────────
    def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)
        return self._client

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        with_token: bool = True,
    ) -> httpx.Response:
        """统一 HTTP 出口：注入令牌、超时、把传输错误转成 DocSourceError。"""
        hdrs = dict(headers or {})
        q = dict(params or {})
        if with_token and self.token_in != "none":
            token = await self._access_token()
            if token:
                if self.token_in == "header":
                    hdrs["Authorization"] = f"Bearer {token}"
                elif self.token_in == "header_raw":
                    # 钉钉等新版开放平台：令牌直接作为指定头的值（无 Bearer 前缀）
                    hdrs[self.token_header_name] = token
                else:
                    q[self.token_query_name] = token
        try:
            resp = await self._client_instance().request(
                method, url, headers=hdrs or None, params=q or None, json=json_body,
            )
        except httpx.HTTPError as exc:
            raise DocSourceError(f"无法连接外部平台（{type(exc).__name__}），请检查网络或凭据") from exc
        return resp

    async def _request_json(
        self, method: str, url: str, **kwargs: Any
    ) -> Any:
        """请求并解析 JSON；非 2xx / 非法 JSON 统一转成 DocSourceError。"""
        resp = await self._request(method, url, **kwargs)
        if resp.status_code >= 400:
            raise DocSourceError(self._http_error_message(resp))
        try:
            return resp.json()
        except ValueError as exc:
            raise DocSourceError("外部平台返回了非 JSON 响应") from exc

    @staticmethod
    def _http_error_message(resp: httpx.Response) -> str:
        """把平台原始报错映射为可读中文，尽量带上平台自己的 msg。"""
        detail = ""
        try:
            body = resp.json()
            if isinstance(body, dict):
                detail = (
                    body.get("msg") or body.get("message") or body.get("error") or ""
                )
        except ValueError:
            detail = (resp.text or "")[:200]
        code = resp.status_code
        if code in (401, 403):
            base = "凭据无效或权限不足（401/403）"
        elif code == 404:
            base = "资源不存在（404）"
        elif code == 429:
            base = "被平台限流（429），请稍后重试"
        elif code >= 500:
            base = f"外部平台服务异常（{code}）"
        else:
            base = f"请求失败（HTTP {code}）"
        return f"{base}：{detail}" if detail else base

    async def aclose(self) -> None:
        """释放 HTTP 客户端；导入服务在 finally 中调用。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# ── 注册表（与 app.connectors.registry 同构） ─────────────────────
_DOC_SOURCES: Dict[str, type] = {}
_PROVIDER_META: Dict[str, ProviderMeta] = {}


def register_doc_source(source_type: str, cls: type, meta: ProviderMeta) -> None:
    """注册一个文档源实现及其平台元数据。"""
    _DOC_SOURCES[source_type] = cls
    _PROVIDER_META[source_type] = meta


def get_doc_source(source_type: str, credentials: Dict[str, Any]) -> BaseDocSource:
    """按类型构造文档源；未注册类型直接报错（不做静默降级）。"""
    cls = _DOC_SOURCES.get(source_type)
    if cls is None:
        raise DocSourceError(f"不支持的外部平台类型：{source_type}")
    return cls(credentials)


def list_providers() -> List[Dict[str, Any]]:
    """返回全部平台元数据（含凭据字段 schema），驱动前端动态表单。"""
    return [meta.to_dict() for meta in _PROVIDER_META.values()]


def get_provider_meta(source_type: str) -> Optional[ProviderMeta]:
    return _PROVIDER_META.get(source_type)


def supported_source_types() -> List[str]:
    return list(_DOC_SOURCES.keys())
