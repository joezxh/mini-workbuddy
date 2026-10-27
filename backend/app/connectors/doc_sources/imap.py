"""IMAP 邮箱文档源（``source_type=imap``）。

本模块是 ``doc_sources`` 中**唯一的非 HTTP 平台**：不复用基类的 ``_request`` /
``_request_json``，而是用标准库 ``imaplib`` + ``email`` 自建连接；所有阻塞调用经
``asyncio.to_thread`` 包装，避免卡住事件循环。``aclose()`` 同时关闭 IMAP 连接
（``close`` + ``logout``），``timeout`` 复用基类类属性以保持风格统一。

**主机由用户填写**（邮箱服务器必然是用户自己的），因此是全模块第二个「可变主机」
场景，必须经 ``_host.resolve_hostname`` 校验：命中 ``SSRF_WHITELIST`` 放行内网邮件
服务器，否则拒绝内网 / 环回 / 保留网段。

文档 ID：``{mailbox}:{uidvalidity}:{uid}`` —— 带上 UIDVALIDITY 是因为 IMAP 的 UID
只在「同一邮箱的同一 validity 周期」内唯一，缺少它会跨会话复用导致覆盖错文档。
"""
from __future__ import annotations

import asyncio
import email
import imaplib
import logging
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message
from typing import Any, Dict, List, Optional, Tuple

from app.connectors.doc_sources._host import resolve_hostname
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
from app.connectors.doc_sources.html import html_to_markdown

logger = logging.getLogger(__name__)

DEFAULT_PORT = 993
DEFAULT_MAILBOX = "INBOX"
DEFAULT_MAX_MESSAGES = 200
MAX_MESSAGES_LIMIT = 2000
# 单次 FETCH 的字节上限（8MB），避免超大邮件拖垮内存
MAX_FETCH_BYTES = 8 * 1024 * 1024

SEP = ":"


def _encode_mailbox(name: str) -> str:
    return f"mbox{SEP}{name}"


def _encode_message(mailbox: str, uid_validity: str, uid: str) -> str:
    return f"msg{SEP}{mailbox}{SEP}{uid_validity}{SEP}{uid}"


def _decode(doc_id: str) -> Tuple[str, ...]:
    parts = (doc_id or "").split(SEP)
    if len(parts) == 2 and parts[0] == "mbox":
        return "mbox", parts[1]
    if len(parts) == 4 and parts[0] == "msg":
        return "msg", parts[1], parts[2], parts[3]
    raise DocSourceError(f"无法解析的邮箱标识：{doc_id}")


def decode_subject(raw: Optional[str]) -> str:
    """解码可能带 MIME 编码的邮件主题。"""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:  # noqa: BLE001 - 主题编码异常不影响正文导入
        return (raw or "").strip()


def _body_of(msg: Message) -> str:
    """取正文：text/plain 优先，其次 text/html 转 Markdown。"""
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            if ctype == "text/plain" and not plain:
                plain = _decode_part(part)
            elif ctype == "text/html" and not html:
                html = _decode_part(part)
    else:
        ctype = (msg.get_content_type() or "").lower()
        text = _decode_part(msg)
        if ctype == "text/html":
            html = text
        else:
            plain = text
    if plain.strip():
        return plain.strip()
    if html.strip():
        return html_to_markdown(html)
    return ""


def _decode_part(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True) or b""
    except Exception:  # noqa: BLE001
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="ignore")
    except LookupError:
        return payload.decode("utf-8", errors="ignore")


class IMAPDocSource(BaseDocSource):
    source_type = "imap"
    token_in = "none"
    error_code_field = None
    timeout = 30.0

    def __init__(self, credentials: Dict[str, Any]) -> None:
        super().__init__(credentials)
        self._imap: Optional[imaplib.IMAP4] = None

    # ── 凭据 ──────────────────────────────────────────────────
    def _host(self) -> str:
        return resolve_hostname(self.credentials.get("host") or "")

    def _port(self) -> int:
        try:
            return int(str(self.credentials.get("port") or "").strip() or DEFAULT_PORT)
        except ValueError:
            return DEFAULT_PORT

    def _use_ssl(self) -> bool:
        raw = str(self.credentials.get("use_ssl") or "true").strip().lower()
        return raw not in ("false", "0", "no", "off")

    def _mailbox(self) -> str:
        return (self.credentials.get("mailbox") or "").strip() or DEFAULT_MAILBOX

    def _max_messages(self) -> int:
        try:
            value = int(str(self.credentials.get("max_messages") or "").strip()
                        or DEFAULT_MAX_MESSAGES)
        except ValueError:
            value = DEFAULT_MAX_MESSAGES
        return max(1, min(value, MAX_MESSAGES_LIMIT))

    def _since_days(self) -> int:
        try:
            value = int(str(self.credentials.get("since_days") or "").strip() or 0)
        except ValueError:
            value = 0
        return max(0, value)

    # ── 连接（线程包装）──────────────────────────────────────
    async def _connection(self) -> imaplib.IMAP4:
        if self._imap is not None:
            return self._imap
        host = self._host()
        username = (self.credentials.get("username") or "").strip()
        password = self.credentials.get("password") or ""
        if not username:
            raise DocSourceError("缺少邮箱用户名")
        if not password:
            raise DocSourceError("缺少邮箱密码 / 授权码")

        def _login() -> imaplib.IMAP4:
            factory = imaplib.IMAP4_SSL if self._use_ssl() else imaplib.IMAP4
            client = factory(host, self._port(), timeout=self.timeout)
            client.login(username, password)
            return client

        try:
            self._imap = await asyncio.to_thread(_login)
        except imaplib.IMAP4.error as exc:
            raise DocSourceError(f"邮箱登录失败：{exc}") from exc
        except OSError as exc:
            raise DocSourceError(f"无法连接邮箱服务器 {host}:{self._port()}（{exc}）") from exc
        return self._imap

    # ── 实现三个抽象方法 ──────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        try:
            client = await self._connection()

            def _probe() -> str:
                typ, _data = client.select(self._mailbox(), readonly=True)
                if typ != "OK":
                    raise DocSourceError(f"无法打开邮箱文件夹 {self._mailbox()}")
                return (_data[0].decode("utf-8", errors="ignore") if _data and _data[0] else "")

            info = await asyncio.to_thread(_probe)
            return DocConnResult(
                ok=True, message="连通成功：邮箱可登录",
                identity=f"{self._mailbox()}（{info or '已打开'}）",
            )
        except DocSourceError as exc:
            return DocConnResult(ok=False, message=str(exc))
        except Exception as exc:  # noqa: BLE001 - imaplib 异常类型繁杂，统一收敛
            return DocConnResult(ok=False, message=f"邮箱连通性测试失败：{exc}")
        finally:
            await self.aclose()

    async def list_nodes(self, parent_id: Optional[str] = None) -> List[ExternalDocRef]:
        try:
            client = await self._connection()
            if not parent_id:
                folders = await asyncio.to_thread(self._list_folders, client)
                return [
                    ExternalDocRef(doc_id=_encode_mailbox(name), title=name,
                                   node_type="folder")
                    for name in folders
                ]
            parts = _decode(parent_id)
            if parts[0] != "mbox":
                return []
            return await asyncio.to_thread(self._list_messages, client, parts[1])
        except DocSourceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DocSourceError(f"读取邮箱失败：{exc}") from exc
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            parts = _decode(doc_id)
            if parts[0] != "msg":
                raise DocSourceError(f"{doc_id} 不是可导入的邮件")
            _kind, mailbox, uid_validity, uid = parts
            client = await self._connection()
            raw = await asyncio.to_thread(self._fetch_raw, client, mailbox, uid_validity, uid)
            msg = email.message_from_bytes(raw)
            body = _body_of(msg)
            if not body.strip():
                raise DocSourceError("该邮件没有可提取的正文")
            return FetchDocResult(
                title=decode_subject(msg.get("Subject")) or f"邮件 {uid}",
                markdown=body,
                updated_at=msg.get("Date"),
            )
        except DocSourceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DocSourceError(f"读取邮件失败：{exc}") from exc
        finally:
            await self.aclose()

    # ── 阻塞实现（在线程中执行）──────────────────────────────
    @staticmethod
    def _list_folders(client: imaplib.IMAP4) -> List[str]:
        typ, data = client.list()
        if typ != "OK":
            raise DocSourceError("无法列出邮箱文件夹")
        names: List[str] = []
        for raw in data or []:
            text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
            # LIST 响应形如：(\Flags) "/" "INBOX"
            name = text.rsplit('"', 2)[-2] if '"' in text else text.split()[-1]
            name = name.strip()
            if name:
                names.append(name)
        return names

    def _list_messages(
        self, client: imaplib.IMAP4, mailbox: str
    ) -> List[ExternalDocRef]:
        typ, _data = client.select(mailbox, readonly=True)
        if typ != "OK":
            raise DocSourceError(f"无法打开邮箱文件夹 {mailbox}")
        uid_validity = self._uid_validity(client, mailbox)
        criteria = "ALL"
        since = self._since_days()
        if since:
            since_date = (datetime.now(timezone.utc) - timedelta(days=since)).strftime("%d-%b-%Y")
            criteria = f"(SINCE {since_date})"
        typ, data = client.uid("SEARCH", None, criteria)
        if typ != "OK":
            raise DocSourceError(f"搜索邮件失败（{mailbox}）")
        uids = [u for u in (data[0].split() if data and data[0] else [])]
        # 只保留最新的 N 封（IMAP SEARCH 返回按序递增，末尾即最新）
        uids = [u.decode() if isinstance(u, bytes) else str(u) for u in uids[-self._max_messages():]]
        refs: List[ExternalDocRef] = []
        for uid in uids:
            subject, date = self._envelope(client, uid)
            refs.append(
                ExternalDocRef(
                    doc_id=_encode_message(mailbox, uid_validity, uid),
                    title=subject or f"邮件 {uid}",
                    node_type="doc",
                    parent_id=_encode_mailbox(mailbox),
                    updated_at=date,
                )
            )
        return refs

    @staticmethod
    def _uid_validity(client: imaplib.IMAP4, mailbox: str) -> str:
        typ, data = client.status(mailbox, "(UIDVALIDITY)")
        text = (data[0].decode("utf-8", errors="ignore")
                if data and isinstance(data[0], bytes) else "")
        if typ == "OK" and "UIDVALIDITY" in text:
            return text.split("UIDVALIDITY")[1].strip(" ()").rstrip(")").strip()
        return "0"

    @staticmethod
    def _envelope(client: imaplib.IMAP4, uid: str) -> Tuple[str, str]:
        """只取信封（主题 + 日期），避免列举阶段就下载全部正文。"""
        typ, data = client.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])")
        if typ != "OK" or not data or not data[0]:
            return "", ""
        raw = data[0][1] if isinstance(data[0], tuple) else b""
        msg = email.message_from_bytes(raw or b"")
        return decode_subject(msg.get("Subject")), msg.get("Date") or ""

    @staticmethod
    def _fetch_raw(client: imaplib.IMAP4, mailbox: str, uid_validity: str, uid: str) -> bytes:
        typ, _data = client.select(mailbox, readonly=True)
        if typ != "OK":
            raise DocSourceError(f"无法打开邮箱文件夹 {mailbox}")
        current = IMAPDocSource._uid_validity(client, mailbox)
        if uid_validity != "0" and current != "0" and current != uid_validity:
            # UIDVALIDITY 变化说明邮箱被重建，UID 语义已失效
            raise DocSourceError(
                f"邮箱 {mailbox} 的 UIDVALIDITY 已变化（{uid_validity} → {current}），"
                "请重新选择邮件"
            )
        typ, data = client.uid("FETCH", uid, "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            raise DocSourceError(f"读取邮件失败（uid={uid}）")
        raw = data[0][1] if isinstance(data[0], tuple) else b""
        if len(raw or b"") > MAX_FETCH_BYTES:
            raise DocSourceError("邮件超过 8MB 上限，已跳过")
        return raw or b""

    # ── 资源释放 ──────────────────────────────────────────────
    async def aclose(self) -> None:
        await super().aclose()
        if self._imap is None:
            return
        client, self._imap = self._imap, None

        def _shutdown() -> None:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - 关闭失败不必影响主流程
                pass
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass

        await asyncio.to_thread(_shutdown)


register_doc_source(
    "imap",
    IMAPDocSource,
    ProviderMeta(
        source_type="imap",
        name="邮件（IMAP）",
        desc="邮箱文件夹内的邮件正文",
        host="（按邮箱服务器地址）",
        credential_fields=(
            CredField("host", "邮箱服务器", required=True, placeholder="imap.example.com",
                      hint="内网邮件服务器需先把域名加入 SSRF_WHITELIST"),
            CredField("port", "端口", placeholder="993", hint="SSL 默认 993，非 SSL 默认 143"),
            CredField("use_ssl", "启用 SSL", placeholder="true",
                      hint="默认 true；填 false 则使用明文 IMAP"),
            CredField("username", "邮箱账号", required=True, placeholder="kb@example.com"),
            CredField("password", "密码 / 授权码", required=True, secret=True,
                      placeholder="部分邮箱需填客户端专用授权码"),
            CredField("mailbox", "文件夹", placeholder="INBOX",
                      hint="默认 INBOX；可在「选择文档」时切换其它文件夹"),
            CredField("since_days", "仅最近 N 天", placeholder="留空则不限",
                      hint="按收件时间过滤，减少列举量"),
            CredField("max_messages", "最多邮件数", placeholder="200",
                      hint=f"默认 {DEFAULT_MAX_MESSAGES}，上限 {MAX_MESSAGES_LIMIT}"),
        ),
    ),
)
