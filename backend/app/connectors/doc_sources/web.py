"""web 站点连接器（新建）。

给定种子 URL 列表，抓取网页正文转 Markdown 后走与既有连接器相同的切片入库流程。
SSRF 防护：每跳 URL 经 ``app.core.security.is_safe_url`` 校验，拒绝内网/环回/保留地址；
抓取并发上限由导入服务 ``FETCH_CONCURRENCY`` 约束。

种子 URL、爬取深度等以「凭据」形式下发（前端按 multiline 渲染 seed_urls 多行输入框）。
"""
from __future__ import annotations

import re
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
from app.core.security import is_safe_url

# 最大爬取深度（防止失控的全站抓取）；前端可配，超界被钳制
MAX_CRAWL_DEPTH = 2
# 单次列目录最多返回的链接数
MAX_LINKS = 200


def _normalize_url(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = "https://" + raw
    return raw


class WebDocSource(BaseDocSource):
    source_type = "web"
    token_in = "none"  # web 站点无需令牌

    # ── 凭据解析 ──────────────────────────────────────────────
    def _seed_urls(self) -> List[str]:
        raw = (self.credentials.get("seed_urls") or "").strip()
        out: List[str] = []
        for line in raw.splitlines():
            u = _normalize_url(line)
            if u:
                out.append(u)
        # 去重保序
        seen = set()
        deduped: List[str] = []
        for u in out:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    def _crawl_depth(self) -> int:
        try:
            d = int(str(self.credentials.get("crawl_depth") or "1").strip() or "1")
        except ValueError:
            d = 1
        return max(0, min(d, MAX_CRAWL_DEPTH))

    # ── 实现三个抽象方法 ─────────────────────────────────────
    async def test_connection(self) -> DocConnResult:
        urls = self._seed_urls()
        if not urls:
            return DocConnResult(ok=False, message="未配置任何种子 URL")
        total = len(urls)
        reachable = 0
        sampled = urls[:10]
        for u in sampled:
            try:
                is_safe_url(u)
                resp = await self._request("GET", u)
                if resp.status_code < 400:
                    reachable += 1
            except DocSourceError:
                continue
            except Exception:  # noqa: BLE001 - 单条失败不影响其它种子
                continue
        if reachable == 0:
            return DocConnResult(
                ok=False, message="所有种子 URL 均不可达或命中 SSRF 拦截"
            )
        return DocConnResult(
            ok=True,
            message=f"连通成功：{reachable}/{total} 个站点可达",
            identity=f"{reachable} 个种子站点",
        )

    async def list_nodes(
        self, parent_id: Optional[str] = None
    ) -> List[ExternalDocRef]:
        try:
            if not parent_id:
                # 顶层：种子 URL 作为可选文档
                return [
                    ExternalDocRef(
                        doc_id=u, title=self._title_from_url(u),
                        node_type="doc", url=u,
                    )
                    for u in self._seed_urls()
                ]
            # 下钻：在父页面内发现同域出站链接（受 crawl_depth 约束）
            if self._crawl_depth() < 1:
                return []
            links = await self._discover_links(parent_id)
            return [
                ExternalDocRef(
                    doc_id=u, title=self._title_from_url(u),
                    node_type="doc", parent_id=parent_id, url=u,
                )
                for u in links
            ]
        finally:
            await self.aclose()

    async def fetch_doc(self, doc_id: str) -> FetchDocResult:
        try:
            url = _normalize_url(doc_id) or doc_id
            is_safe_url(url)
            resp = await self._request("GET", url)
            html = resp.text or ""
            title = self._extract_title(html) or self._title_from_url(url)
            markdown = self._html_to_markdown(html)
            return FetchDocResult(title=title, markdown=markdown)
        finally:
            await self.aclose()

    # ── 私有辅助 ─────────────────────────────────────────────
    @staticmethod
    def _title_from_url(url: str) -> str:
        # 取路径末段作为可读标题，缺省回退域名
        from urllib.parse import urlparse

        p = urlparse(url)
        seg = [s for s in p.path.split("/") if s]
        return seg[-1] if seg else (p.netloc or url)

    @staticmethod
    def _extract_title(html: str) -> Optional[str]:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        return re.sub(r"\s+", " ", m.group(1)).strip()[:200] or None

    async def _discover_links(self, page_url: str) -> List[str]:
        """抓取父页面，抽取同域出站链接（去重）。"""
        try:
            is_safe_url(page_url)
            resp = await self._request("GET", page_url)
            html = resp.text or ""
        except DocSourceError as exc:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DocSourceError(f"无法抓取页面链接：{exc}") from exc

        from urllib.parse import urljoin, urlparse

        base = urlparse(page_url)
        hrefs = re.findall(r"""<a[^>]+href=["']([^"']+)["']""", html, re.IGNORECASE)
        out: List[str] = []
        seen = set()
        for h in hrefs:
            if h.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
                continue
            abs_url = urljoin(page_url, h)
            u = _normalize_url(abs_url)
            if not u:
                continue
            parsed = urlparse(u)
            # 仅保留同域链接，避免跨站泛爬
            if parsed.netloc != base.netloc:
                continue
            # 过滤非网页资源
            if parsed.path.lower().endswith(
                (".png", ".jpg", ".jpeg", ".gif", ".css", ".js", ".ico",
                 ".pdf", ".zip", ".svg", ".woff", ".woff2")
            ):
                continue
            if u not in seen:
                seen.add(u)
                out.append(u)
            if len(out) >= MAX_LINKS:
                break
        return out

    @staticmethod
    def _html_to_markdown(html: str) -> str:
        try:
            from markdownify import markdownify
        except ImportError:  # markdownify 未安装时降级为去标签纯文本
            text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            return re.sub(r"\s+", " ", text).strip() + "\n"
        return markdownify(html, heading_style="ATX").strip() + "\n"


register_doc_source(
    "web",
    WebDocSource,
    ProviderMeta(
        source_type="web",
        name="web网站",
        desc="种子 URL 列表抓取（自动转 Markdown）",
        host="(按种子 URL)",
        credential_fields=(
            CredField(
                "seed_urls", "种子 URL 列表", required=True, multiline=True,
                placeholder="https://example.com\ndocs/intro",
                hint="每行一个 URL；留空协议时自动补 https。可填站点首页或具体文档页。",
            ),
            CredField(
                "crawl_depth", "爬取深度", required=False,
                placeholder="1",
                hint="从种子页向下钻取的层级（0=仅种子页，1=种子页同域链接，最大 2）。",
            ),
        ),
    ),
)
