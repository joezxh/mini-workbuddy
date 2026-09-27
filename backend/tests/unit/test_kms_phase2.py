"""知识库统一化 Phase 2 回归（spec §10.2 新模型 / §10.3 摄取管线 / §9 OKF）。"""


def test_kb_document_model_fields():
    from app.models.kb.kb_document import KbDocument

    assert KbDocument.__tablename__ == "kb_document"
    for col in ("knowledge_id", "collection", "name", "source_type",
                "file_type", "file_size", "status", "segment_count", "error_detail"):
        assert col in KbDocument.__table__.c
    assert KbDocument.__table__.c["status"].server_default is not None


def test_kb_segment_asset_model_fields():
    from app.models.kb.kb_segment_asset import KbSegmentAsset

    assert KbSegmentAsset.__tablename__ == "kb_segment_asset"
    for col in ("segment_id", "file_path", "mime_type", "size"):
        assert col in KbSegmentAsset.__table__.c


def test_external_kb_endpoint_model_fields():
    from app.models.connectors.external_kb_endpoint import ExternalKbEndpoint

    assert ExternalKbEndpoint.__tablename__ == "kms_external_kb_endpoint"
    for col in ("knowledge_id", "endpoint_url", "auth_key", "index_name", "status"):
        assert col in ExternalKbEndpoint.__table__.c
