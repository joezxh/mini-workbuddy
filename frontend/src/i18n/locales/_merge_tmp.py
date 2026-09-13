"""临时 v3：合并 _pending/*.json 到四语言包（跳过已存在 key）。用完即删。"""
import io
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
LOCALES = ["zh-CN", "zh-TW", "en-US", "ja-JP"]


def ts_escape(v: str) -> str:
    return v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


total = 0
for loc in LOCALES:
    f = HERE / f"{loc}.ts"
    src = io.open(f, encoding="utf-8").read()
    for pf in sorted(HERE.glob("_pending/*.json")):
        data = json.loads(io.open(pf, encoding="utf-8").read())
        by_ns: dict = {}
        for key, tr in data.items():
            ns, _ = key.split(".", 1)
            by_ns.setdefault(ns, {})[key] = tr[loc]
        for ns, entries in by_ns.items():
            m = re.search(r"(?m)^  %s: \{[\s\S]*?^  \},$" % re.escape(ns), src)
            if m:
                add = "".join(
                    f"    {k.split('.', 1)[1]}: '{ts_escape(v)}',\n"
                    for k, v in entries.items()
                    if f"    {k.split('.', 1)[1]}:" not in m.group(0)
                )
                if add:
                    src = src.replace(m.group(0), m.group(0).replace("\n  },", "\n" + add + "  },", 1), 1)
            else:
                block = f"  {ns}: {{\n" + "".join(
                    f"    {k.split('.', 1)[1]}: '{ts_escape(v)}',\n" for k, v in entries.items()
                ) + "  },\n"
                idx = src.rstrip().rfind("}")
                src = src[:idx] + block + "\n" + src[idx:]
        total += len(data)
    io.open(f, "w", encoding="utf-8", newline="").write(src)

print("merged (key×locale):", total)

# key 对齐检查
def flatten(src: str):
    keys, cur = set(), None
    for line in src.split("\n"):
        m = re.match(r"^  (\w+): \{", line)
        if m:
            cur = m.group(1)
            continue
        if re.match(r"^  \},?", line):
            cur = None
            continue
        m = re.match(r"^    (\w+):", line)
        if m and cur:
            keys.add(f"{cur}.{m.group(1)}")
    return keys


sets = {loc: flatten(io.open(HERE / f"{loc}.ts", encoding="utf-8").read()) for loc in LOCALES}
for loc in LOCALES:
    print(loc, len(sets[loc]))
base = sets["zh-CN"]
ok = True
for loc in LOCALES[1:]:
    miss, extra = base - sets[loc], sets[loc] - base
    if miss or extra:
        ok = False
        print(f"[{loc}] 缺失{len(miss)} {sorted(miss)[:6]} | 多余{len(extra)} {sorted(extra)[:6]}")
print("ALIGN_OK" if ok else "ALIGN_FAIL")
