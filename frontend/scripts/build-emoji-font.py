"""生成菜单彩色图标专用的彩色 emoji 字体子集。

用法（需要 Python 3.9+ 且装有 fontTools、brotli；仓库 backend/.venv 已具备）::

    python frontend/scripts/build-emoji-font.py

流程：
  1. 从 ``src/constants/emoji-icons.ts`` 提取全部 emoji 字符 → Unicode 码点集；
  2. 下载 Noto Color Emoji（Google Fonts 分发的 COLRv1 版本，OFL-1.1 允许再分发）；
  3. 用 fontTools 子集化到上述码点，输出 ``public/fonts/mbw-emoji.woff2``。

产物已被 ``src/styles/tokens.css`` 的 ``@font-face`` 引用（family: MinWorkBuddy Emoji）。
字体文件缺失或某个码点未被覆盖时，浏览器自动回落到各平台系统彩色 emoji 字体
（Segoe UI Emoji / Apple Color Emoji / Noto Color Emoji），不影响功能。

注意：不要用系统自带的 ``C:\\Windows\\Fonts\\seguiemj.ttf``（Segoe UI Emoji）——
它是 Microsoft 专有字体，禁止再分发，不可随仓库分发。
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
ICON_TS = FRONTEND_ROOT / "src" / "constants" / "emoji-icons.ts"
CACHE_DIR = FRONTEND_ROOT / "scripts" / ".emoji-font-cache"
OUTPUT_WOFF2 = FRONTEND_ROOT / "public" / "fonts" / "mbw-emoji.woff2"

GOOGLE_FONT_CSS = "https://fonts.googleapis.com/css2?family=Noto+Color+Emoji"

# Emoji 所在的 Unicode 区段（含变体选择符 / 零宽连接符的组合情况）
EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),
    (0x1F1E6, 0x1F1FF),  # 区域指示符（旗帜）
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0x2190, 0x21FF),    # 箭头类符号（部分带彩色变体）
    (0x2300, 0x23FF),    # ⌚⌛ 等
    (0x25A0, 0x25FF),
    (0x2B50, 0x2B55),
)
COMBINING = {0xFE0F, 0x200D, 0x20E3}


def is_emoji_codepoint(cp: int) -> bool:
    if cp in COMBINING:
        return True
    return any(lo <= cp <= hi for lo, hi in EMOJI_RANGES)


def extract_codepoints() -> set[int]:
    """从 emoji-icons.ts 的 ``char: '…'`` 中提取所有码点。"""
    if not ICON_TS.exists():
        sys.exit(f"[emoji-font] 找不到图标集文件：{ICON_TS}")
    source = ICON_TS.read_text(encoding="utf-8")
    chars = re.findall(r"char:\s*'([^']*)'", source)
    if not chars:
        sys.exit("[emoji-font] 图标集里没有解析到任何 char")
    codepoints: set[int] = set()
    for text in chars:
        for ch in text:
            cp = ord(ch)
            if is_emoji_codepoint(cp):
                codepoints.add(cp)
    return codepoints


def resolve_source_font() -> Path:
    """下载 Noto Color Emoji 源字体（带缓存），返回本地路径。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / "NotoColorEmoji.ttf"
    if cached.exists() and cached.stat().st_size > 1_000_000:
        print(f"[emoji-font] 使用缓存：{cached}")
        return cached

    print("[emoji-font] 查询 Google Fonts CSS ...")
    req = urllib.request.Request(
        GOOGLE_FONT_CSS, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        css = resp.read().decode("utf-8")
    match = re.search(r"src:\s*url\((https://[^)]+\.ttf)\)", css)
    if not match:
        sys.exit("[emoji-font] 无法从 Google Fonts CSS 解析出 TTF 地址")
    url = match.group(1)
    print(f"[emoji-font] 下载源字体：{url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    cached.write_bytes(data)
    print(f"[emoji-font] 源字体已缓存：{cached}（{len(data) / 1024 / 1024:.1f} MiB）")
    return cached


def build(codepoints: set[int]) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    src = resolve_source_font()

    options = subset.Options()
    options.flavor = "woff2"
    options.desubroutinize = True
    options.drop_tables += ["DSIG"]
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.notdef_outline = True
    options.recalc_bounds = True
    options.recalc_timestamp = False
    options.hinting = False

    print(f"[emoji-font] 子集化 {len(codepoints)} 个码点 ...")
    font = TTFont(str(src), fontNumber=0, lazy=False)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)

    OUTPUT_WOFF2.parent.mkdir(parents=True, exist_ok=True)
    font.flavor = "woff2"
    font.save(str(OUTPUT_WOFF2))
    font.close()

    # 复核：产物实际覆盖的码点数
    check = TTFont(str(OUTPUT_WOFF2))
    covered = set(check.getBestCmap().keys())
    missing = sorted(codepoints - covered)
    size_kb = OUTPUT_WOFF2.stat().st_size / 1024
    print(f"[emoji-font] 输出：{OUTPUT_WOFF2}（{size_kb:.1f} KiB）")
    print(f"[emoji-font] 覆盖码点：{len(covered)}/{len(codepoints)}")
    if missing:
        print(f"[emoji-font] 未覆盖（将回落到系统字体）：{[hex(c) for c in missing]}")
    check.close()


def main() -> None:
    codepoints = extract_codepoints()
    print(f"[emoji-font] 图标集解析到 {len(codepoints)} 个码点")
    build(codepoints)


if __name__ == "__main__":
    main()
