#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - 社区情绪分析工具

为CrewAI Agent提供社区评论获取和情绪分析能力
支持雪球、东方财富股吧、淘股吧三大平台
"""

from crewai.tools import tool
from typing import Dict
import asyncio
import time
import os
import threading
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ✅ 全局锁：确保同一时间只有一个社区情绪请求在执行（避免批量分析时并发导致账号被封）
_community_request_lock = threading.Lock()

# ✅ 社区评论缓存（从环境变量读取，默认1小时）
_community_comments_cache: Dict[str, Dict] = {}
_cache_ttl = int(os.getenv('COMMUNITY_CACHE_TTL', '3600'))  # 默认1小时 = 3600秒
_request_delay = float(os.getenv('COMMUNITY_REQUEST_DELAY', '1.5'))  # 默认1.5秒（释放锁前的延迟）


@tool("获取股票社区评论")
def get_stock_community_comments(stock_code: str, max_items: int = 5) -> str:
    """
    获取股票在社区平台的讨论评论（雪球+东财股吧+淘股吧）

    使用 Grok 模型进行实时搜索，获取最新的社区讨论和散户情绪

    Args:
        stock_code: 股票代码（6位数字，如"000001"）
        max_items: 每个平台的最大评论数，默认5条（减少上下文长度）

    Returns:
        社区评论摘要（包含散户情绪、讨论热度、关键观点）
    """
    logger.info(f"📊 使用 Grok 实时搜索社区情绪: {stock_code}")

    try:
        from src.tools.grok_client import get_grok_client
        from src.tools.zhitu_api import ZhituAPI

        # 获取股票名称
        stock_name = stock_code
        try:
            zhitu = ZhituAPI()
            stock_info = zhitu.get_real_time_broker(stock_code)
            if stock_info and 'name' in stock_info:
                stock_name = stock_info['name']
        except Exception:
            pass

        client = get_grok_client()
        result = client.search_community_sentiment(stock_code, stock_name)

        if result["success"]:
            return f"""
=== {stock_name}({stock_code}) 社区评论分析（Grok实时搜索） ===

{result["content"]}
"""
        else:
            # Grok 调用失败，返回中性分数
            logger.warning(f"Grok 社区情绪搜索失败，返回中性分数: {stock_code}")
            return f"""
=== {stock_code} 社区评论分析 ===

【社区情绪】评分: 60/100（搜索失败，中性分数）

⚠️ Grok 实时搜索暂时不可用: {result["content"]}
建议：检查 GROK_API_KEY 配置

散户情绪：中性（默认）
讨论热度：中等（默认）
"""

    except Exception as e:
        logger.error(f"社区情绪搜索异常: {stock_code} - {e}")
        return f"""
=== {stock_code} 社区评论分析 ===

【社区情绪】评分: 60/100（异常，中性分数）

⚠️ 社区情绪搜索异常: {str(e)}

散户情绪：中性（默认）
讨论热度：中等（默认）
"""


@tool("获取雪球评论")
def get_xueqiu_comments(stock_code: str, max_items: int = 5) -> str:
    """
    获取股票在雪球的讨论评论

    Args:
        stock_code: 股票代码（6位数字，如"000001"）
        max_items: 最大评论数，默认5条（减少上下文长度）
        
    Returns:
        雪球评论数据
    """
    try:
        from src.tools.stock_mcp_community import get_community_client
        
        client = get_community_client()
        comments = asyncio.run(client.get_xueqiu_comments(
            symbol=stock_code,
            max_items=max_items
        ))
        
        if not comments or "失败" in comments:
            return f"⚠️ 无法获取{stock_code}的雪球评论: {comments}"
        
        return f"=== {stock_code} 雪球评论 ===\n\n{comments}"
        
    except Exception as e:
        error_msg = f"获取雪球评论失败: {str(e)}"
        logger.error(error_msg)
        return f"⚠️ {error_msg}"


@tool("获取东财股吧评论")
def get_eastmoney_comments(stock_code: str, max_items: int = 5) -> str:
    """
    获取股票在东方财富股吧的讨论评论

    Args:
        stock_code: 股票代码（6位数字，如"000001"）
        max_items: 最大评论数，默认5条（减少上下文长度）
        
    Returns:
        东财股吧评论数据
    """
    try:
        from src.tools.stock_mcp_community import get_community_client
        
        client = get_community_client()
        comments = asyncio.run(client.get_eastmoney_comments(
            symbol=stock_code,
            max_items=max_items
        ))
        
        if not comments or "失败" in comments:
            return f"⚠️ 无法获取{stock_code}的东财股吧评论: {comments}"
        
        return f"=== {stock_code} 东财股吧评论 ===\n\n{comments}"
        
    except Exception as e:
        error_msg = f"获取东财股吧评论失败: {str(e)}"
        logger.error(error_msg)
        return f"⚠️ {error_msg}"


@tool("获取淘股吧评论")
def get_taoguba_comments(stock_code: str, max_items: int = 5) -> str:
    """
    获取股票在淘股吧的讨论评论

    Args:
        stock_code: 股票代码（6位数字，如"000001"）
        max_items: 最大评论数，默认5条（减少上下文长度）
        
    Returns:
        淘股吧评论数据
    """
    try:
        from src.tools.stock_mcp_community import get_community_client
        
        client = get_community_client()
        comments = asyncio.run(client.get_taoguba_comments(
            symbol=stock_code,
            max_items=max_items
        ))
        
        if not comments or "失败" in comments:
            return f"⚠️ 无法获取{stock_code}的淘股吧评论: {comments}"
        
        return f"=== {stock_code} 淘股吧评论 ===\n\n{comments}"
        
    except Exception as e:
        error_msg = f"获取淘股吧评论失败: {str(e)}"
        logger.error(error_msg)
        return f"⚠️ {error_msg}"

