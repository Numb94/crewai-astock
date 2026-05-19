#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grok 实时搜索客户端

使用 Grok 模型进行实时新闻和社区情绪搜索
Grok 具有实时搜索能力，可以获取最新的市场信息
"""

import os
from datetime import datetime
from typing import Optional
from loguru import logger
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class GrokClient:
    """Grok 实时搜索客户端"""

    def __init__(self):
        self.api_key = os.getenv('GROK_API_KEY')
        self.base_url = os.getenv('GROK_BASE_URL', 'https://api.x.ai/v1')
        self.model = os.getenv('GROK_MODEL', 'grok-beta')

        if not self.api_key:
            raise ValueError("GROK_API_KEY 未配置")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        logger.info(f"Grok 客户端初始化: model={self.model}, base_url={self.base_url}")

    def search_stock_news(self, stock_code: str, stock_name: str) -> dict:
        """
        使用 Grok 实时搜索股票相关新闻

        Args:
            stock_code: 股票代码
            stock_name: 股票名称

        Returns:
            新闻分析结果，包含评分和摘要
        """
        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""今天是{today}。请搜索 {stock_name}（股票代码：{stock_code}）最近3天的新闻和公告。

请分析并返回以下内容：
1. 最近3天的重要新闻标题和日期（最多5条）
2. 新闻情绪评分（0-100分，50分为中性）
3. 新闻性质分类（利好/利空/中性）
4. 简要分析（50字以内）

请严格按以下格式输出：
【新闻列表】
1. [日期] 新闻标题
2. [日期] 新闻标题
...

【新闻情绪评分】XX分
【新闻性质】利好/利空/中性
【简要分析】...

如果没有找到相关新闻，请说明"近3天无重大新闻"，评分给60分（偏中性）。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的A股市场新闻分析师，擅长搜索和分析股票相关新闻。请基于实时搜索结果进行分析。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            content = response.choices[0].message.content
            logger.info(f"Grok 新闻搜索完成: {stock_name}({stock_code})")

            # 解析评分
            score = self._extract_score(content)

            return {
                "success": True,
                "content": content,
                "score": score,
                "stock_code": stock_code,
                "stock_name": stock_name
            }

        except Exception as e:
            logger.error(f"Grok 新闻搜索失败: {stock_name}({stock_code}) - {e}")
            return {
                "success": False,
                "content": f"搜索失败: {str(e)}",
                "score": 60,  # 失败时返回中性分数
                "stock_code": stock_code,
                "stock_name": stock_name
            }

    def search_community_sentiment(self, stock_code: str, stock_name: str) -> dict:
        """
        使用 Grok 实时搜索股票社区情绪

        Args:
            stock_code: 股票代码
            stock_name: 股票名称

        Returns:
            社区情绪分析结果，包含评分和摘要
        """
        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""今天是{today}。请搜索 {stock_name}（股票代码：{stock_code}）在雪球、东方财富股吧、淘股吧等平台的最新讨论和评论。

请分析并返回以下内容：
1. 散户情绪倾向（看多/看空/中性）
2. 讨论热度（高/中/低）
3. 主要观点摘要（最多3条）
4. 社区情绪评分（0-100分，50分为中性）
5. 简要分析（50字以内）

请严格按以下格式输出：
【散户情绪】看多/看空/中性
【讨论热度】高/中/低
【主要观点】
1. ...
2. ...
3. ...

【社区情绪评分】XX分
【简要分析】...

注意：散户情绪可作为反向指标参考。如果散户过度乐观可能需要警惕，过度悲观可能是机会。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的A股市场社区情绪分析师，擅长分析雪球、东财股吧、淘股吧等平台的散户情绪。请基于实时搜索结果进行分析。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            content = response.choices[0].message.content
            logger.info(f"Grok 社区情绪搜索完成: {stock_name}({stock_code})")

            # 解析评分
            score = self._extract_score(content)

            return {
                "success": True,
                "content": content,
                "score": score,
                "stock_code": stock_code,
                "stock_name": stock_name
            }

        except Exception as e:
            logger.error(f"Grok 社区情绪搜索失败: {stock_name}({stock_code}) - {e}")
            return {
                "success": False,
                "content": f"搜索失败: {str(e)}",
                "score": 60,  # 失败时返回中性分数
                "stock_code": stock_code,
                "stock_name": stock_name
            }

    def search_market_news(self, keywords: str = "A股 股市") -> dict:
        """
        使用 Grok 实时搜索市场新闻热点

        Args:
            keywords: 搜索关键词

        Returns:
            市场新闻分析结果
        """
        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""今天是{today}。请搜索全球金融市场最新动态，重点关注对A股有影响的信息。

关键词：{keywords}

请分析并返回以下内容：

【一、外围市场动态】
1. 美股三大指数（道琼斯、纳斯达克、标普500）最新表现
2. 港股恒生指数、恒生科技指数最新表现
3. 欧洲股市、日韩股市重要动态（如有）

【二、宏观经济与政策】
1. 美联储/中国央行最新动态（利率、货币政策）
2. 重要经济数据（CPI、PMI、就业数据等）
3. 中美关系、国际贸易相关新闻
4. 国内重要政策（产业政策、财政政策等）

【三、大宗商品与汇率】
1. 原油、黄金、铜等大宗商品走势
2. 美元指数、人民币汇率变化
3. 对相关A股板块的影响判断

【四、A股市场热点】
1. 当前最热门题材板块 TOP 5
2. 近3天重要财经新闻（最多10条）
3. 市场情绪判断

请严格按以下格式输出：

🌍 外围市场:
- 美股: [涨跌情况及原因]
- 港股: [涨跌情况]
- 其他: [重要动态]

📊 宏观经济:
- 货币政策: [美联储/央行动态]
- 经济数据: [重要数据]
- 政策动向: [国内外政策]

💰 商品汇率:
- 大宗商品: [原油/黄金/铜等]
- 汇率: [美元/人民币]
- A股影响: [对哪些板块有影响]

🔥 A股热点 TOP 5:
1. 题材名称 - 热度说明
2. 题材名称 - 热度说明
...

📰 重要新闻:
1. 【来源】新闻标题
...

📈 市场情绪:
整体判断（乐观/谨慎/悲观）+ 操作建议"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的全球金融市场分析师，擅长分析外围市场、宏观经济、大宗商品对A股的影响。请基于实时搜索结果进行全面分析，帮助投资者把握市场脉搏。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=3000
            )

            content = response.choices[0].message.content
            logger.info(f"Grok 市场新闻搜索完成")

            return {
                "success": True,
                "content": content
            }

        except Exception as e:
            logger.error(f"Grok 市场新闻搜索失败: {e}")
            return {
                "success": False,
                "content": f"搜索失败: {str(e)}"
            }

    def get_trending_topics(self, limit: int = 10) -> dict:
        """
        使用 Grok 获取当前热门关注词/话题

        Args:
            limit: 返回数量限制

        Returns:
            热门话题列表
        """
        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""今天是{today}。请搜索当前A股市场最热门的关注话题和概念。

请返回 TOP {limit} 热门话题，包括：
- 行业板块（如AI、新能源、半导体、医药等）
- 热门概念（如机器人、CPO、算力、低空经济等）
- 政策相关话题

请严格按以下格式输出：
🔥 热门关注词 TOP {limit}:
1. 话题名称 - 热度说明（高/中/低）
2. 话题名称 - 热度说明（高/中/低）
...

📈 近期趋势:
- 上升趋势：...
- 下降趋势：..."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的A股市场分析师，擅长识别市场热点和热门话题。请基于实时搜索结果进行分析。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            content = response.choices[0].message.content
            logger.info(f"Grok 热门话题搜索完成")

            return {
                "success": True,
                "content": content
            }

        except Exception as e:
            logger.error(f"Grok 热门话题搜索失败: {e}")
            return {
                "success": False,
                "content": f"搜索失败: {str(e)}"
            }

    def analyze_topic_trend(self, topic: str, days: int = 7) -> dict:
        """
        使用 Grok 分析话题热度趋势

        Args:
            topic: 话题关键词
            days: 分析天数

        Returns:
            话题趋势分析结果
        """
        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""今天是{today}。请分析「{topic}」这个话题在A股市场最近{days}天的热度趋势。

请分析并返回以下内容：
1. 热度变化趋势（上升/平稳/下降）
2. 相关新闻数量变化
3. 相关概念股表现
4. 未来走势预判

请严格按以下格式输出：
=== {topic} 热度趋势分析（最近{days}天）===

📈 热度变化:
- 趋势：上升/平稳/下降
- 变化说明：...

📰 新闻关注度:
- 最近{days}天相关新闻情况
- 重要事件节点

📊 相关概念股:
- 代表性股票及表现

🔮 未来预判:
- 短期走势预判及理由"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的A股市场分析师，擅长分析行业话题和概念的热度变化。请基于实时搜索结果进行分析。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            content = response.choices[0].message.content
            logger.info(f"Grok 话题趋势分析完成: {topic}")

            return {
                "success": True,
                "content": content,
                "topic": topic
            }

        except Exception as e:
            logger.error(f"Grok 话题趋势分析失败: {topic} - {e}")
            return {
                "success": False,
                "content": f"分析失败: {str(e)}",
                "topic": topic
            }

    def _extract_score(self, content: str) -> int:
        """从内容中提取评分"""
        import re

        # 尝试匹配 "XX分" 格式
        patterns = [
            r'【.*评分】\s*(\d+)\s*分',
            r'评分[：:]\s*(\d+)',
            r'(\d+)\s*分',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                score = int(match.group(1))
                if 0 <= score <= 100:
                    return score

        # 默认返回中性分数
        return 60


# 全局客户端实例（懒加载）
_grok_client: Optional[GrokClient] = None


def get_grok_client() -> GrokClient:
    """获取 Grok 客户端单例"""
    global _grok_client
    if _grok_client is None:
        _grok_client = GrokClient()
    return _grok_client
