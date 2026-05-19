#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock V2.0 - Tavily 新闻 API 工具封装

提供新闻搜索、热点事件提取、情绪分析功能

作者: AI Architect
版本: v2.0.5-db-complete
日期: 2025-10-21
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv
from crewai.tools import BaseTool
from pydantic import Field

try:
    from tavily import TavilyClient
except ImportError:
    logger.warning("tavily-python 未安装,请运行: pip install tavily-python")
    TavilyClient = None

load_dotenv()


# ========================================
# Tavily API 客户端封装
# ========================================

class TavilyAPIClient:
    """Tavily API 客户端

    提供新闻搜索、热点提取、情绪分析功能
    """

    def __init__(self, api_key: str = None):
        """初始化 Tavily 客户端

        Args:
            api_key: Tavily API Key (默认从环境变量读取)
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

        if not self.api_key:
            raise ValueError("缺少 Tavily API Key,请设置环境变量 TAVILY_API_KEY")

        if TavilyClient is None:
            raise ImportError("请安装 tavily-python: pip install tavily-python")

        self.client = TavilyClient(api_key=self.api_key)

    def search_news(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: List[str] = None,
        exclude_domains: List[str] = None
    ) -> List[Dict[str, Any]]:
        """搜索新闻

        Args:
            query: 搜索关键词
            max_results: 最大结果数 (默认 5)
            search_depth: 搜索深度 ("basic" 或 "advanced")
            include_domains: 包含的域名列表
            exclude_domains: 排除的域名列表

        Returns:
            [
                {
                    "title": "新闻标题",
                    "url": "新闻链接",
                    "content": "新闻内容",
                    "published_date": "发布日期",
                    "score": 0.95  # 相关性评分
                },
                ...
            ]
        """
        try:
            # ✅ 优先使用多Key管理器
            if hasattr(self, '_multi_key_manager'):
                return self._multi_key_manager.search_news(
                    query=query,
                    max_results=max_results,
                    search_depth=search_depth
                )

            # 降级：使用单Key模式
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_domains=include_domains,
                exclude_domains=exclude_domains
            )

            # 提取结果
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "published_date": item.get("published_date", ""),
                    "score": item.get("score", 0.0)
                })

            logger.info(f"Tavily 搜索成功: {query}, 返回 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"Tavily 搜索失败: {str(e)}")
            return []

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """分析文本情绪

        Args:
            text: 待分析文本

        Returns:
            {
                "sentiment": "positive",  # positive/negative/neutral
                "score": 0.85,  # 情绪强度 0-1
                "keywords": ["AI", "突破", "上涨"]  # 关键词
            }
        """
        # 简化版情绪分析 (基于关键词匹配)
        # TODO: 生产环境可接入专业情绪分析 API

        positive_keywords = [
            "利好", "上涨", "突破", "创新", "增长", "盈利", "业绩",
            "订单", "合作", "中标", "政策", "扶持", "补贴"
        ]

        negative_keywords = [
            "利空", "下跌", "暴跌", "亏损", "风险", "调查", "处罚",
            "诉讼", "违规", "裁员", "ST", "退市", "破产"
        ]

        # 统计关键词出现次数
        positive_count = sum(1 for kw in positive_keywords if kw in text)
        negative_count = sum(1 for kw in negative_keywords if kw in text)

        # 判断情绪
        if positive_count > negative_count:
            sentiment = "positive"
            score = min(0.5 + (positive_count - negative_count) * 0.1, 1.0)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = min(0.5 + (negative_count - positive_count) * 0.1, 1.0)
        else:
            sentiment = "neutral"
            score = 0.5

        # 提取关键词
        keywords = []
        for kw in positive_keywords + negative_keywords:
            if kw in text:
                keywords.append(kw)

        return {
            "sentiment": sentiment,
            "score": score,
            "keywords": keywords[:5]  # 最多返回 5 个关键词
        }


# 全局客户端实例
_tavily_client = None


def get_tavily_client() -> TavilyAPIClient:
    """获取全局 Tavily API 客户端实例

    优先使用多Key管理器，如果未配置则使用单Key模式
    """
    global _tavily_client
    if _tavily_client is None:
        # ✅ 优先尝试使用多Key管理器
        try:
            from src.tools.tavily_multi_key_manager import get_tavily_manager
            manager = get_tavily_manager()
            logger.info(f"✅ 使用Tavily多Key管理器，共{len(manager.api_keys)}个Key")
            # 使用第一个Key初始化客户端（实际搜索时会轮询）
            _tavily_client = TavilyAPIClient(api_key=manager.api_keys[0])
            _tavily_client._multi_key_manager = manager  # 保存管理器引用
        except Exception as e:
            logger.warning(f"多Key管理器初始化失败，使用单Key模式: {e}")
            _tavily_client = TavilyAPIClient()
    return _tavily_client


# ========================================
# 1. NewsSearchTool - 新闻搜索工具
# ========================================

class NewsSearchTool(BaseTool):
    """搜索最新新闻

    用于 CMO Agent 和新闻监控员 Agent 获取实时新闻
    """

    name: str = "news_search"
    description: str = "搜索股市相关新闻,用于捕捉重大事件和市场情绪"

    query: str = Field(description="搜索关键词 (如 '人工智能政策', '半导体行业')")
    max_results: int = Field(default=5, description="最大结果数")

    def _run(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """执行新闻搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数

        Returns:
            [
                {
                    "title": "国务院发布AI产业扶持政策",
                    "url": "https://...",
                    "content": "...",
                    "published_date": "2025-10-21",
                    "score": 0.95,
                    "sentiment": "positive"  # 新增情绪字段
                },
                ...
            ]
        """
        client = get_tavily_client()

        # 搜索新闻
        results = client.search_news(
            query=query,
            max_results=max_results,
            search_depth="basic"
        )

        # 为每条新闻添加情绪分析
        for result in results:
            content = result.get("content", "") + " " + result.get("title", "")
            sentiment_analysis = client.analyze_sentiment(content)
            result["sentiment"] = sentiment_analysis["sentiment"]
            result["sentiment_score"] = sentiment_analysis["score"]
            result["keywords"] = sentiment_analysis["keywords"]

        return results


# ========================================
# 2. HotTopicExtractorTool - 热点事件提取工具
# ========================================

class HotTopicExtractorTool(BaseTool):
    """提取当前热点题材

    用于 CMO Agent 识别市场热点题材
    """

    name: str = "hot_topic_extractor"
    description: str = "提取当前股市热点题材,用于题材轮动策略"

    def _run(self) -> List[Dict[str, Any]]:
        """提取热点题材

        Returns:
            [
                {
                    "topic": "人工智能",
                    "news_count": 15,  # 相关新闻数
                    "sentiment": "positive",
                    "keywords": ["AI", "ChatGPT", "算力"]
                },
                {
                    "topic": "半导体",
                    "news_count": 10,
                    "sentiment": "positive",
                    "keywords": ["芯片", "国产替代", "光刻机"]
                },
                ...
            ]
        """
        client = get_tavily_client()

        # 🔴 使用动态识别的热点题材
        # 调用get_hot_topics()获取动态热点列表
        try:
            logger.info("🔍 使用动态热点识别...")
            hot_topics_data = get_hot_topics()

            # 提取热点名称
            if hot_topics_data and len(hot_topics_data) > 0:
                # get_hot_topics()返回的是包含topic字段的字典列表
                hot_topics = [item['topic'] for item in hot_topics_data if 'topic' in item]
                logger.success(f"✅ 使用动态热点: {', '.join(hot_topics)}")
            else:
                # 降级方案
                logger.warning("⚠️ 动态热点为空，使用默认列表")
                hot_topics = [
                    "人工智能",
                    "半导体",
                    "新能源汽车",
                    "锂电池",
                    "光伏",
                    "军工",
                    "医药",
                    "消费电子",
                    "5G",
                    "数字经济"
                ]
        except Exception as e:
            logger.error(f"❌ 获取动态热点失败: {e}，使用默认列表")
            hot_topics = [
                "人工智能",
                "半导体",
                "新能源汽车",
                "锂电池",
                "光伏",
                "军工",
                "医药",
                "消费电子",
                "5G",
                "数字经济"
            ]

        topic_results = []

        for topic in hot_topics:
            # 搜索该题材的新闻
            news = client.search_news(
                query=f"{topic} 股票",
                max_results=3,
                search_depth="basic"
            )

            if not news:
                continue

            # 分析整体情绪
            all_content = " ".join([n.get("content", "") for n in news])
            sentiment_analysis = client.analyze_sentiment(all_content)

            topic_results.append({
                "topic": topic,
                "news_count": len(news),
                "sentiment": sentiment_analysis["sentiment"],
                "sentiment_score": sentiment_analysis["score"],
                "keywords": sentiment_analysis["keywords"],
                "sample_news": news[0]["title"] if news else ""
            })

        # 按新闻数排序
        topic_results.sort(key=lambda x: x["news_count"], reverse=True)

        logger.info(f"提取热点题材成功,共 {len(topic_results)} 个题材")
        return topic_results[:5]  # 返回 Top 5 热点


# ========================================
# 3. BreakingNewsTool - 重大突发新闻工具
# ========================================

class BreakingNewsTool(BaseTool):
    """监控重大突发新闻

    用于触发紧急决策会议
    """

    name: str = "breaking_news"
    description: str = "监控重大突发新闻,用于触发紧急会议"

    def _run(self) -> List[Dict[str, Any]]:
        """获取重大突发新闻

        Returns:
            [
                {
                    "title": "央行宣布降准0.5个百分点",
                    "url": "https://...",
                    "published_date": "2025-10-21 10:00:00",
                    "importance": "high",  # high/medium/low
                    "sentiment": "positive",
                    "impact_sectors": ["银行", "地产", "基建"]
                },
                ...
            ]
        """
        client = get_tavily_client()

        # 重大新闻关键词
        breaking_keywords = [
            "央行 降准",
            "央行 降息",
            "国务院 政策",
            "证监会 新规",
            "美联储",
            "地缘政治"
        ]

        breaking_news = []

        for keyword in breaking_keywords:
            news = client.search_news(
                query=keyword,
                max_results=2,
                search_depth="basic"
            )

            for item in news:
                # 分析重要性 (基于评分)
                score = item.get("score", 0)
                if score > 0.8:
                    importance = "high"
                elif score > 0.6:
                    importance = "medium"
                else:
                    importance = "low"

                # 情绪分析
                content = item.get("content", "") + " " + item.get("title", "")
                sentiment_analysis = client.analyze_sentiment(content)

                breaking_news.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "published_date": item.get("published_date", ""),
                    "importance": importance,
                    "sentiment": sentiment_analysis["sentiment"],
                    "sentiment_score": sentiment_analysis["score"],
                    "keywords": sentiment_analysis["keywords"],
                    "impact_sectors": []  # TODO: 可通过 NLP 提取影响板块
                })

        # 按重要性和分数排序
        breaking_news.sort(
            key=lambda x: (
                1 if x["importance"] == "high" else 0,
                x.get("sentiment_score", 0)
            ),
            reverse=True
        )

        logger.info(f"获取重大新闻成功,共 {len(breaking_news)} 条")
        return breaking_news[:5]  # 返回 Top 5


# ========================================
# 便捷函数
# ========================================

def search_stock_news(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """便捷函数: 搜索股票相关新闻

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        新闻列表
    """
    client = get_tavily_client()
    return client.search_news(query=query, max_results=max_results)


def get_hot_topics() -> List[Dict[str, Any]]:
    """便捷函数: 获取当前热点题材（动态识别版本）

    通过搜索最新新闻，动态提取高频关键词作为热点题材

    Returns:
        热点题材列表
    """
    client = get_tavily_client()

    try:
        # 🔴 第1步：搜索最新A股新闻
        logger.info("🔍 搜索最新A股新闻，动态识别热点...")
        latest_news = client.search_news(
            query="A股 股市 热点",
            max_results=20,  # 增加新闻数量，提高准确性
            search_depth="basic"
        )

        if not latest_news:
            logger.warning("⚠️ 未找到最新新闻，使用默认热点列表")
            # 降级方案：使用默认热点列表
            hot_topics = [
                "人工智能",
                "半导体",
                "新能源汽车",
                "锂电池",
                "光伏",
                "军工",
                "医药",
                "消费电子",
                "5G",
                "数字经济"
            ]
        else:
            # 🔴 第2步：提取高频关键词
            from collections import Counter
            keyword_counter = Counter()

            for news in latest_news:
                # 提取新闻的关键词（Tavily已提供）
                if 'keywords' in news and news['keywords']:
                    for keyword in news['keywords']:
                        # 过滤掉通用词
                        if keyword not in ['股票', '上涨', '下跌', 'A股', '股市', '市场', '投资', '交易']:
                            keyword_counter[keyword] += 1

            # 🔴 第3步：取Top 10高频关键词作为热点
            hot_topics = [keyword for keyword, count in keyword_counter.most_common(10)]

            if not hot_topics:
                logger.warning("⚠️ 未提取到有效关键词，使用默认热点列表")
                hot_topics = [
                    "人工智能",
                    "半导体",
                    "新能源汽车",
                    "锂电池",
                    "光伏",
                    "军工",
                    "医药",
                    "消费电子",
                    "5G",
                    "数字经济"
                ]
            else:
                logger.success(f"✅ 动态识别到{len(hot_topics)}个热点题材: {', '.join(hot_topics)}")

    except Exception as e:
        logger.error(f"❌ 动态识别热点失败: {e}，使用默认热点列表")
        hot_topics = [
            "人工智能",
            "半导体",
            "新能源汽车",
            "锂电池",
            "光伏",
            "军工",
            "医药",
            "消费电子",
            "5G",
            "数字经济"
        ]

    # 🔴 第4步：搜索每个热点的最新新闻
    topic_results = []

    for topic in hot_topics:
        # 搜索该题材的新闻
        news = client.search_news(
            query=f"{topic} 股票",
            max_results=3,
            search_depth="basic"
        )

        if not news:
            continue

        # 分析整体情绪
        all_content = " ".join([n.get("content", "") for n in news])
        sentiment_analysis = client.analyze_sentiment(all_content)

        topic_results.append({
            "topic": topic,
            "news_count": len(news),
            "sentiment": sentiment_analysis["sentiment"],
            "sentiment_score": sentiment_analysis["score"],
            "keywords": sentiment_analysis["keywords"],
            "sample_news": news[0]["title"] if news else ""
        })

    # 按新闻数排序
    topic_results.sort(key=lambda x: x["news_count"], reverse=True)

    logger.info(f"提取热点题材成功,共 {len(topic_results)} 个题材")
    return topic_results[:5]  # 返回 Top 5 热点


def get_breaking_news() -> List[Dict[str, Any]]:
    """便捷函数: 获取重大突发新闻

    Returns:
        突发新闻列表
    """
    client = get_tavily_client()

    # 重大新闻关键词
    breaking_keywords = [
        "央行 降准",
        "央行 降息",
        "国务院 政策",
        "证监会 新规",
        "美联储",
        "地缘政治"
    ]

    breaking_news = []

    for keyword in breaking_keywords:
        news = client.search_news(
            query=keyword,
            max_results=2,
            search_depth="basic"
        )

        for item in news:
            # 分析重要性 (基于评分)
            score = item.get("score", 0)
            if score > 0.8:
                importance = "high"
            elif score > 0.6:
                importance = "medium"
            else:
                importance = "low"

            # 情绪分析
            content = item.get("content", "") + " " + item.get("title", "")
            sentiment_analysis = client.analyze_sentiment(content)

            breaking_news.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "published_date": item.get("published_date", ""),
                "importance": importance,
                "sentiment": sentiment_analysis["sentiment"],
                "sentiment_score": sentiment_analysis["score"],
                "keywords": sentiment_analysis["keywords"],
                "impact_sectors": []  # TODO: 可通过 NLP 提取影响板块
            })

    # 按重要性和分数排序
    breaking_news.sort(
        key=lambda x: (
            1 if x["importance"] == "high" else 0,
            x.get("sentiment_score", 0)
        ),
        reverse=True
    )

    logger.info(f"获取重大新闻成功,共 {len(breaking_news)} 条")
    return breaking_news[:5]  # 返回 Top 5


def analyze_news_sentiment(text: str) -> Dict[str, Any]:
    """便捷函数: 分析新闻情绪

    Args:
        text: 新闻文本

    Returns:
        情绪分析结果
    """
    client = get_tavily_client()
    return client.analyze_sentiment(text)
