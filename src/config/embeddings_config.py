#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - Embeddings配置模块

使用硅基流动(SiliconFlow)的Embeddings服务
"""

import os
import requests
from typing import List, Optional
from dotenv import load_dotenv
from loguru import logger

# CrewAI自定义Embedding基类
from crewai.rag.embeddings.providers.custom.embedding_callable import CustomEmbeddingFunction

# 加载环境变量
load_dotenv()


class SiliconFlowEmbedder:
    """
    硅基流动Embeddings服务适配器
    
    兼容CrewAI的embedder接口，使用硅基流动API生成向量
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "BAAI/bge-m3",
        base_url: str = "https://api.siliconflow.cn/v1"
    ):
        """
        初始化Embedder
        
        Args:
            api_key: 硅基流动API Key，默认从环境变量读取
            model: Embedding模型名称，默认bge-m3
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            raise ValueError(
                "请配置SILICONFLOW_API_KEY环境变量! "
                "获取方式: https://cloud.siliconflow.cn/account/ak"
            )
        
        self.model = model
        self.base_url = base_url
        self.endpoint = f"{base_url}/embeddings"
        
        logger.info(f"✅ SiliconFlow Embedder初始化: model={model}")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文档向量（CrewAI Memory调用此方法）
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        embeddings = []
        for text in texts:
            embedding = self._get_embedding(text)
            embeddings.append(embedding)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """
        生成查询向量（CrewAI Memory调用此方法）
        
        Args:
            text: 查询文本
            
        Returns:
            向量
        """
        return self._get_embedding(text)
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        调用硅基流动API生成向量
        
        Args:
            text: 输入文本
            
        Returns:
            向量
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }
        
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            embedding = data["data"][0]["embedding"]
            
            logger.debug(f"✅ Embedding生成成功: {len(embedding)}维向量")
            return embedding
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Embedding API调用失败: {e}")
            raise


class SiliconFlowEmbeddingFunction(CustomEmbeddingFunction):
    """
    硅基流动Embedding函数（兼容CrewAI）

    继承CustomEmbeddingFunction以通过Pydantic验证
    支持自动截断超长文本（硅基流动限制512 tokens）
    """

    def __init__(self):
        """无参构造函数（CrewAI要求）"""
        self.api_key = os.getenv("SILICONFLOW_API_KEY")
        self.model = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
        self.endpoint = "https://api.siliconflow.cn/v1/embeddings"
        self.max_tokens = 500  # 保守设置为500（硅基流动限制512）

    def _truncate_text(self, text: str) -> str:
        """
        截断文本到最大token限制

        简单策略：按字符数截断（中文约1字=1token，英文约4字符=1token）
        """
        # 粗略估算：中英文混合，取平均值 2字符≈1token
        max_chars = self.max_tokens * 2
        if len(text) > max_chars:
            truncated = text[:max_chars]
            logger.debug(f"文本被截断: {len(text)} -> {len(truncated)} 字符")
            return truncated
        return text

    def __call__(self, input: List[str]) -> List[List[float]]:
        """CrewAI调用此方法"""
        embeddings = []
        for text in input:
            # 截断超长文本
            truncated_text = self._truncate_text(text)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "input": truncated_text,
                "encoding_format": "float"
            }
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                embedding = data["data"][0]["embedding"]
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Embedding API调用失败: {e}")
                # 返回零向量避免崩溃
                embeddings.append([0.0] * 1024)
        return embeddings





def get_siliconflow_embedder_config() -> dict:
    """
    获取硅基流动Embedder配置（用于CrewAI）

    Returns:
        embedder配置字典，使用自定义Embedding函数（支持文本截断）
    """
    api_key = os.getenv("SILICONFLOW_API_KEY")

    if not api_key:
        logger.warning("⚠️ 未配置SILICONFLOW_API_KEY，Memory功能将不可用")
        return None

    # 使用custom provider + 自定义Embedding函数（支持文本截断）
    return {
        "provider": "custom",
        "config": {
            "embedding_callable": SiliconFlowEmbeddingFunction
        }
    }


def get_embedder_instance() -> Optional[SiliconFlowEmbedder]:
    """
    获取Embedder实例
    
    Returns:
        SiliconFlowEmbedder实例，如果未配置则返回None
    """
    try:
        return SiliconFlowEmbedder()
    except ValueError:
        logger.warning("⚠️ 未配置Embeddings，Memory功能禁用")
        return None

