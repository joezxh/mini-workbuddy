"""具体连接器类型（P3 Task 2~5）：钉钉 / 飞书 / 企业微信 等。"""
from app.connectors.types.dingtalk import DingtalkConnector
from app.connectors.types.feishu import FeishuConnector
from app.connectors.types.oauth2 import OAuth2ApiConnector
from app.connectors.types.wecom import WeComConnector

__all__ = [
    "OAuth2ApiConnector",
    "DingtalkConnector",
    "FeishuConnector",
    "WeComConnector",
]
