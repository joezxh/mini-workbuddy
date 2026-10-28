"""DXF 提取器测试（ezdxf 编程生成 fixture）。"""
import asyncio

import ezdxf
import pytest


def _make_dxf_bytes() -> bytes:
    """两层图纸：LAYER-A 两个 TEXT、LAYER-B 一个 MTEXT。"""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("LAYER-A")
    doc.layers.add("LAYER-B")
    msp.add_text("第一行标注", dxfattribs={"layer": "LAYER-A"})
    msp.add_text("第二行标注", dxfattribs={"layer": "LAYER-A"})
    msp.add_mtext("多行\n说明文字", dxfattribs={"layer": "LAYER-B"})
    msp.add_line((0, 0), (10, 10), dxfattribs={"layer": "LAYER-A"})  # 无文字图元
    import io
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_dxf_segments_by_layer():
    from app.services.kb.media.dxf_extractor import DxfExtractor

    result = asyncio.run(DxfExtractor(None).extract(_make_dxf_bytes(), "part.dxf"))
    assert result.kind == "drawing"
    layers = [s.locator["layer"] for s in result.segments]
    assert layers == ["LAYER-A", "LAYER-B"]  # 按图层名排序
    text_a = result.segments[0].text
    assert "第一行标注" in text_a and "第二行标注" in text_a
    assert "多行" in result.segments[1].text and "说明文字" in result.segments[1].text
    assert result.meta["layer_count"] == 2


def test_dxf_no_text_falls_back_to_stats():
    from app.services.kb.media.dxf_extractor import DxfExtractor

    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (1, 1))
    import io
    buf = io.StringIO()
    doc.write(buf)
    result = asyncio.run(DxfExtractor(None).extract(
        buf.getvalue().encode("utf-8"), "empty.dxf"))
    assert len(result.segments) == 1
    assert result.segments[0].locator == {}
    assert "无文字标注" in result.segments[0].text


def test_dxf_over_limit_raises():
    from app.services.kb.media.dxf_extractor import DxfExtractor

    ext = DxfExtractor(None)
    ext.max_mb = 0  # 强制超限
    with pytest.raises(ValueError):
        asyncio.run(ext.extract(_make_dxf_bytes(), "big.dxf"))


def test_dxf_preview_png():
    from app.services.kb.media.dxf_extractor import DxfExtractor

    png = DxfExtractor(None).preview_png_bytes(_make_dxf_bytes())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
