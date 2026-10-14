#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将微信公众号文章 HTML（_wechat.html）转换为 Markdown，并把正文图片下载到 images/。

相比通用 html2text，本脚本专门处理微信图文结构：
- 标题（h1-h6）中若嵌套了图片，则整体当作「图 + 图注」块渲染，避免把图注误判成标题；
- 列表（ul/ol/li）按层级渲染；行内加粗/斜体/代码/链接保留；
- 所有正文中出现的图片（含封面、图、专辑缩略图等）下载到 images/ 并以相对路径引用。
"""
import os
import re
import urllib.request
from lxml import html as lxml_html

BASE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(BASE, "_wechat.html")
IMG_DIR = os.path.join(BASE, "images")
MD_OUT = os.path.join(BASE, "淘宝直播数字人Harness-Aware-Training.md")

os.makedirs(IMG_DIR, exist_ok=True)

URL_RE = re.compile(r"wx_fmt=(\w+)")
_counter = {"n": 0}
_seen: dict[str, str] = {}


def img_ext(url: str) -> str:
    m = URL_RE.search(url)
    if m:
        return {
            "png": "png", "jpeg": "jpg", "jpg": "jpg",
            "gif": "gif", "webp": "webp", "other": "png",
        }.get(m.group(1).lower(), "png")
    return "png"


def download(url: str, fname: str) -> bool:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://mp.weixin.qq.com/"},
    )
    try:
        data = urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:  # noqa: BLE001
        print("  [WARN] 下载失败:", url, "->", e)
        return False
    with open(os.path.join(IMG_DIR, fname), "wb") as f:
        f.write(data)
    return True


def handle_img(node) -> str:
    ds = node.get("data-src") or node.get("src")
    if not ds:
        return ""
    ds = ds.replace("&amp;", "&")
    if ds in _seen:
        local = _seen[ds]
    else:
        _counter["n"] += 1
        ext = img_ext(ds)
        fname = f"fig_{_counter['n']:03d}.{ext}"
        ok = download(ds, fname)
        local = f"images/{fname}" if ok else ds
        _seen[ds] = local
    alt = node.get("alt") or ""
    return f"![{alt}]({local})"


def inline_children(node) -> str:
    parts = []
    if node.text:
        parts.append(node.text)
    for child in node:
        parts.append(inline(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def inline(node) -> str:
    if isinstance(node, str):
        return node
    tag = node.tag
    if not isinstance(tag, str):
        return ""
    if tag in ("script", "style"):
        return ""
    if tag == "br":
        return "\n"
    if tag == "img":
        return handle_img(node)
    if tag in ("strong", "b"):
        return "**" + inline_children(node).strip() + "**"
    if tag in ("em", "i"):
        return "*" + inline_children(node).strip() + "*"
    if tag == "code":
        return "`" + inline_children(node) + "`"
    if tag == "a":
        href = node.get("href")
        t = inline_children(node)
        return f"[{t}]({href})" if href else t
    # 列表/表格在块级处理，行内遇到直接跳过其内容（避免重复）
    if tag in ("ul", "ol", "table"):
        return ""
    return inline_children(node)


def convert_list(node, depth: int = 0) -> str:
    lines = []
    ordered = node.tag == "ol"
    idx = 1
    for li in node.findall("li"):
        txt = inline(li).strip()
        marker = f"{idx}. " if ordered else "- "
        lines.append("  " * depth + marker + txt)
        for sub in li:
            if sub.tag in ("ul", "ol"):
                lines.append(convert_list(sub, depth + 1))
        if ordered:
            idx += 1
    return "\n".join(lines)


def convert_block(node, depth: int = 0) -> str:
    out = []
    for child in node:
        if not isinstance(child.tag, str):
            continue
        tag = child.tag
        if tag in ("script", "style"):
            continue
        if tag == "img":
            out.append(handle_img(child))
            if child.tail:
                out.append(child.tail)
            continue
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            txt = inline(child)
            if child.find(".//img") is not None:
                # 标题内嵌了图片：可能是「图 + 图注」块，也可能是带装饰图标的普通标题
                text_only = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", txt).strip()
                if text_only.startswith("图"):
                    # 真正的图注块：图片行 + 图注文本
                    imgs = re.findall(r"!\[[^\]]*\]\([^)]*\)", txt)
                    block = "\n".join(imgs)
                    if text_only:
                        block += "\n" + text_only
                    out.append(block)
                else:
                    # 带装饰图标的普通标题：去掉图标，仅保留标题文字
                    if text_only:
                        out.append("#" * level + " " + text_only)
            else:
                stripped = txt.strip()
                if stripped:
                    out.append("#" * level + " " + stripped)
            if child.tail:
                out.append(child.tail)
            continue
        if tag == "p":
            txt = inline(child).strip()
            if txt:
                out.append(txt)
            if child.tail:
                out.append(child.tail)
            continue
        if tag in ("ul", "ol"):
            out.append(convert_list(child, depth))
            if child.tail:
                out.append(child.tail)
            continue
        if tag == "pre":
            code = child.text_content()
            out.append("```\n" + code + "\n```")
            if child.tail:
                out.append(child.tail)
            continue
        # section / div / blockquote / td 等容器：透明递归
        out.append(convert_block(child, depth))
        if child.tail:
            out.append(child.tail)
    blocks = [b for b in out if b is not None and b.strip() != ""]
    return "\n\n".join(blocks)


def main() -> None:
    doc = lxml_html.fromstring(open(HTML, encoding="utf-8").read())
    content = doc.get_element_by_id("js_content")
    if content is None:
        raise SystemExit("找不到 #js_content 正文节点")

    raw = convert_block(content).strip() + "\n"
    raw = re.sub(r"\n{3,}", "\n\n", raw)

    header = (
        "# 淘宝直播数字人互动 Harness-Aware Training 实践：让 Agent Model 随 Harness 一起进化\n\n"
        "> 来源：大淘宝技术（微信公众号）  \n"
        "> 作者：语瀚（淘天集团-直播AIGC团队）  \n"
        "> 发布时间：2026-10-09 14:04  \n"
        "> 原文：https://mp.weixin.qq.com/s/ajL2P5PY1HcQnJt_RFalnw  \n"
        "> 技术报告：https://arxiv.org/pdf/2608.15763  \n"
        "> Hugging Face：https://huggingface.co/papers/2608.15763\n\n"
        "---\n\n"
    )

    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(header + raw)

    print(f"已写出 Markdown：{MD_OUT}")
    print(f"下载正文图片：{_counter['n']} 张")


if __name__ == "__main__":
    main()
