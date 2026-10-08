import os, re, requests
from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://arxiv.org/html/2609.17523v1"
HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, "images")
os.makedirs(IMG_DIR, exist_ok=True)

html = open(os.path.join(HERE, "paper.html"), encoding="utf-8").read()
soup = BeautifulSoup(html, "html.parser")
article = soup.select_one("article.ltx_document")

# ---------- image download ----------
def img_basename(src):
    return src.rstrip("/").split("/")[-1]

content_imgs = []
for im in article.find_all("img"):
    src = im.get("src", "")
    if src.startswith("2609.17523v1/"):  # paper content figures only
        rel = re.sub(r"^2609\.17523v1/", "", src)
        url = BASE + "/" + rel
        bn = img_basename(src)
        dst = os.path.join(IMG_DIR, bn)
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                with open(dst, "wb") as f:
                    f.write(r.content)
                content_imgs.append((bn, im))
                print("saved", bn, len(r.content))
            else:
                print("FAIL", bn, r.status_code)
        except Exception as e:
            print("ERR", bn, e)

# ---------- inline rendering ----------
def math_tex(m):
    ann = m.find("annotation", attrs={"encoding": "application/x-tex"})
    if ann and ann.string:
        return ann.string.strip()
    return (m.get("alttext") or "").strip()

def clean_text(s):
    return re.sub(r"\s+", " ", s).strip()

def render_inline(node):
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        cls = child.get("class") or []
        cls = " ".join(cls)
        tag = child.name
        if "ltx_Math" in cls:
            tex = math_tex(child)
            disp = child.get("display")
            if disp == "block":
                out.append("\n$$\n" + tex + "\n$$\n")
            else:
                out.append("$" + tex + "$")
        elif tag == "a":
            txt = clean_text(child.get_text())
            href = child.get("href", "")
            if href and not href.startswith("#"):
                out.append(f"[{txt}]({href})")
            else:
                out.append(txt)
        elif tag == "cite":
            out.append(clean_text(child.get_text()))
        elif "ltx_text_bf" in cls or tag == "strong" or tag == "b":
            out.append("**" + render_inline(child) + "**")
        elif "ltx_text_it" in cls or tag == "em" or tag == "i":
            out.append("*" + render_inline(child) + "*")
        elif "ltx_text_tt" in cls or tag == "code":
            out.append("`" + clean_text(child.get_text()) + "`")
        elif "ltx_text_sc" in cls:
            out.append(render_inline(child).upper())
        else:
            out.append(render_inline(child))
    return "".join(out)

# ---------- block rendering ----------
lines = []

def flush_para(text):
    t = clean_text(text)
    if t:
        lines.append(t)
        lines.append("")

def render_heading(node, level):
    txt = clean_text(node.get_text())
    lines.append("#" * level + " " + txt)
    lines.append("")

def render_figure(fig):
    im = fig.find("img")
    if im:
        src = im.get("src", "")
        if src.startswith("2609.17523v1/"):
            bn = img_basename(src)
            cap = fig.find("figcaption")
            cap_txt = clean_text(cap.get_text()) if cap else ""
            lines.append(f"![{cap_txt[:60]}](images/{bn})")
            if cap_txt:
                lines.append("")
                lines.append("*" + cap_txt + "*")
            lines.append("")

def render_table(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        rows.append([clean_text(c.get_text()) for c in cells])
    if not rows:
        return
    # header = first row
    header = rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + " --- |" * len(header))
    for r in rows[1:]:
        # pad
        r = r + [""] * (len(header) - len(r))
        lines.append("| " + " | ".join(r) + " |")
    lines.append("")

def render_list(ul, ordered=False):
    items = ul.find_all("li", recursive=False)
    if not items:
        items = ul.find_all("li")
    for i, li in enumerate(items, 1):
        txt = clean_text(render_inline(li))
        prefix = f"{i}. " if ordered else "- "
        lines.append(prefix + txt)
    lines.append("")

def render_block(node, hlevel=2):
    for child in node.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag):
            continue
        cls = " ".join(child.get("class") or [])
        toks = cls.split()
        tag = child.name
        if tag in ("h1",):
            render_heading(child, 1)
        elif tag in ("h2", "h3", "h4", "h5", "h6"):
            lvl = int(tag[1])
            render_heading(child, lvl)
        elif "ltx_Math" in toks and child.get("display") == "block":
            lines.append("$$")
            lines.append(math_tex(child))
            lines.append("$$")
            lines.append("")
        elif tag == "p" or "ltx_para" in toks:
            flush_para(render_inline(child))
        elif "ltx_figure" in toks:
            render_figure(child)
        elif "ltx_table" in toks or tag == "table":
            render_table(child)
        elif "ltx_itemize" in toks or tag == "ul":
            render_list(child, ordered=False)
        elif "ltx_enumerate" in toks or tag == "ol":
            render_list(child, ordered=True)
        elif "ltx_theorem" in toks or tag == "blockquote":
            txt = clean_text(render_inline(child))
            if txt:
                lines.append("> " + txt)
                lines.append("")
        elif tag == "section" or tag == "div":
            # recurse; detect subsection level from class
            sub = hlevel
            if "ltx_subsection" in toks:
                sub = 3
            elif "ltx_subsubsection" in toks:
                sub = 4
            render_block(child, sub)
        else:
            # container with block children -> recurse so nested figures/tables are caught
            if child.find(["section", "figure", "table", "p", "ul", "ol",
                           "h1", "h2", "h3", "h4", "h5", "h6"]):
                render_block(child, hlevel)
            else:
                txt = clean_text(render_inline(child))
                if txt:
                    flush_para(txt)

render_block(article, 2)

# ---------- post-processing ----------
# 1) drop everything before the title heading (# ...)
start = 0
for i, l in enumerate(lines):
    if l.startswith("# "):
        start = i
        break
lines = lines[start:]

# 2) remove auto-generated Contents TOC paragraph
lines = [l for l in lines if not l.startswith("Contents ")]

# 3) clean footnote marker lines (e.g. "11footnotetext: Equal contribution.")
cleaned = []
for l in lines:
    m = re.match(r"^\d+footnotetext:\s*(.*)$", l)
    if m:
        cleaned.append("*" + m.group(1).strip() + "*")
    else:
        cleaned.append(l)
lines = cleaned

# 4) reorder "Figure N: ..." caption paragraphs to follow the image
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # find next non-empty line
    j = i + 1
    while j < len(lines) and lines[j] == "":
        j += 1
    if line.startswith("Figure ") and j < len(lines) and lines[j].lstrip().startswith("!["):
        img = lines[j].strip()
        k = j + 1
        while k < len(lines) and lines[k] == "":
            k += 1
        new_lines.append(img)
        new_lines.append("")
        new_lines.append("*" + line.strip() + "*")
        new_lines.append("")
        i = k
        continue
    new_lines.append(line)
    i += 1
lines = new_lines

# 5) move the References section to the end (arxiv html lists it before the appendix)
ref_start = None
next_head = None
for i, l in enumerate(lines):
    if l.startswith("## References"):
        ref_start = i
    elif ref_start is not None and l.startswith("## ") and i > ref_start:
        next_head = i
        break
if ref_start is not None:
    end = next_head if next_head is not None else len(lines)
    block = lines[ref_start:end]
    lines = lines[:ref_start] + lines[end:] + block

md = "\n".join(lines)
md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"

EN_NAME = "ScienceBuddy_Recursive-in-Recursive_Self-Improvement_for_Interactive_Scientific_Agents.md"
CN_NAME = EN_NAME[:-3] + "_CN.md"

out_path = os.path.join(HERE, EN_NAME)
open(out_path, "w", encoding="utf-8").write(md)
print("WROTE", out_path, "chars:", len(md))
print("EN_NAME:", EN_NAME)
print("CN_NAME:", CN_NAME)
