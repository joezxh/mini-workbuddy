"""DXF 图纸提取器：图层名 + TEXT/MTEXT/ATTRIB 标注 → 结构化文本（spec §1）。

按图层聚合标注为分段（locator={"layer": 图层名}）；纯图形无标注时以
文件名+图元统计兜底，保证可检索。预览图经 ezdxf drawing add-on 渲染 modelspace。
"""
from __future__ import annotations

import io
from collections import defaultdict
from typing import Optional

from app.config import settings
from app.services.kb.media.base import MediaExtraction, MediaSegment


class DxfExtractor:
    """DXF → 图层分段文本；预览 PNG 由 ingest 侧按需调用。"""

    def __init__(self, db, override: Optional[dict] = None):  # noqa: ARG002 统一构造签名
        self.max_mb = settings.MEDIA_MAX_DXF_MB

    def _load(self, data: bytes, filename: str):
        import ezdxf

        if len(data) > self.max_mb * 1024 * 1024:
            raise ValueError(f"DXF 大小超过上限 {self.max_mb}MB")
        # DXF 是文本格式：ezdxf.read 需文本流（编码容错，兼容常见 GBK 图纸）
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("gbk", errors="replace")
        return ezdxf.read(io.StringIO(text))

    async def extract(self, data: bytes, filename: str) -> MediaExtraction:
        doc = self._load(data, filename)
        msp = doc.modelspace()
        by_layer: dict[str, list[str]] = defaultdict(list)
        for e in msp.query("TEXT MTEXT ATTRIB"):
            if e.dxftype() == "MTEXT":
                text = e.plain_text()
            else:
                text = e.dxf.get("text", "") or ""
            text = (text or "").strip()
            if text:
                by_layer[e.dxf.layer].append(text)
        segments = [
            MediaSegment(
                text=f"图层 {layer}：\n" + "\n".join(texts),
                locator={"layer": layer},
            )
            for layer, texts in sorted(by_layer.items())
        ]
        if not segments:  # 纯图形无标注：文件名+统计兜底，保证可检索
            segments = [MediaSegment(
                text=f"图纸 {filename}（无文字标注，图元 {len(msp)} 个）", locator={})]
        return MediaExtraction(kind="drawing", segments=segments, meta={
            "layer_count": len(by_layer), "entity_count": len(msp)})

    def preview_png_bytes(self, data: bytes) -> bytes:
        """modelspace 渲染 PNG（ezdxf drawing add-on + matplotlib Agg 后端）。"""
        import ezdxf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        doc = ezdxf.read(io.StringIO(data.decode("utf-8")))
        msp = doc.modelspace()
        fig = plt.figure()
        ax = fig.add_axes([0, 0, 1, 1])
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(
            msp, finalize=True)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return buf.getvalue()


def register() -> None:
    from app.services.kb.media.base import register_extractor

    register_extractor("drawing", DxfExtractor)


register()
