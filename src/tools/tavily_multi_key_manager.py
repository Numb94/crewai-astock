#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - Tavily多Key轮询管理器

支持配置多个Tavily API Key，自动轮询使用，突破单Key 1000次/月限制

作者: AI Assistant
日期: 2025-11-18
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

try:
    from tavily import TavilyClient
except ImportError:
    logger.warning("tavily-python 未安装,请运行: pip install tavily-python")
    TavilyClient = None

load_dotenv()


class TavilyMultiKeyManager:
    """Tavily多Key轮询管理器
    
    功能：
    1. 支持配置多个API Key（最多10个）
    2. 自动轮询使用，均衡负载
    3. 自动跳过失败的Key
    4. 统计每个Key的使用次数
    """
    
    def __init__(self, api_keys: List[str] = None):
        """初始化多Key管理器
        
        Args:
            api_keys: API Key列表，默认从环境变量读取
        """
        # 从环境变量读取多个Key
        if api_keys is None:
            api_keys = []
            # 支持TAVILY_API_KEY_1, TAVILY_API_KEY_2, ..., TAVILY_API_KEY_10
            for i in range(1, 11):
                key = os.getenv(f"TAVILY_API_KEY_{i}")
                if key and key != "tvly-your_tavily_api_key_here":
                    api_keys.append(key)
            
            # 如果没有配置多个Key，尝试读取单个Key
            if not api_keys:
                single_key = os.getenv("TAVILY_API_KEY")
                if single_key and single_key != "tvly-your_tavily_api_key_here":
                    api_keys.append(single_key)
        
        if not api_keys:
            raise ValueError(
                "未配置Tavily API Key！\n"
                "请在.env文件中配置：\n"
                "TAVILY_API_KEY_1=tvly-xxx\n"
                "TAVILY_API_KEY_2=tvly-xxx\n"
                "...\n"
                "TAVILY_API_KEY_10=tvly-xxx"
            )
        
        self.api_keys = api_keys
        self.current_index = 0  # 当前使用的Key索引
        self.key_stats = {key: {"count": 0, "errors": 0} for key in api_keys}  # 统计信息
        
        logger.info(f"✅ Tavily多Key管理器初始化成功，共{len(api_keys)}个Key")
    
    def get_client(self) -> TavilyClient:
        """获取Tavily客户端（自动轮询）
        
        Returns:
            TavilyClient实例
        """
        if TavilyClient is None:
            raise ImportError("请安装 tavily-python: pip install tavily-python")
        
        # 轮询获取下一个Key
        api_key = self.api_keys[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        
        # 更新统计
        self.key_stats[api_key]["count"] += 1
        
        logger.debug(f"使用Tavily Key #{self.current_index}: {api_key[:10]}...")
        
        return TavilyClient(api_key=api_key)
    
    def search_news(self, query: str, max_results: int = 5, 
                    search_depth: str = "basic", retry: int = 3) -> List[Dict[str, Any]]:
        """搜索新闻（自动重试）
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            search_depth: 搜索深度 (basic/advanced)
            retry: 重试次数
        
        Returns:
            新闻列表
        """
        for attempt in range(retry):
            try:
                client = self.get_client()
                response = client.search(
                    query=query,
                    max_results=max_results,
                    search_depth=search_depth
                )
                
                # 提取结果
                results = []
                for item in response.get("results", []):
                    # ✅ 修复：Tavily返回的published_date可能是空字符串，需要转换为None
                    published_date = item.get("published_date", "")
                    if not published_date or published_date.strip() == "":
                        published_date = None

                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "published_date": published_date,  # ✅ 空字符串转为None
                        "score": item.get("score", 0.0)
                    })

                logger.info(f"Tavily搜索成功: {query}, 返回{len(results)}条结果")
                return results
                
            except Exception as e:
                # 记录错误
                current_key = self.api_keys[(self.current_index - 1) % len(self.api_keys)]
                self.key_stats[current_key]["errors"] += 1
                
                logger.warning(f"Tavily搜索失败 (尝试{attempt + 1}/{retry}): {e}")
                
                if attempt == retry - 1:
                    logger.error(f"Tavily搜索失败，已重试{retry}次")
                    return []
        
        return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取使用统计
        
        Returns:
            统计信息
        """
        total_count = sum(stats["count"] for stats in self.key_stats.values())
        total_errors = sum(stats["errors"] for stats in self.key_stats.values())
        
        return {
            "total_keys": len(self.api_keys),
            "total_requests": total_count,
            "total_errors": total_errors,
            "key_details": self.key_stats
        }


# 全局单例
_tavily_manager = None


def get_tavily_manager() -> TavilyMultiKeyManager:
    """获取Tavily多Key管理器（单例）
    
    Returns:
        TavilyMultiKeyManager实例
    """
    global _tavily_manager
    if _tavily_manager is None:
        _tavily_manager = TavilyMultiKeyManager()
    return _tavily_manager

