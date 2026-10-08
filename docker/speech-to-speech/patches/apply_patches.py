#!/usr/bin/env python3
"""speech-to-speech 运行时缺陷补丁（幂等，构建期执行）。

解决三个在国内部署时必然踩到的问题：

1. nltk punkt 缺失导致"万能兜底文案"
   `nltk.sent_tokenize` 需要 punkt 资源，容器里 nltk.org 常被安全代理拦截
   （典型报错：Security Violation: SSRF attempt to restricted IP）。
   LookupError 被上层捕获后会走 PROVIDER_FAILURE_FALLBACK，表现就是
   "I'm having trouble responding right now. Please try again."。
   处理：把 sent_tokenize 换成带正则兜底的包装版本，缺资源也能正常断句。

2. transformers 新版无 rope_theta 导致 Qwen3-TTS 加载崩溃
   transformers>=5.15 的 MimiConfig 没有 rope_theta 字段，
   qwen_tts/_transformers_compat.py 里 `base = config.rope_theta` 直接 AttributeError。
   处理：改为 getattr 取默认值。

3. 补丁不落地也不至于让构建失败：每项都单独 try/except，失败只告警。
"""

from __future__ import annotations

import os
import re
import sys

SOURCES_ROOT = "/usr/src/app/src"

SAFE_SENT_TOKENIZE = '''

def sent_tokenize(text: str, language: str = "english") -> list[str]:
    """nltk.sent_tokenize 的兜底包装。

    容器达不上 nltk.org 时缺 punkt 资源，nltk.sent_tokenize 会抛 LookupError，
    上层捕获后降级为固定兜底文案，表现为"助手一直说同一句话"。
    这里退化为按中英文句末标点正则切分，保证语音链路可用。
    """
    try:
        from nltk.tokenize import sent_tokenize as _nltk_sent_tokenize

        return _nltk_sent_tokenize(text, language=language)
    except (LookupError, OSError):
        parts = re.split(r"(?<=[.!?。！？；;\\n])\\s*", text)
        return [p for p in parts if p and p.strip()]
'''

NLTK_IMPORT_OLD = "from nltk import sent_tokenize\n"
NLTK_IMPORT_NEW = "from speech_to_speech.LLM.utils import sent_tokenize\n"

ROPE_OLD = re.compile(r"base\s*=\s*config\.rope_theta")
ROPE_NEW = 'base = getattr(config, "rope_theta", 10000.0)'


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def candidate_roots() -> list[str]:
    """补丁目标可能在源码目录（editable 安装）或 site-packages（普通安装）。"""
    roots = [SOURCES_ROOT]
    try:
        import speech_to_speech  # noqa: PLC0415

        pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(speech_to_speech.__file__)))
        if pkg_parent not in roots:
            roots.append(pkg_parent)
    except Exception:
        pass
    return roots


def patch_nltk_fallback() -> bool:
    done = False
    for root in candidate_roots():
        utils_path = os.path.join(root, "speech_to_speech", "LLM", "utils.py")
        content = _read(utils_path)
        if content is None:
            continue
        if "def sent_tokenize(" in content:
            print(f"[skip] 已存在兜底实现：{utils_path}")
        else:
            # 需要保证 re 已导入
            if not re.search(r"^import re$", content, flags=re.M):
                content = "import re\n" + content
            _write(utils_path, content.rstrip("\n") + "\n" + SAFE_SENT_TOKENIZE)
            print(f"[ok  ] 注入 sent_tokenize 兜底：{utils_path}")
            done = True

        for name in ("language_model.py", "base_openai_compatible_language_model.py"):
            target = os.path.join(root, "speech_to_speech", "LLM", name)
            data = _read(target)
            if data is None:
                continue
            if NLTK_IMPORT_OLD in data:
                _write(target, data.replace(NLTK_IMPORT_OLD, NLTK_IMPORT_NEW))
                print(f"[ok  ] 替换 nltk 导入：{target}")
                done = True
            elif NLTK_IMPORT_NEW in data:
                print(f"[skip] 已是补丁版：{target}")
    return done


def patch_qwen3_tts_compat() -> bool:
    """qwen_tts 在 site-packages 里，用 import 定位真实路径。"""
    try:
        import qwen_tts  # noqa: PLC0415

        base_dir = os.path.dirname(os.path.abspath(qwen_tts.__file__))
    except Exception as exc:
        print(f"[warn] 未找到 qwen_tts，跳过 rope_theta 补丁（{exc}）")
        return False

    target = os.path.join(base_dir, "_transformers_compat.py")
    content = _read(target)
    if content is None:
        print(f"[warn] 不存在 {target}，跳过")
        return False
    if ROPE_NEW in content:
        print(f"[skip] 已打过补丁：{target}")
        return True
    patched, n = ROPE_OLD.subn(ROPE_NEW, content)
    if n == 0:
        print(f"[warn] 未匹配到 config.rope_theta，请人工确认 {target}")
        return False
    _write(target, patched)
    print(f"[ok  ] 修补 rope_theta 兼容：{target}（{n} 处）")
    return True


def main() -> int:
    print("=== speech-to-speech 补丁 ===")
    ok = True
    for fn in (patch_nltk_fallback, patch_qwen3_tts_compat):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] 补丁执行异常（不阻断构建）：{exc}", file=sys.stderr)
            ok = False
    print("=== 补丁结束 ===")
    return 0 if ok else 0  # 补丁失败不阻断镜像构建


if __name__ == "__main__":
    sys.exit(main())
