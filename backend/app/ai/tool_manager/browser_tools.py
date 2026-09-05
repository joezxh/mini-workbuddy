"""浏览器自动化工具 - 基于 Playwright 的网页操作。

基于 AgentScope 2.0.4 ToolBase 协议实现。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from agentscope.tool import ToolBase, ToolChunk
from agentscope.message import TextBlock
from agentscope.permission import (
    PermissionBehavior,
    PermissionContext,
    PermissionDecision,
)

logger = logging.getLogger(__name__)


def _text_chunk(payload: Any) -> ToolChunk:
    """把任意 python 对象序列化成 TextBlock ToolChunk。"""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return ToolChunk(content=[TextBlock(type="text", text=text)])


class BrowserAutomation(ToolBase):
    """浏览器自动化 - 网页导航、元素操作、数据抓取、截图。"""

    name: str = "browser_automation"
    description: str = "自动化浏览器操作：导航网页、点击元素、填写表单、抓取数据、页面截图"
    input_schema: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "click", "fill", "extract", "screenshot"],
                "description": "操作类型：navigate-导航 / click-点击 / fill-填写 / extract-提取文本 / screenshot-截图",
            },
            "url": {"type": "string", "description": "目标网页 URL"},
            "selector": {
                "type": "string",
                "description": "CSS 选择器（click/fill/extract 时使用）",
            },
            "value": {
                "type": "string",
                "description": "填写的内容（fill 操作时使用）",
            },
            "screenshot_path": {
                "type": "string",
                "description": "截图保存路径（screenshot 操作时使用）",
            },
            "wait_selector": {
                "type": "string",
                "description": "等待元素出现的 CSS 选择器（可选）",
            },
            "timeout": {
                "type": "integer",
                "description": "超时毫秒数",
                "default": 30000,
            },
        },
        "required": ["action", "url"],
    }
    is_concurrency_safe: bool = False
    is_read_only: bool = False

    async def check_permissions(
        self, tool_input: dict, context: PermissionContext,
    ) -> PermissionDecision:
        action = tool_input.get("action", "navigate")
        if action in ("navigate", "extract", "screenshot"):
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="Read-only browser action.",
            )
        return PermissionDecision(
            behavior=PermissionBehavior.ASK,
            message=f"Browser action '{action}' may modify page state.",
        )

    async def call(
        self,
        action: str,
        url: str,
        selector: Optional[str] = None,
        value: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        wait_selector: Optional[str] = None,
        timeout: int = 30000,
    ) -> ToolChunk:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return _text_chunk({"error": "playwright 未安装，请执行: pip install playwright && playwright install chromium"})

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                page = await context.new_page()
                page.set_default_timeout(timeout)

                try:
                    # 导航到页面
                    await page.goto(url, wait_until="domcontentloaded")

                    if wait_selector:
                        await page.wait_for_selector(wait_selector, timeout=timeout)

                    if action == "navigate":
                        title = await page.title()
                        return _text_chunk({
                            "action": "navigate",
                            "url": url,
                            "title": title,
                            "status": "success",
                        })

                    elif action == "click":
                        if not selector:
                            return _text_chunk({"error": "click 操作需要提供 selector 参数"})
                        await page.click(selector)
                        await page.wait_for_load_state("domcontentloaded")
                        return _text_chunk({
                            "action": "click",
                            "selector": selector,
                            "status": "success",
                        })

                    elif action == "fill":
                        if not selector:
                            return _text_chunk({"error": "fill 操作需要提供 selector 参数"})
                        if value is None:
                            return _text_chunk({"error": "fill 操作需要提供 value 参数"})
                        await page.fill(selector, value)
                        return _text_chunk({
                            "action": "fill",
                            "selector": selector,
                            "status": "success",
                        })

                    elif action == "extract":
                        if selector:
                            elements = await page.query_selector_all(selector)
                            texts = []
                            for el in elements:
                                text = await el.inner_text()
                                texts.append(text.strip())
                            return _text_chunk({
                                "action": "extract",
                                "selector": selector,
                                "texts": texts,
                                "count": len(texts),
                            })
                        else:
                            # 提取整个页面文本
                            text = await page.inner_text("body")
                            return _text_chunk({
                                "action": "extract",
                                "text": text[:5000],  # 限制长度
                                "truncated": len(text) > 5000,
                            })

                    elif action == "screenshot":
                        if not screenshot_path:
                            screenshot_path = os.path.join(
                                os.getcwd(), "uploads", f"screenshot_{int(page.url.__hash__())}.png"
                            )
                        os.makedirs(os.path.dirname(screenshot_path) or ".", exist_ok=True)
                        await page.screenshot(path=screenshot_path, full_page=True)
                        return _text_chunk({
                            "action": "screenshot",
                            "screenshot_path": screenshot_path,
                            "status": "success",
                        })

                    else:
                        return _text_chunk({"error": f"未知 action: {action}"})

                finally:
                    await browser.close()

        except Exception as exc:
            logger.warning("browser_automation failed: %s", exc)
            return _text_chunk({"error": str(exc)})
