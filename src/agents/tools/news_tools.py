#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - 新闻分析工具

为CrewAI Agent提供Tavily新闻搜索和情绪分析能力
"""

from crewai.tools import tool
from typing import List, Dict
import json
from loguru import logger


@tool("搜索市场新闻热点")
def search_market_news(keywords: str = "A股 股市") -> str:
    """
    搜索市场新闻热点，识别当前题材和热点

    使用 Grok 模型进行实时搜索，获取最新的市场新闻和热点题材

    Args:
        keywords: 搜索关键词，默认"A股 股市"

    Returns:
        新闻摘要和热点题材(自然语言描述)
    """
    logger.info(f"📰 使用 Grok 实时搜索市场新闻: {keywords}")

    try:
        from src.tools.grok_client import get_grok_client

        client = get_grok_client()
        result = client.search_market_news(keywords)

        if result["success"]:
            return f"""
=== 市场新闻热点（Grok实时搜索） ===

{result["content"]}
"""
        else:
            # Grok 调用失败，返回提示
            logger.warning(f"Grok 市场新闻搜索失败: {result['content']}")
            return f"""
=== 市场新闻热点 ===

⚠️ Grok 实时搜索暂时不可用: {result["content"]}
建议：检查 GROK_API_KEY 配置

热点题材（默认）:
1. AI人工智能 (高热度)
2. 新能源汽车 (中热度)
3. 半导体芯片 (中热度)
"""

    except Exception as e:
        logger.error(f"市场新闻搜索异常: {e}")
        return f"""
=== 市场新闻热点 ===

⚠️ 市场新闻搜索异常: {str(e)}

热点题材（默认）:
1. AI人工智能 (高热度)
2. 新能源汽车 (中热度)
3. 半导体芯片 (中热度)
"""


@tool("搜索股票相关新闻")
def search_stock_news(stock_code: str, stock_name: str) -> str:
    """
    搜索指定股票的最新新闻，分析新闻情绪

    使用 Grok 模型进行实时搜索，获取最新的股票新闻和公告

    Args:
        stock_code: 股票代码
        stock_name: 股票名称

    Returns:
        新闻摘要和情绪评分(自然语言描述)
    """
    logger.info(f"📰 使用 Grok 实时搜索新闻: {stock_name}({stock_code})")

    try:
        from src.tools.grok_client import get_grok_client

        client = get_grok_client()
        result = client.search_stock_news(stock_code, stock_name)

        if result["success"]:
            return f"""
=== {stock_name}({stock_code}) 新闻分析（Grok实时搜索） ===

{result["content"]}
"""
        else:
            # Grok 调用失败，返回中性分数
            logger.warning(f"Grok 新闻搜索失败，返回中性分数: {stock_name}")
            return f"""
=== {stock_name}({stock_code}) 新闻分析 ===

【新闻面】评分: 60/100（搜索失败，中性分数）

⚠️ Grok 实时搜索暂时不可用: {result["content"]}
建议：检查 GROK_API_KEY 配置

新闻情绪：中性（默认）
"""

    except Exception as e:
        logger.error(f"新闻搜索异常: {stock_name}({stock_code}) - {e}")
        return f"""
=== {stock_name}({stock_code}) 新闻分析 ===

【新闻面】评分: 60/100（异常，中性分数）

⚠️ 新闻搜索异常: {str(e)}

新闻情绪：中性（默认）
"""


@tool("分析新闻情绪")
def analyze_news_sentiment(news_text: str) -> str:
    """
    分析新闻文本的情绪倾向
    
    Args:
        news_text: 新闻文本
    
    Returns:
        情绪评分和分析(自然语言描述)
    """
    from src.tools.tavily_api import get_tavily_client
    
    try:
        client = get_tavily_client()
        
        # 简单的情绪分析（基于关键词）
        positive_keywords = ['利好', '上涨', '增长', '突破', '创新高', '盈利', '业绩增长']
        negative_keywords = ['利空', '下跌', '亏损', '风险', '警告', '下滑', '业绩下降']
        
        positive_count = sum(1 for kw in positive_keywords if kw in news_text)
        negative_count = sum(1 for kw in negative_keywords if kw in news_text)
        
        # 计算情绪评分
        if positive_count > negative_count:
            sentiment_score = 60 + (positive_count - negative_count) * 10
            sentiment = "积极"
        elif negative_count > positive_count:
            sentiment_score = 40 - (negative_count - positive_count) * 10
            sentiment = "消极"
        else:
            sentiment_score = 50
            sentiment = "中性"
        
        sentiment_score = max(0, min(100, sentiment_score))  # 限制在0-100
        
        return f"""
=== 新闻情绪分析 ===

情绪倾向: {sentiment}
情绪评分: {sentiment_score}/100

积极关键词: {positive_count}个
消极关键词: {negative_count}个

建议: {'新闻偏向积极，可关注' if sentiment_score >= 60 else '新闻偏向消极，需谨慎' if sentiment_score <= 40 else '新闻中性，综合判断'}
"""
        
    except Exception as e:
        return f"分析新闻情绪失败: {str(e)}"

