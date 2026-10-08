import os

HERE = os.path.dirname(os.path.abspath(__file__))
EN = "ScienceBuddy_Recursive-in-Recursive_Self-Improvement_for_Interactive_Scientific_Agents.md"
CN = EN[:-3] + "_CN.md"

EN_TOGGLE = """<p align="center">
  <a href="{cn}" title="查看中文版本"><b>🇨🇳 中文</b></a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <span><b>English</b></span>
</p>

---

""".format(cn=CN)

CN_TOGGLE = """<p align="center">
  <span><b>中文</b></span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="{en}" title="View English version"><b>🇬🇧 English</b></a>
</p>

---

""".format(en=EN)

# Build Chinese file from translated parts
parts = ["cn_part1.md", "cn_part2.md", "cn_part3.md", "cn_part4.md",
         "cn_part5.md", "cn_part6.md", "cn_part7.md", "cn_references.md"]
cn_body = []
for p in parts:
    path = os.path.join(HERE, p)
    if os.path.exists(path):
        cn_body.append(open(path, encoding="utf-8").read().strip())
cn_text = CN_TOGGLE + "\n\n".join(cn_body) + "\n"
open(os.path.join(HERE, CN), "w", encoding="utf-8").write(cn_text)
print("WROTE", CN, len(cn_text))

# Prepend toggle to English file
en_path = os.path.join(HERE, EN)
en_text = open(en_path, encoding="utf-8").read()
if "🇨🇳" not in en_text:
    en_text = EN_TOGGLE + en_text
    open(en_path, "w", encoding="utf-8").write(en_text)
    print("UPDATED EN with toggle")
else:
    print("EN toggle already present")
