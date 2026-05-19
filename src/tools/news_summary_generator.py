#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
开盘前新闻摘要生成器 - CrewAI A-Stock V2.0

描述: 生成开盘前新闻摘要，汇总夜间重大新闻
格式:
- 重大利好
- 市场动态
- 风险提示

作者: AI Architect
版本: v2.0.0
日期: 2025-11-07
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)


class NewsSummaryGenerator:
    """开盘前新闻摘要生成器"""
    
    def __init__(self):
        """初始化"""
        pass
    
    def generate_summary(self, news_list: List[Dict[str, Any]]) -> str:
        """
        生成开盘前新闻摘要
        
        Args:
            news_list: 新闻列表
            
        Returns:
            摘要文本（Markdown格式）
        """
        if not news_list:
            return "📰 开盘前新闻摘要\n\n暂无重要新闻"
        
        # 分类新闻
        positive_news = []  # 重大利好
        market_news = []    # 市场动态
        risk_news = []      # 风险提示
        
        for news in news_list:
            keywords = news.get('keywords', [])
            title = news.get('title', '')
            
            # 判断新闻类型
            if any(kw in keywords for kw in ["利好", "上涨", "突破", "增长", "盈利", "降准", "降息"]):
                positive_news.append(news)
            elif any(kw in keywords for kw in ["利空", "下跌", "亏损", "风险", "处罚"]):
                risk_news.append(news)
            else:
                market_news.append(news)
        
        # 生成摘要
        summary = f"📰 开盘前新闻摘要（{datetime.now().strftime('%Y-%m-%d %H:%M')}）\n\n"
        
        # 重大利好
        if positive_news:
            summary += "🔴 重大利好：\n"
            for i, news in enumerate(positive_news[:5], 1):
                summary += f"{i}. {news['title']}\n"
            summary += "\n"
        
        # 市场动态
        if market_news:
            summary += "📊 市场动态：\n"
            for i, news in enumerate(market_news[:5], 1):
                summary += f"{i}. {news['title']}\n"
            summary += "\n"
        
        # 风险提示
        if risk_news:
            summary += "⚠️ 风险提示：\n"
            for i, news in enumerate(risk_news[:5], 1):
                summary += f"{i}. {news['title']}\n"
            summary += "\n"
        
        summary += "---\n本摘要由AI系统自动生成"
        
        return summary
    
    def generate_html_summary(self, news_list: List[Dict[str, Any]]) -> str:
        """
        生成开盘前新闻摘要（HTML格式）
        
        Args:
            news_list: 新闻列表
            
        Returns:
            摘要HTML
        """
        if not news_list:
            return "<h3>📰 开盘前新闻摘要</h3><p>暂无重要新闻</p>"
        
        # 分类新闻
        positive_news = []  # 重大利好
        market_news = []    # 市场动态
        risk_news = []      # 风险提示
        
        for news in news_list:
            keywords = news.get('keywords', [])
            
            # 判断新闻类型
            if any(kw in keywords for kw in ["利好", "上涨", "突破", "增长", "盈利", "降准", "降息"]):
                positive_news.append(news)
            elif any(kw in keywords for kw in ["利空", "下跌", "亏损", "风险", "处罚"]):
                risk_news.append(news)
            else:
                market_news.append(news)
        
        # 生成HTML
        html = f"<h3>📰 开盘前新闻摘要（{datetime.now().strftime('%Y-%m-%d %H:%M')}）</h3>"
        
        # 重大利好
        if positive_news:
            html += "<h4 style='color: #f56c6c;'>🔴 重大利好：</h4><ol>"
            for news in positive_news[:5]:
                html += f"<li><a href='{news['url']}' target='_blank'>{news['title']}</a></li>"
            html += "</ol>"
        
        # 市场动态
        if market_news:
            html += "<h4 style='color: #409eff;'>📊 市场动态：</h4><ol>"
            for news in market_news[:5]:
                html += f"<li><a href='{news['url']}' target='_blank'>{news['title']}</a></li>"
            html += "</ol>"
        
        # 风险提示
        if risk_news:
            html += "<h4 style='color: #e6a23c;'>⚠️ 风险提示：</h4><ol>"
            for news in risk_news[:5]:
                html += f"<li><a href='{news['url']}' target='_blank'>{news['title']}</a></li>"
            html += "</ol>"
        
        html += "<hr><p style='color: #909399; font-size: 12px;'>本摘要由AI系统自动生成</p>"
        
        return html


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 创建摘要生成器
    generator = NewsSummaryGenerator()
    
    # 测试数据
    test_news = [
        {
            'title': '央行宣布降准0.5个百分点',
            'keywords': ['降准', '利好'],
            'url': 'https://example.com/1'
        },
        {
            'title': '美股三大指数集体上涨',
            'keywords': ['上涨'],
            'url': 'https://example.com/2'
        },
        {
            'title': '某某公司业绩预亏',
            'keywords': ['亏损', '风险'],
            'url': 'https://example.com/3'
        }
    ]
    
    # 生成摘要
    summary = generator.generate_summary(test_news)
    print(summary)
    
    print("\n" + "="*50 + "\n")
    
    # 生成HTML摘要
    html_summary = generator.generate_html_summary(test_news)
    print(html_summary)

