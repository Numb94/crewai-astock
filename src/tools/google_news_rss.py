#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Google News RSS工具 - CrewAI A-Stock V2.0

描述: Google News RSS新闻获取工具，免费、实时性好
作为三个数据源之一，主要提供实时新闻

特性:
- 免费使用，无API限制
- 实时性好，延迟1-5分钟
- 支持关键词搜索
- 支持中文新闻

作者: AI Architect
版本: v2.0.0
日期: 2025-11-07
"""

import feedparser
import logging
from typing import List, Dict, Any
from datetime import datetime
import time
from urllib.parse import quote

# 配置日志
logger = logging.getLogger(__name__)


class GoogleNewsRSS:
    """Google News RSS新闻获取工具"""
    
    def __init__(self):
        """初始化"""
        self.base_url = "https://news.google.com/rss/search"
    
    def get_news(self, query: str = "股票", limit: int = 10, language: str = "zh-CN") -> List[Dict[str, Any]]:
        """
        获取Google News RSS新闻

        Args:
            query: 搜索关键词，默认"股票"
            limit: 获取数量，默认10条
            language: 语言，默认zh-CN（简体中文）

        Returns:
            [
                {
                    'title': '新闻标题',
                    'content': '新闻摘要',
                    'publish_time': '2025-11-07 10:30:00',
                    'source': 'Google News',
                    'url': 'https://...',
                    'keywords': ['关键词1', '关键词2']
                },
                ...
            ]
        """
        try:
            # 🔧 URL编码查询字符串（修复控制字符错误）
            query_encoded = quote(query)

            # 构建RSS URL
            url = f"{self.base_url}?q={query_encoded}&hl={language}&gl=CN&ceid=CN:{language}"

            # 解析RSS
            feed = feedparser.parse(url)

            if not feed.entries:
                logger.warning(f"未获取到Google News RSS新闻: {query}")
                return []

            news_list = []
            filtered_count = 0
            for entry in feed.entries[:limit * 2]:  # 多获取一些，因为要过滤
                title = entry.get('title', '')
                url = entry.get('link', '')

                # 🔴 过滤非新闻内容（股票行情页面）
                if self._is_stock_info_page(title, url):
                    filtered_count += 1
                    logger.debug(f"过滤非新闻内容: {title}")
                    continue

                # 解析发布时间（尝试多个字段）
                published_str = entry.get('published', '') or entry.get('updated', '') or entry.get('pubDate', '')

                # 🔴 调试：打印第一条新闻的时间信息
                if len(news_list) == 0:
                    logger.debug(f"第一条新闻时间字段:")
                    logger.debug(f"  published: {entry.get('published', 'N/A')}")
                    logger.debug(f"  updated: {entry.get('updated', 'N/A')}")
                    logger.debug(f"  pubDate: {entry.get('pubDate', 'N/A')}")
                    logger.debug(f"  published_parsed: {entry.get('published_parsed', 'N/A')}")

                publish_time = self._parse_time(published_str)

                news_list.append({
                    'title': title,
                    'content': entry.get('summary', ''),
                    'publish_time': publish_time,
                    'source': 'Google News',
                    'url': url,
                    'keywords': self._extract_keywords(title + entry.get('summary', ''))
                })

                # 达到目标数量后停止
                if len(news_list) >= limit:
                    break

            logger.info(f"✅ 获取Google News RSS新闻成功: {len(news_list)}条（过滤{filtered_count}条非新闻内容）")
            return news_list

        except Exception as e:
            logger.error(f"获取Google News RSS新闻失败: {e}")
            return []

    def _is_stock_info_page(self, title: str, url: str) -> bool:
        """
        判断是否是股票行情页面（非新闻内容）

        Args:
            title: 标题
            url: URL

        Returns:
            True: 是股票行情页面
            False: 是新闻内容
        """
        # 🔴 标题特征：包含这些关键词的通常是行情页面
        title_patterns = [
            "_股票价格_行情_走势图",
            "_股票行情",
            "股票股价",
            "公司高管",
            "搜狐证券",
            "新浪股票",
            "东方财富网",
            "中财网",
            "雪球",
            "股票行情中心"
        ]

        for pattern in title_patterns:
            if pattern in title:
                return True

        # 🔴 URL特征：这些域名通常是行情页面
        url_patterns = [
            "quote.eastmoney.com",  # 东方财富行情页
            "finance.sina.com.cn/realstock",  # 新浪实时行情
            "q.stock.sohu.com",  # 搜狐行情
            "xueqiu.com/S/",  # 雪球股票页
            "cfi.cn/p",  # 中财网行情
        ]

        for pattern in url_patterns:
            if pattern in url:
                return True

        return False
    
    def _parse_time(self, time_str: str) -> str:
        """
        解析时间字符串

        Args:
            time_str: 时间字符串（如"Thu, 07 Nov 2025 10:30:00 GMT"）

        Returns:
            格式化时间字符串（如"2025-11-07 10:30:00"）
        """
        if not time_str:
            logger.warning("时间字符串为空，使用当前时间")
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 尝试多种时间格式
        time_formats = [
            "%a, %d %b %Y %H:%M:%S %Z",  # Thu, 07 Nov 2025 10:30:00 GMT
            "%a, %d %b %Y %H:%M:%S %z",  # Thu, 07 Nov 2025 10:30:00 +0800
            "%Y-%m-%dT%H:%M:%S%z",       # 2025-11-07T10:30:00+08:00
            "%Y-%m-%dT%H:%M:%SZ",        # 2025-11-07T10:30:00Z
            "%Y-%m-%d %H:%M:%S",         # 2025-11-07 10:30:00
        ]

        for fmt in time_formats:
            try:
                time_struct = time.strptime(time_str, fmt)
                dt = datetime(*time_struct[:6])
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

        # 所有格式都失败，记录警告并使用当前时间
        logger.warning(f"无法解析时间字符串: {time_str}，使用当前时间")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词
        
        Args:
            text: 文本内容
            
        Returns:
            关键词列表
        """
        # 关键词列表
        positive_keywords = [
            "利好", "上涨", "突破", "创新", "增长", "盈利", "业绩",
            "订单", "合作", "中标", "政策", "扶持", "补贴", "降准", "降息"
        ]
        
        negative_keywords = [
            "利空", "下跌", "暴跌", "亏损", "风险", "调查", "处罚",
            "诉讼", "违规", "裁员", "ST", "退市", "破产"
        ]
        
        keywords = []
        for kw in positive_keywords + negative_keywords:
            if kw in text:
                keywords.append(kw)
        
        return keywords[:5]  # 最多返回5个关键词


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 创建Google News RSS工具
    google_news = GoogleNewsRSS()
    
    # 获取股票新闻
    news = google_news.get_news(query="股票", limit=5)
    
    print(f"\n获取到{len(news)}条新闻：")
    for i, item in enumerate(news, 1):
        print(f"\n{i}. {item['title']}")
        print(f"   来源: {item['source']}")
        print(f"   时间: {item['publish_time']}")
        print(f"   关键词: {', '.join(item['keywords'])}")
        print(f"   链接: {item['url']}")

