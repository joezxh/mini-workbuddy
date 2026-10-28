"""媒体上传校验测试。"""
import pytest

from app.services.kb.media.validation import validate_media_upload


class _KB:
    def __init__(self, enabled):
        self.multimodal_enabled = enabled


def test_non_media_always_passes():
    validate_media_upload(_KB(False), "a.pdf", 999 * 1024 * 1024)


def test_media_requires_multimodal_enabled():
    with pytest.raises(ValueError):
        validate_media_upload(_KB(False), "a.mp3", 1)
    validate_media_upload(_KB(True), "a.mp3", 1024)


def test_general_size_limit():
    with pytest.raises(ValueError):
        validate_media_upload(_KB(True), "a.mp4", 101 * 1024 * 1024)
    validate_media_upload(_KB(True), "a.mp4", 99 * 1024 * 1024)


def test_dxf_size_limit():
    with pytest.raises(ValueError):
        validate_media_upload(_KB(True), "a.dxf", 60 * 1024 * 1024)
    validate_media_upload(_KB(True), "a.dxf", 40 * 1024 * 1024)
