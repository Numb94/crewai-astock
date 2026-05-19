#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新闻数据源管理器 - CrewAI Stock

描述: 基于 Tavily API 的新闻获取与紧急程度判断

特性:
- Tavily API 调用次数控制
- 数据去重和合并
- 情感分析和紧急程度判断（时效性权重衰减）
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# 导入数据源工具
from src.tools.tavily_api import TavilyAPIClient

# 配置日志
logger = logging.getLogger(__name__)


class NewsSourceManager:
    """新闻数据源管理器（Tavily）"""

    def __init__(self):
        """初始化"""
        # Tavily API
        try:
            self.tavily = TavilyAPIClient()
            logger.info("✅ Tavily API 初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ Tavily API 初始化失败: {e}")
            self.tavily = None

        # Tavily API 调用计数（每天限制10次）
        self.tavily_call_count = 0
        self.tavily_max_calls = 10
        self.tavily_reset_date = datetime.now().date()

    def get_breaking_news(self, keywords: List[str], urgency: str = 'normal') -> List[Dict[str, Any]]:
        """
        获取突发新闻

        Args:
            keywords: 关键词列表（如["降准", "降息", "重组"]）
            urgency: 紧急程度（'critical'=立即, 'high'=5分钟, 'normal'=常规）

        Returns:
            新闻列表
        """
        all_news = []

        # 重置 Tavily API 调用计数（每天重置）
        if datetime.now().date() > self.tavily_reset_date:
            self.tavily_call_count = 0
            self.tavily_reset_date = datetime.now().date()

        # Tavily API（紧急情况下调用）
        if urgency == 'critical' and self.tavily_call_count < self.tavily_max_calls and self.tavily is not None:
            logger.info(f"🔴 紧急情况，调用 Tavily API 搜索新闻: {keywords}")
            for keyword in keywords:
                try:
                    tavily_news = self.tavily.search_news(query=keyword, max_results=5)
                    all_news.extend(tavily_news)
                    self.tavily_call_count += 1
                    logger.info(f"✅ Tavily API 调用成功，剩余次数: {self.tavily_max_calls - self.tavily_call_count}")
                except Exception as e:
                    logger.error(f"❌ Tavily API 调用失败: {e}")

        # 数据去重和合并
        unique_news = self._deduplicate_news(all_news)

        # 按发布时间排序（最新的在前）
        unique_news.sort(key=lambda x: x.get('publish_time', ''), reverse=True)

        logger.info(f"📰 获取新闻总数: {len(unique_news)} 条（去重后）")
        return unique_news

    def _deduplicate_news(self, news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """新闻去重"""
        seen_titles = set()
        unique_news = []

        for news in news_list:
            title = news.get('title', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news)

        return unique_news

    def _extract_date_from_url(self, url: str) -> Optional[datetime]:
        """从URL中提取日期"""
        import re

        # 匹配常见日期格式：20250507, 2025-05-07, 2025/05/07
        patterns = [
            (r'(\d{8})', '%Y%m%d'),
            (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
            (r'(\d{4})/(\d{2})/(\d{2})', '%Y/%m/%d'),
        ]

        for pattern, date_format in patterns:
            match = re.search(pattern, url)
            if match:
                try:
                    if len(match.groups()) == 1:
                        date_str = match.group(1)
                        return datetime.strptime(date_str, date_format)
                    else:
                        date_str = '-'.join(match.groups())
                        return datetime.strptime(date_str, date_format)
                except Exception:
                    continue

        return None

    def is_recent_news(self, news: Dict[str, Any], hours: int = 1) -> bool:
        """判断新闻是否是最近发布的"""
        publish_time_str = news.get('publish_time') or news.get('published_date')
        publish_time = None

        if publish_time_str:
            try:
                from dateutil import parser as date_parser
                if isinstance(publish_time_str, str):
                    publish_time = date_parser.parse(publish_time_str)
                else:
                    publish_time = publish_time_str
                if publish_time.tzinfo is not None:
                    publish_time = publish_time.replace(tzinfo=None)
            except Exception:
                publish_time = None

        if not publish_time:
            url = news.get('url', '')
            if url:
                publish_time = self._extract_date_from_url(url)

        if not publish_time:
            logger.debug("新闻缺少发布时间且无法从URL提取，默认为旧新闻")
            return False

        now = datetime.now()
        time_diff = now - publish_time
        hours_diff = time_diff.total_seconds() / 3600

        return hours_diff <= hours

    def judge_news_urgency(self, news: Dict[str, Any]) -> str:
        """
        判断新闻紧急程度（支持时效性权重衰减）

        Returns:
            'critical' | 'high' | 'medium' | 'low'
        """
        title = news.get('title', '')
        content = news.get('content', '')
        source = news.get('source', '')

        # 时效性权重
        publish_time_str = news.get('publish_time') or news.get('published_date')
        publish_time = None
        time_weight = 0.0

        if publish_time_str:
            try:
                from dateutil import parser as date_parser
                if isinstance(publish_time_str, str):
                    publish_time = date_parser.parse(publish_time_str)
                else:
                    publish_time = publish_time_str
                if publish_time.tzinfo is not None:
                    publish_time = publish_time.replace(tzinfo=None)
            except Exception:
                pass

        if not publish_time:
            url = news.get('url', '')
            if url:
                publish_time = self._extract_date_from_url(url)

        if publish_time:
            now = datetime.now()
            time_diff = now - publish_time
            hours_diff = time_diff.total_seconds() / 3600

            if hours_diff <= 6:
                time_weight = 1.0
            elif hours_diff <= 24:
                time_weight = 0.9
            elif hours_diff <= 48:
                time_weight = 0.7
            elif hours_diff <= 72:
                time_weight = 0.5
            elif hours_diff <= 168:
                time_weight = 0.3
            else:
                time_weight = 0.1
        else:
            time_weight = 0.5

        # 关键词权重评分
        critical_keywords = {
            "重大政策": 9, "央行": 8, "国务院": 8, "证监会": 7,
            "行业利好": 8, "重组": 7, "并购": 6
        }
        high_keywords = {
            "业绩暴增": 6, "业绩预增": 5, "中标": 5,
            "合作": 4, "政策": 4, "扶持": 4, "补贴": 3,
            "涨停": 3, "停牌": 2, "复牌": 2
        }

        score = 0
        for keyword, weight in critical_keywords.items():
            if keyword in title or keyword in content:
                score += weight

        for keyword, weight in high_keywords.items():
            if keyword in title or keyword in content:
                score += weight

        # 来源可信度加权
        trusted_sources = ["新华社", "人民日报", "央视", "证券时报", "中国证券报", "上海证券报"]
        if any(src in source for src in trusted_sources):
            score = int(score * 1.5)

        # 应用时效性权重衰减
        score = int(score * time_weight)

        if score >= 10:
            return 'critical'
        elif score >= 5:
            return 'high'
        elif score >= 2:
            return 'medium'
        else:
            return 'low'


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = NewsSourceManager()
    news = manager.get_breaking_news(keywords=["股票", "A股"], urgency='normal')
    print(f"\n获取到 {len(news)} 条新闻")
