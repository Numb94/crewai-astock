#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新闻工具 - CrewAI Agent 工具集

使用 Grok 实时搜索提供新闻和热点分析能力
"""

from typing import Optional
from crewai.tools import tool
from loguru import logger


@tool("获取最新新闻热点")
def get_latest_news_tool(limit: int = 30) -> str:
    """
    获取最新市场新闻热点，快速了解当前热点

    使用 Grok 模型进行实时搜索

    Args:
        limit: 返回数量限制（默认30条，实际由Grok控制）

    Returns:
        新闻列表的文本摘要

    使用场景：
    - 市场情报官：了解当前市场热点和舆论焦点
    - 多维分析师：分析新闻对股票的影响
    """
    logger.info(f"📰 使用 Grok 实时搜索最新新闻热点")

    try:
        from src.tools.grok_client import get_grok_client

        client = get_grok_client()
        result = client.search_market_news("A股 股市 最新")

        if result["success"]:
            return f"""
=== 最新新闻热点（Grok实时搜索） ===

{result["content"]}
"""
        else:
            logger.warning(f"Grok 新闻搜索失败: {result['content']}")
            return f"""
=== 最新新闻热点 ===

⚠️ Grok 实时搜索暂时不可用: {result["content"]}
建议：检查 GROK_API_KEY 配置
"""

    except Exception as e:
        logger.error(f"❌ 获取最新新闻失败: {e}")
        return f"❌ 获取最新新闻失败: {str(e)}"


@tool("搜索股票相关新闻")
def search_stock_news_tool(stock_code: str = None, stock_name: str = None, days: int = 7) -> str:
    """
    按股票代码/名称搜索新闻

    使用 Grok 模型进行实时搜索

    Args:
        stock_code: 股票代码（如 "000001"）
        stock_name: 股票名称（如 "平安银行"）
        days: 搜索天数（默认7天）

    Returns:
        股票相关新闻的文本摘要

    使用场景：
    - 智能选股师：分析候选股票的新闻热度
    - 多维分析师：评估股票的舆论环境
    - 风险管理官：识别负面新闻风险
    """
    if not stock_code and not stock_name:
        return "❌ 请提供股票代码或股票名称"

    logger.info(f"📰 使用 Grok 实时搜索股票新闻: {stock_name or stock_code}")

    try:
        from src.tools.grok_client import get_grok_client

        client = get_grok_client()

        # 确定搜索参数
        code = stock_code or ""
        name = stock_name or stock_code

        result = client.search_stock_news(code, name)

        if result["success"]:
            return f"""
=== {name}({code}) 相关新闻（Grok实时搜索） ===

{result["content"]}
"""
        else:
            logger.warning(f"Grok 股票新闻搜索失败: {result['content']}")
            return f"""
=== {name}({code}) 相关新闻 ===

【新闻面】评分: 60/100（搜索失败，中性分数）

⚠️ Grok 实时搜索暂时不可用: {result["content"]}

新闻情绪：中性（默认）
"""

    except Exception as e:
        logger.error(f"❌ 搜索股票新闻失败: {e}")
        return f"❌ 搜索股票新闻失败: {str(e)}"


@tool("分析话题热度趋势")
def analyze_topic_trend_tool(topic: str, days: int = 7) -> str:
    """
    分析话题的热度趋势变化

    使用 Grok 模型进行实时分析

    Args:
        topic: 话题关键词（如 "人工智能"、"新能源"）
        days: 分析天数（默认7天）

    Returns:
        话题热度趋势分析报告

    使用场景：
    - 市场情报官：追踪行业热点和题材炒作
    - 智能选股师：识别热门题材和概念股
    """
    logger.info(f"📊 使用 Grok 分析话题趋势: {topic}")

    try:
        from src.tools.grok_client import get_grok_client

        client = get_grok_client()
        result = client.analyze_topic_trend(topic, days)

        if result["success"]:
            return result["content"]
        else:
            logger.warning(f"Grok 话题趋势分析失败: {result['content']}")
            return f"""
=== {topic} 热度趋势分析 ===

⚠️ Grok 分析暂时不可用: {result["content"]}

📈 默认判断:
- 趋势：中性
- 热度：中等
"""

    except Exception as e:
        logger.error(f"❌ 分析话题趋势失败: {e}")
        return f"❌ 分析话题趋势失败: {str(e)}"


@tool("获取热门关注词")
def get_trending_topics_tool(top_n: int = 10) -> str:
    """
    获取当前热门关注词和话题

    使用 Grok 模型进行实时搜索

    Args:
        top_n: 返回TOP N关注词（默认10）

    Returns:
        热门关注词列表

    使用场景：
    - 市场情报官：发现市场关注焦点
    - 智能选股师：识别热门题材
    """
    logger.info(f"🔥 使用 Grok 获取热门关注词 TOP {top_n}")

    try:
        from src.tools.grok_client import get_grok_client

        client = get_grok_client()
        result = client.get_trending_topics(top_n)

        if result["success"]:
            return f"""
=== 热门关注词（Grok实时搜索） ===

{result["content"]}
"""
        else:
            logger.warning(f"Grok 热门话题搜索失败: {result['content']}")
            return f"""
=== 热门关注词 ===

⚠️ Grok 搜索暂时不可用: {result["content"]}

🔥 默认热门话题:
1. AI人工智能 - 高热度
2. 新能源汽车 - 中热度
3. 半导体芯片 - 中热度
4. 医药生物 - 中热度
5. 机器人 - 高热度
"""

    except Exception as e:
        logger.error(f"❌ 获取热门关注词失败: {e}")
        return f"❌ 获取热门关注词失败: {str(e)}"

