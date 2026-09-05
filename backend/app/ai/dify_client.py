import httpx
from typing import Dict, Any, Optional
from loguru import logger

from app.config import settings


class DifyClient:
    """Dify API 客户端"""

    def __init__(self):
        self.base_url = settings.DIFY_API_URL
        self.api_key = settings.DIFY_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def run_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        运行 Dify 工作流
        
        Args:
            workflow_id: 工作流ID
            inputs: 输入参数
            user_id: 用户ID
            
        Returns:
            工作流执行结果
        """
        url = f"{self.base_url}/v1/workflows/run"
        
        payload = {
            "workflow_id": workflow_id,
            "inputs": inputs,
            "user": user_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Dify 工作流执行失败: {e}")
            raise

    async def chat_completion(
        self,
        app_id: str,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        对话型应用调用
        
        Args:
            app_id: 应用ID
            query: 用户问题
            user_id: 用户ID
            conversation_id: 会话ID（可选）
            
        Returns:
            对话响应
        """
        url = f"{self.base_url}/v1/chat-messages"
        
        payload = {
            "app_id": app_id,
            "query": query,
            "user": user_id,
            "response_mode": "streaming"
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Dify 对话调用失败: {e}")
            raise

    async def agent_chat(
        self,
        agent_id: str,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Agent 应用调用
        
        Args:
            agent_id: Agent ID
            query: 用户问题
            user_id: 用户ID
            conversation_id: 会话ID（可选）
            
        Returns:
            Agent 响应
        """
        url = f"{self.base_url}/v1/agent/chat"
        
        payload = {
            "agent_id": agent_id,
            "query": query,
            "user": user_id
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=120.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Dify Agent 调用失败: {e}")
            raise


# 创建全局实例
dify_client = DifyClient()

