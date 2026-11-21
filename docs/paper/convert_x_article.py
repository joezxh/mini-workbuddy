#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 X（Twitter）长文 Article（Draft.js 内容结构）转换为 Markdown，并把正文图片下载到 images/。

数据来源：_x_article.json（由 api.fxtwitter.com 抓取的公开长文数据，含 article.content 的
Draft.js blocks/entityMap、article.media_entities 与 cover_media）。

与 convert_wechat.py 保持同一约定：
- 正文图片下载到 images/，Markdown 中用相对路径 images/xxx 引用；
- 文件名前缀带主题，避免与既有图片重名（seedance-fig01.jpg / gemini4-omni-fig01.jpg ...）。

Draft.js 结构要点：
- content.blocks[] 每块含 text / type / entityRanges / inlineStyleRanges；
- content.entityMap[] 为数组，下标即 entityRanges[].key；
  - MARKDOWN 实体：data.markdown 为已带 ``` 围栏的代码块原文，原样输出；
  - MEDIA 实体：data.mediaItems[0].mediaId → media_entities 的 media_id → original_img_url；
- block type → Markdown：unstyled/header-one/header-two/ordered-list-item/unordered-list-item/
  blockquote/code-block/atomic。
"""
import json
import os
import re
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
JSON_IN = os.path.join(BASE, "_x_article.json")
IMG_DIR = os.path.join(BASE, "images")
PREFIX = "situking"
MD_OUT = os.path.join(BASE, "如何快速进入陌生行业_五力模型拆解成9个AI提示词.md")

os.makedirs(IMG_DIR, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ---------------------------------------------------------------- 图片下载

_img_cache: dict[str, str] = {}


def download(url: str, fname: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://x.com/"})
    try:
        data = urllib.request.urlopen(req, timeout=40).read()
    except Exception as e:  # noqa: BLE001
        print("  [WARN] 下载失败:", url, "->", e)
        return False
    with open(os.path.join(IMG_DIR, fname), "wb") as f:
        f.write(data)
    print(f"  [OK] {fname}  ({len(data)} bytes)")
    return True


def img_ref(url: str, fname: str) -> str:
    """下载并返回相对路径；同 URL 只下载一次。"""
    if url in _img_cache:
        return _img_cache[url]
    ok = download(url, fname)
    local = f"images/{fname}" if ok else url
    _img_cache[url] = local
    return local


# ---------------------------------------------------------------- 行内样式

_STYLE = {
    "Bold": "**",
    "ITALIC": "*",
    "Italic": "*",
    "CODE": "`",
    "Code": "`",
    "Strikethrough": "~~",
    "UNDERLINE": "",
    "Underline": "",
}


def apply_styles(text: str, ranges: list) -> str:
    """把 Draft.js 行内样式区间转成 Markdown 行内标记（从后往前替换，避免偏移串位）。"""
    for rng in sorted(ranges or [], key=lambda r: r.get("offset", 0), reverse=True):
        style = rng.get("style", "")
        mark = _STYLE.get(style)
        if not mark:
            continue
        off = int(rng.get("offset", 0))
        ln = int(rng.get("length", 0))
        if off < 0 or off + ln > len(text):
            continue
        seg = text[off:off + ln]
        if style in ("CODE", "Code"):
            text = text[:off] + mark + seg + mark + text[off + ln:]
        else:
            text = text[:off] + mark + seg + mark + text[off + ln:]
    return text


# ---------------------------------------------------------------- 块渲染

def main() -> None:
    with open(JSON_IN, encoding="utf-8") as f:
        raw = json.load(f)

    tweet = raw["tweet"]
    art = tweet["article"]
    content = art["content"]
    blocks = content["blocks"]
    entity_map = content.get("entityMap") or []

    # mediaId -> {url,w,h}
    media_map: dict[str, dict] = {}
    for m in art.get("media_entities") or []:
        mi = m["media_info"]
        media_map[str(m.get("media_id"))] = {
            "url": mi.get("original_img_url"),
            "w": mi.get("original_img_width"),
            "h": mi.get("original_img_height"),
        }
    cover = art.get("cover_media") or {}
    cover_info = (cover.get("media_info") or {})
    cover_url = cover_info.get("original_img_url")

    img_seq = {"n": 0}

    def media_local(url: str) -> str:
        img_seq["n"] += 1
        ext = "jpg"
        m = re.search(r"\.([A-Za-z0-9]{3,4})(?:\?|$)", url or "")
        if m:
            ext = m.group(1).lower()
        fname = f"{PREFIX}-fig{img_seq['n']:02d}.{ext}"
        return img_ref(url, fname)

    def entity_of(key):
        try:
            e = entity_map[int(key)]
        except (ValueError, IndexError, TypeError):
            return None
        return (e or {}).get("value") or {}

    out: list[str] = []
    ol_counter = 0

    for blk in blocks:
        btype = blk.get("type", "unstyled")
        text = blk.get("text", "") or ""

        # ---- atomic 块：承载 MARKDOWN 代码块 / MEDIA 图片
        if btype == "atomic":
            for rng in blk.get("entityRanges") or []:
                ent = entity_of(rng.get("key"))
                if not ent:
                    continue
                etype = (ent.get("type") or "").upper()
                data = ent.get("data") or {}
                if etype == "MARKDOWN":
                    md = (data.get("markdown") or "").strip()
                    if md:
                        out.append(md)
                elif etype == "MEDIA":
                    items = data.get("mediaItems") or []
                    mid = str(items[0].get("mediaId")) if items else None
                    info = media_map.get(mid or "")
                    if info and info.get("url"):
                        out.append(f"![图]({media_local(info['url'])})")
                elif etype == "LINK":
                    url = data.get("url") or data.get("uri") or ""
                    if url:
                        out.append(f"[链接]({url})")
            continue

        # ---- 普通块：应用行内样式与行内实体
        text = apply_styles(text, blk.get("inlineStyleRanges"))
        for rng in sorted(blk.get("entityRanges") or [],
                          key=lambda r: r.get("offset", 0), reverse=True):
            ent = entity_of(rng.get("key"))
            if not ent:
                continue
            etype = (ent.get("type") or "").upper()
            data = ent.get("data") or {}
            off = int(rng.get("offset", 0))
            ln = int(rng.get("length", 0))
            if etype == "MEDIA":
                items = data.get("mediaItems") or []
                mid = str(items[0].get("mediaId")) if items else None
                info = media_map.get(mid or "")
                rep = f"![图]({media_local(info['url'])})" if info and info.get("url") else ""
            elif etype == "LINK":
                rep = f"[{text[off:off + ln]}]({data.get('url') or ''})"
            else:
                continue
            text = text[:off] + rep + text[off + ln:]

        stripped = text.strip()
        if not stripped:
            continue

        if btype == "header-one":
            out.append("# " + stripped)
        elif btype == "header-two":
            out.append("## " + stripped)
        elif btype == "header-three":
            out.append("### " + stripped)
        elif btype == "header-four":
            out.append("#### " + stripped)
        elif btype == "blockquote":
            out.append("> " + stripped)
        elif btype == "code-block":
            out.append("```\n" + stripped + "\n```")
        elif btype == "unordered-list-item":
            out.append("- " + stripped)
        elif btype == "ordered-list-item":
            ol_counter += 1
            out.append(f"{ol_counter}. {stripped}")
        else:
            out.append(stripped)

        # 列表项之间连续时重置有序编号（新列表从 1 开始）
        if btype not in ("ordered-list-item", "unordered-list-item"):
            ol_counter = 0

    body = "\n\n".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body)

    # ---- 文首元信息
    author = tweet.get("author") or {}
    created = art.get("created_at") or tweet.get("created_at")
    date_str = created[:10] if created else ""
    stats = []
    if tweet.get("likes") is not None:
        stats.append(f"👍 {tweet['likes']}")
    if tweet.get("retweets") is not None:
        stats.append(f"🔁 {tweet['retweets']}")
    if tweet.get("replies") is not None:
        stats.append(f"💬 {tweet['replies']}")
    if tweet.get("views") is not None:
        stats.append(f"👁 {tweet['views']}")

    title = art.get("title") or tweet.get("text", "").split("\n")[0]
    tweet_url = tweet.get("url") or ""
    art_url = f"https://x.com/i/article/{art.get('id')}"

    header = (
        f"# {title}\n\n"
        f"> 作者：{author.get('name') or author.get('screen_name')}"
        f"（@{author.get('screen_name')}）  \n"
        f"> 来源：X 长文（Article）  \n"
        f"> 发布时间：{date_str}  \n"
        f"> 原文链接：{tweet_url}  \n"
        f"> 文章链接：{art_url}  \n"
        f"> 互动数据：{' · '.join(stats)}\n\n"
        "---\n\n"
    )

    if cover_url:
        cover_local = img_ref(cover_url, f"{PREFIX}-cover.jpg")
        header += f"![封面]({cover_local})\n\n"

    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(header + body + "\n")

    print(f"已写出 Markdown：{MD_OUT}")
    print(f"下载图片：{img_seq['n']} 张正文图 + 封面 1 张")
    print(f"块数：{len(blocks)}  实体数：{len(entity_map)}")


if __name__ == "__main__":
    main()
