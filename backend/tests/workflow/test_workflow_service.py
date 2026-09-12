"""WorkflowService 单元测试"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.workflow.workflow_service import WorkflowService
from app.services.workflow.crypto import encrypt_api_key


class TestWorkflowService:
    """CRUD 服务层测试（使用 mock DB）"""

    def test_create_flow_encrypts_key(self):
        """创建流程时 API Key 应被加密"""
        svc = WorkflowService()
        db = MagicMock()
        data = {
            "flow_code": "test-flow",
            "flow_name": "Test",
            "platform_type": "dify",
            "flow_type": "Workflow",
            "base_url": "https://dify.test",
            "api_key": "sk-plain-key",
            "tenant_id": 1,
        }
        with patch.object(db, 'add') as mock_add:
            flow = svc.create_flow(db, data)
            assert flow.api_key_enc != "sk-plain-key"
            assert flow.flow_code == "test-flow"
            mock_add.assert_called_once()
