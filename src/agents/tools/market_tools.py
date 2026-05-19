#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - 市场数据工具

为CrewAI Agent提供市场数据查询能力(基于智兔API)
"""

from crewai.tools import tool
from typing import List, Dict, Optional, Any, Set
from pydantic import Field
import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)


# ========================================
# LLM板块匹配缓存（避免重复调用LLM）
# ========================================
_llm_sector_match_cache: Dict[str, Set[str]] = {}

# ========================================
# 股票概念缓存（避免重复API调用）
# ========================================
_stock_concepts_cache: Dict[str, List[str]] = {}


def _get_stock_concepts_from_api(stock_code: str) -> List[str]:
    """
    从智兔API获取股票概念标签

    Args:
        stock_code: 股票代码

    Returns:
        概念标签列表
    """
    global _stock_concepts_cache

    # 检查内存缓存
    if stock_code in _stock_concepts_cache:
        return _stock_concepts_cache[stock_code]

    try:
        from src.tools.zhitu_api import ZhituAPI
        zhitu = ZhituAPI()
        sectors = zhitu.get_stock_sectors(stock_code)

        concepts = []
        if sectors:
            # 智兔API返回格式: [{"keyword": "所属板块", "content": "银行 广东板块 破净股 ..."}]
            if isinstance(sectors, list):
                for item in sectors:
                    content = item.get('content', '')
                    if content:
                        # 按空格分割概念
                        tags = content.split()
                        concepts.extend(tags)
            elif isinstance(sectors, dict):
                # 兼容字典格式
                content = sectors.get('content', '')
                if content:
                    tags = content.split()
                    concepts.extend(tags)

        # 缓存结果
        _stock_concepts_cache[stock_code] = concepts

        # 同时保存到数据库
        if concepts:
            _save_concepts_to_db(stock_code, concepts)
            logger.debug(f"✅ {stock_code} 从API获取 {len(concepts)} 个概念: {concepts[:5]}...")

        return concepts

    except Exception as e:
        logger.warning(f"获取{stock_code}概念失败: {e}")
        return []


def _save_concepts_to_db(stock_code: str, concepts: List[str]):
    """将概念保存到数据库（去重）"""
    try:
        from src.database.db_manager import DatabaseManager
        from src.database.models import StockConcepts
        from datetime import datetime

        db_manager = DatabaseManager()
        with db_manager.get_session() as db:
            # 检查已有的标签
            existing = db.query(StockConcepts.tag).filter(
                StockConcepts.stock_code == stock_code
            ).all()
            existing_tags = {t[0] for t in existing}

            # 插入新标签
            new_tags = [c for c in concepts if c and c not in existing_tags]
            for tag in new_tags[:20]:  # 最多保存20个标签
                db.add(StockConcepts(
                    stock_code=stock_code,
                    tag=tag,
                    category='概念',
                    updated_at=datetime.now()
                ))
            db.commit()

    except Exception as e:
        logger.debug(f"保存{stock_code}概念到数据库失败: {e}")


def _get_stock_concepts(stock_code: str, db_tags_map: Dict[str, str]) -> List[str]:
    """
    获取股票概念（优先本地缓存，否则调用API）

    Args:
        stock_code: 股票代码
        db_tags_map: 数据库中的标签映射

    Returns:
        概念列表
    """
    # 1. 优先使用数据库缓存
    if stock_code in db_tags_map and db_tags_map[stock_code]:
        return db_tags_map[stock_code].split()

    # 2. 调用智兔API获取
    return _get_stock_concepts_from_api(stock_code)


def _stock_matches_concepts_simple(stock_concepts: List[str], user_concepts: List[str]) -> tuple[bool, str]:
    """
    简单的概念匹配（子串匹配 + 精确匹配）

    Args:
        stock_concepts: 股票的概念列表
        user_concepts: 用户指定的概念

    Returns:
        (是否匹配, 匹配到的概念)
    """
    for user_concept in user_concepts:
        user_concept_lower = user_concept.lower()

        for stock_concept in stock_concepts:
            stock_concept_lower = stock_concept.lower()

            # 精确匹配
            if user_concept_lower == stock_concept_lower:
                return True, user_concept

            # 子串匹配（双向）
            if user_concept_lower in stock_concept_lower or stock_concept_lower in user_concept_lower:
                return True, user_concept

            # 常见别名匹配
            alias_map = {
                'ai': ['人工智能', 'aigc', 'chatgpt', 'gpt', '大模型', '机器学习'],
                '人工智能': ['ai', 'aigc', 'chatgpt', 'gpt', '大模型'],
                '锂电': ['锂电池', '动力电池', '储能', '新能源车'],
                '锂电池': ['锂电', '动力电池', '储能', '新能源车'],
                '新能源': ['新能源车', '光伏', '风电', '储能', '锂电池'],
                '芯片': ['半导体', '集成电路', 'ic', '晶圆'],
                '半导体': ['芯片', '集成电路', 'ic', '晶圆'],
            }

            if user_concept_lower in alias_map:
                for alias in alias_map[user_concept_lower]:
                    if alias.lower() in stock_concept_lower or stock_concept_lower in alias.lower():
                        return True, user_concept

    return False, ""


def _get_all_unique_tags() -> List[str]:
    """
    获取数据库中的热门板块/概念标签

    Returns:
        标签列表（按关联股票数量排序的前150个）
    """
    from src.database.db_manager import DatabaseManager
    from src.database.models import StockConcepts
    from sqlalchemy import func

    try:
        db_manager = DatabaseManager()
        with db_manager.get_session() as db:
            # 获取所有标签，按关联股票数排序
            results = db.query(
                StockConcepts.tag,
                func.count(StockConcepts.stock_code).label('stock_count')
            ).group_by(
                StockConcepts.tag
            ).order_by(
                func.count(StockConcepts.stock_code).desc()
            ).limit(150).all()  # 取前150个热门标签

            # 过滤超长标签（经营范围等）
            tags = [r[0] for r in results if r[0] and len(r[0]) < 15]

            logger.info(f"✅ 标签采样: 共{len(tags)}个热门标签")
            return tags

    except Exception as e:
        logger.warning(f"获取标签列表失败: {e}")
        return []


def _llm_match_sectors(user_concepts: List[str], all_tags: List[str]) -> Dict[str, Set[str]]:
    """
    使用LLM匹配用户输入的概念和数据库标签

    Args:
        user_concepts: 用户输入的概念列表，如 ["AI", "芯片"]
        all_tags: 数据库中的标签列表

    Returns:
        {用户概念: {匹配的标签集合}}
    """
    global _llm_sector_match_cache

    # 检查缓存
    cache_key = ','.join(sorted(user_concepts))
    if cache_key in _llm_sector_match_cache:
        logger.info(f"✅ 使用缓存的板块匹配结果: {cache_key}")
        return {c: _llm_sector_match_cache[cache_key] for c in user_concepts}

    from src.config.llm_config import get_direct_llm

    try:
        llm = get_direct_llm()

        # 构建简洁的提示词
        prompt = f"""将用户概念匹配到数据库标签。

用户概念: {', '.join(user_concepts)}

数据库标签: {', '.join(all_tags[:100])}

规则: AI=人工智能, 芯片=半导体, 新能源车=锂电池。只返回存在的标签。

输出JSON:
{{"概念1": ["匹配标签1", "匹配标签2"]}}"""

        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        # 提取JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            matched = {k: set(v) for k, v in result.items()}

            # 缓存
            all_matched_tags = set()
            for tags in matched.values():
                all_matched_tags.update(tags)
            _llm_sector_match_cache[cache_key] = all_matched_tags

            logger.info(f"✅ LLM板块匹配: {user_concepts} → {matched}")
            return matched
        else:
            logger.warning(f"⚠️ LLM返回格式错误: {content[:100]}")
            return {}

    except Exception as e:
        logger.error(f"❌ LLM板块匹配失败: {e}")
        return {}


def _stock_matches_concepts_llm(stock_tags: str, user_concepts: List[str],
                                 llm_matched: Dict[str, Set[str]]) -> tuple[bool, str]:
    """
    检查股票标签是否匹配用户概念（使用LLM匹配结果）

    Args:
        stock_tags: 股票的所有标签（空格分隔）
        user_concepts: 用户输入的概念
        llm_matched: LLM匹配结果

    Returns:
        (是否匹配, 匹配到的概念)
    """
    stock_tag_set = set(stock_tags.split())

    for concept in user_concepts:
        # 1. 直接匹配
        if concept in stock_tag_set:
            return True, concept

        # 2. 子串匹配
        for tag in stock_tag_set:
            if concept in tag or tag in concept:
                return True, concept

        # 3. LLM语义匹配
        if concept in llm_matched:
            matched_tags = llm_matched[concept]
            intersection = stock_tag_set & matched_tags
            if intersection:
                return True, concept

    return False, ""


@tool("获取市场情绪数据")
def get_market_sentiment() -> str:
    """
    获取市场情绪综合分析数据，包括：
    1. 大盘走势分析（上证、深证、创业板指数涨跌幅）
    2. 涨跌停数据（今天vs昨天的变化趋势）
    3. 涨跌家数分析（上涨/下跌股票数量和比例）
    4. 成交量变化分析（今天vs昨天）
    5. 综合市场情绪判断（HOT/WARM/NEUTRAL/COLD）

    Returns:
        市场情绪综合分析描述(自然语言)
    """
    from src.tools.data_source_manager import DataSourceManager
    from src.tools.zhitu_api import ZhituAPI
    from src.database.db_manager import get_db
    from src.database.models import MarketSentiment
    from datetime import date, timedelta

    try:
        dsm = DataSourceManager()
        zhitu = ZhituAPI()

        # 获取今天和昨天的日期
        today = date.today()
        yesterday = today - timedelta(days=1)
        today_str = today.strftime('%Y-%m-%d')
        yesterday_str = yesterday.strftime('%Y-%m-%d')

        # ==================== 1. 大盘走势分析 ====================
        # 获取三大指数实时数据
        shanghai_index = zhitu.get_index_realtime("000001.SH")  # 上证指数
        shenzhen_index = zhitu.get_index_realtime("399001.SZ")  # 深证成指
        chinext_index = zhitu.get_index_realtime("399006.SZ")   # 创业板指

        # 提取涨跌幅（使用pc字段，不是zf字段）
        # pc: 涨跌幅（%），正数表示上涨，负数表示下跌
        # zf: 振幅（%），表示当日最高价和最低价的差值
        shanghai_change = shanghai_index.get('pc', 0) if shanghai_index else 0
        shenzhen_change = shenzhen_index.get('pc', 0) if shenzhen_index else 0
        chinext_change = chinext_index.get('pc', 0) if chinext_index else 0

        # 计算大盘平均涨跌幅
        avg_index_change = (shanghai_change + shenzhen_change + chinext_change) / 3

        # 判断大盘走势
        if avg_index_change > 2:
            index_trend = "大涨"
        elif avg_index_change > 1:
            index_trend = "上涨"
        elif avg_index_change > -1:
            index_trend = "横盘"
        elif avg_index_change > -2:
            index_trend = "下跌"
        else:
            index_trend = "大跌"

        # ==================== 2. 涨跌停数据分析 ====================
        # 获取今天的涨停股票
        try:
            response = asyncio.run(dsm.get_limit_up_stocks(today_str))
            if response and response.success and response.data:
                limit_up_stocks_today = response.data
            else:
                limit_up_stocks_today = []
        except Exception:
            limit_up_stocks_today = zhitu.get_limit_up_pool(today_str)

        limit_up_count_today = len(limit_up_stocks_today) if limit_up_stocks_today else 0

        # 获取昨天的涨停/跌停股票数量（从数据库）
        db = get_db()
        with db.get_session() as session:
            yesterday_sentiment = session.query(MarketSentiment).filter_by(sentiment_date=yesterday).first()
            if yesterday_sentiment:
                limit_up_count_yesterday = yesterday_sentiment.limit_up_count
                limit_down_count_yesterday = yesterday_sentiment.limit_down_count if yesterday_sentiment.limit_down_count else 0
            else:
                limit_up_count_yesterday = limit_up_count_today
                limit_down_count_yesterday = 0

        # 计算涨停变化
        if limit_up_count_yesterday > 0:
            limit_up_change_pct = ((limit_up_count_today - limit_up_count_yesterday) / limit_up_count_yesterday) * 100
        else:
            limit_up_change_pct = 0

        # 涨停趋势判断
        if limit_up_change_pct > 50:
            limit_up_trend = f"大幅增加{abs(limit_up_change_pct):.0f}%"
        elif limit_up_change_pct > 20:
            limit_up_trend = f"增加{abs(limit_up_change_pct):.0f}%"
        elif limit_up_change_pct > -20:
            limit_up_trend = "基本持平"
        elif limit_up_change_pct > -50:
            limit_up_trend = f"减少{abs(limit_up_change_pct):.0f}%"
        else:
            limit_up_trend = f"大幅减少{abs(limit_up_change_pct):.0f}%"

        # 获取跌停股票数量
        try:
            limit_down_stocks_today = zhitu.get_limit_down_pool(today_str)
            limit_down_count_today = len(limit_down_stocks_today) if limit_down_stocks_today else 0
        except Exception as e:
            logger.warning(f"获取跌停股池失败: {e}")
            limit_down_count_today = 0

        # 计算跌停变化
        if limit_down_count_yesterday > 0:
            limit_down_change_pct = ((limit_down_count_today - limit_down_count_yesterday) / limit_down_count_yesterday) * 100
        else:
            limit_down_change_pct = 0 if limit_down_count_today == 0 else 100

        # 跌停趋势判断
        if limit_down_change_pct > 200:
            limit_down_trend = f"暴增{abs(limit_down_change_pct):.0f}%"
        elif limit_down_change_pct > 50:
            limit_down_trend = f"大幅增加{abs(limit_down_change_pct):.0f}%"
        elif limit_down_change_pct > 20:
            limit_down_trend = f"增加{abs(limit_down_change_pct):.0f}%"
        elif limit_down_change_pct > -20:
            limit_down_trend = "基本持平"
        elif limit_down_change_pct > -50:
            limit_down_trend = f"减少{abs(limit_down_change_pct):.0f}%"
        else:
            limit_down_trend = f"大幅减少{abs(limit_down_change_pct):.0f}%"

        # ==================== 3. 综合市场情绪判断 ====================
        # 综合判断逻辑：大盘走势 + 涨停家数 + 涨停趋势 + 跌停家数
        if avg_index_change > 2 and limit_up_count_today > 100:
            market_state = "HOT"
            sentiment_score = 90
            market_desc = "市场情绪火热，大盘大涨，涨停家数众多，赚钱效应强"
        elif avg_index_change > 1 and limit_up_count_today > 50:
            market_state = "WARM"
            sentiment_score = 70
            market_desc = "市场情绪温和，大盘上涨，涨停家数较多，赚钱效应一般"
        elif avg_index_change < -2 and limit_up_count_today < limit_up_count_yesterday * 0.5 and limit_down_count_today > 10:
            market_state = "COLD"
            sentiment_score = 30
            market_desc = "市场情绪冷淡，大盘大跌，涨停锐减，跌停增加，市场恐慌"
        elif avg_index_change < -1 and limit_up_count_today < 50:
            market_state = "NEUTRAL"
            sentiment_score = 45
            market_desc = "市场情绪中性偏弱，大盘下跌，涨停较少，赚钱效应弱"
        elif limit_up_count_today > 20:
            market_state = "NEUTRAL"
            sentiment_score = 50
            market_desc = "市场情绪中性，大盘震荡，涨停家数一般，赚钱效应一般"
        else:
            market_state = "COLD"
            sentiment_score = 35
            market_desc = "市场情绪低迷，涨停家数稀少，赚钱效应极弱"

        # ==================== 4. 热点题材分析 ====================
        hot_topics = []
        if limit_up_stocks_today:
            from src.utils.db_cache import get_db_cache
            db_cache = get_db_cache()
            concept_count = {}

            for stock in limit_up_stocks_today[:20]:
                stock_code = stock.get('stock_code')
                try:
                    concepts = db_cache.get_stock_concepts(stock_code)
                    for concept in concepts:
                        if concept:
                            concept_count[concept] = concept_count.get(concept, 0) + 1
                except Exception as e:
                    logger.warning(f"获取{stock_code}概念标签失败: {e}")
                    continue

            hot_topics = sorted(concept_count.items(), key=lambda x: x[1], reverse=True)[:5]

        # ==================== 5. 保存到数据库 ====================
        with db.get_session() as session:
            existing = session.query(MarketSentiment).filter_by(sentiment_date=today).first()

            if existing:
                existing.market_state = market_state.lower()
                existing.sentiment_score = sentiment_score
                existing.limit_up_count = limit_up_count_today
                existing.limit_down_count = limit_down_count_today
                existing.hot_topics = [{"topic": t[0], "count": t[1]} for t in hot_topics]
            else:
                sentiment = MarketSentiment(
                    sentiment_date=today,
                    market_state=market_state.lower(),
                    sentiment_score=sentiment_score,
                    limit_up_count=limit_up_count_today,
                    limit_down_count=limit_down_count_today,
                    hot_topics=[{"topic": t[0], "count": t[1]} for t in hot_topics]
                )
                session.add(sentiment)

            session.commit()

        # ==================== 6. 格式化输出 ====================
        hot_topics_str = ", ".join([f"{t[0]}({t[1]}只)" for t in hot_topics[:3]])

        return f"""
=== 市场情绪综合分析 ===

【大盘走势分析】
  上证指数: {shanghai_change:+.2f}% ({index_trend})
  深证成指: {shenzhen_change:+.2f}% ({index_trend})
  创业板指: {chinext_change:+.2f}% ({index_trend})
  大盘平均: {avg_index_change:+.2f}% ({index_trend})

【涨跌停数据】
  涨停家数: {limit_up_count_today}只 (昨日{limit_up_count_yesterday}只, {limit_up_trend})
  跌停家数: {limit_down_count_today}只 (昨日{limit_down_count_yesterday}只, {limit_down_trend})

【综合判断】
  市场情绪: {market_state}
  情绪评分: {sentiment_score}/100
  市场解读: {market_desc}

【热点题材】
  {hot_topics_str if hot_topics_str else '无明显热点'}

⚠️ 策略建议:
  {'激进策略为主（龙头战法、异常波动跟踪）' if market_state == 'HOT' else '稳健策略为主（低吸埋伏、题材轮动）' if market_state == 'WARM' else '稳健策略为主，激进策略为辅' if market_state == 'NEUTRAL' else '保守策略为主（防守反击、超跌反弹）'}
"""

    except Exception as e:
        logger.error(f"获取市场情绪失败: {e}", exc_info=True)
        return f"获取市场情绪失败: {str(e)}"


@tool("动态筛选候选股")
def dynamic_screen_stocks(
    price_change_min: float = -100,
    price_change_max: float = 100,
    turnover_min: float = 0,
    turnover_max: float = 100,
    volume_min: float = 0,
    amplitude_min: float = 0,
    sort_by: str = "price_change",
    max_results: int = 50,
    strength_ratio_min: float = 0.0,
    price_position_min: float = 0.0,
    price_velocity_min: float = 0.0,
    enable_strong_filter: bool = False,
    sectors: str = "",
    concepts: str = "",
    enable_news_filter: bool = False,
    news_hours: int = 24,
    max_market_cap: float = 0,
    min_market_cap: float = 0,
    max_price: float = 0,
    min_price: float = 0
) -> str:
    """
    根据动态条件从券商实时数据筛选候选股,只保留主板股票(600xxx, 000xxx, 001xxx)

    Args:
        sectors: 板块筛选（逗号分隔），例如："银行,地产,基建"
        concepts: 概念筛选（逗号分隔），例如："AI,算力,芯片"

    🔴 自动保存候选股到AgentContext，供多维分析师使用

    Args:
        price_change_min: 涨跌幅最小值(%)，默认-100
        price_change_max: 涨跌幅最大值(%)，默认100
        turnover_min: 换手率最小值(%)，默认0
        turnover_max: 换手率最大值(%)，默认100
        volume_min: 成交额最小值(亿)，默认0
        amplitude_min: 振幅最小值(%)，默认0
        sort_by: 排序字段(price_change/turnover/volume/amplitude/strength/position)，默认price_change
        max_results: 返回结果数量，默认20（支持更多候选股）
        strength_ratio_min: 强势度最小值(0-1)，默认0（不限制）。强势度=涨幅/振幅，>0.7为强势股
        price_position_min: 价格位置最小值(0-1)，默认0（不限制）。价格位置=(当前价-最低价)/(最高价-最低价)，>0.8为高位
        price_velocity_min: 涨速最小值(%/小时)，默认0（不限制）。涨速=涨幅/4小时，>1.0为快速拉升
        enable_strong_filter: 是否启用强势股过滤，默认False。True时自动过滤冲高回落的弱势股
        enable_news_filter: 是否启用新闻过滤，默认False。True时只保留有最近新闻的股票
        news_hours: 新闻时效性阈值（小时），默认24小时。只保留最近N小时内有新闻的股票
        max_market_cap: 最大流通市值（元），默认0（不限制）。例如：100000000000（1000亿）
        min_market_cap: 最小流通市值（元），默认0（不限制）。例如：10000000000（100亿）
        max_price: 最高价格（元），默认0（不限制）。例如：100.0（100元）
        min_price: 最低价格（元），默认0（不限制）。例如：5.0（5元）

    Returns:
        候选股列表(自然语言描述)
    """
    from src.agents.tools.context_tools import save_agent_context

    # 🚨 强制限制涨幅上限，避免涨停股（所有策略必须遵守）
    if price_change_max > 9.0:
        logger.warning(f"🚨🚨🚨 涨幅上限price_change_max={price_change_max}超过9%！强制修正为9%（避免涨停股9.5%）")
        price_change_max = 9.0

    try:

        # ✅ 使用券商数据源（最稳定）
        logger.info("开始获取券商实时数据...")

        try:
            all_stocks = _get_all_broker_data_with_names(main_board_only=True)
        except Exception as e:
            return f"获取券商实时数据失败: {str(e)}"

        if not all_stocks:
            return f"未获取到实时数据,建议稍后重试"

        # 只保留主板股票（上海600xxx、深圳000xxx）
        filtered = [
            s for s in all_stocks
            if (s.get('dm', '').startswith('60')  # 上海主板
                or s.get('dm', '').startswith('00'))  # 深圳主板
            and s.get('dm', '')  # 确保有股票代码
        ]

        # ✅ 第一步：基础筛选（涨幅、成交额、振幅、价格、市值）
        candidates = []
        filtered_count = 0
        strong_filter_count = 0
        price_filter_count = 0
        market_cap_filter_count = 0

        # ✅ 预加载流通股本数据（如果需要市值过滤）
        float_shares_cache = {}
        if max_market_cap > 0 or min_market_cap > 0:
            try:
                import sqlite3
                conn = sqlite3.connect('data/stock_trading.db')
                cursor = conn.cursor()
                cursor.execute("SELECT stock_code, float_shares FROM stock_basic_info WHERE float_shares IS NOT NULL")
                float_shares_cache = {row[0]: float(row[1]) for row in cursor.fetchall()}
                conn.close()
                logger.info(f"✅ 预加载{len(float_shares_cache)}只股票的流通股本数据")
            except Exception as e:
                logger.warning(f"⚠️ 预加载流通股本数据失败: {e}")

        for s in filtered:
            # ✅ 使用API原始字段名 (pc, cje, zf, p, tr等)
            pc = float(s.get('pc', 0))  # 涨跌幅
            cje = float(s.get('cje', 0))  # 成交额（元）
            zf = float(s.get('zf', 0))  # 振幅
            p = float(s.get('p', 0))  # 当前价
            tr = float(s.get('tr', 0))  # 换手率(API原始值)
            stock_code = s.get('dm', '')  # 股票代码

            # 基础条件
            if not (price_change_min <= pc <= price_change_max):
                continue
            if not (turnover_min <= tr <= turnover_max):
                continue
            if cje < volume_min * 100000000:  # 转换为元
                continue
            if zf < amplitude_min:
                continue

            # ✅ 价格过滤
            if max_price > 0 and p > max_price:
                price_filter_count += 1
                continue
            if min_price > 0 and p < min_price:
                price_filter_count += 1
                continue

            # ✅ 市值过滤
            if max_market_cap > 0 or min_market_cap > 0:
                # 优先使用数据库中的流通股本数据
                if stock_code in float_shares_cache:
                    float_shares = float_shares_cache[stock_code]
                    market_cap = float_shares * p  # 流通市值（元）
                    s['market_cap'] = market_cap  # 保存市值信息

                    if max_market_cap > 0 and market_cap > max_market_cap:
                        market_cap_filter_count += 1
                        continue
                    if min_market_cap > 0 and market_cap < min_market_cap:
                        market_cap_filter_count += 1
                        continue
                else:
                    # 🔴 如果数据库中没有流通股本数据，过滤掉该股票
                    # 理论上所有主板股票都应该有流通股本数据，如果没有说明数据不完整
                    logger.debug(f"⚠️ 股票{stock_code}没有流通股本数据，已过滤")
                    market_cap_filter_count += 1
                    continue

            filtered_count += 1

            # ✅ 第二步：计算新增指标
            # h = float(s.get('h', 0))  # 最高价
            # l = float(s.get('l', 0))  # 最低价
            # # p已经在前面定义过了,这里不需要重复
            # o = float(s.get('o', 0))  # 开盘价

            # 1. 强势度 = 价格位置（当前价在当日振幅中的位置）
            # 范围：0-1，越接近1越强势（收盘价接近最高价）
            # 例如：最低10元，最高20元，当前19元 → 强势度0.9（强势）
            #      最低10元，最高20元，当前11元 → 强势度0.1（弱势）
            # strength_ratio = ((p - l) / (h - l)) if (h - l) > 0 else 0.5
            # s['strength_ratio'] = round(strength_ratio, 3)

            # 2. 价格位置 = (当前价 - 最低价) / (最高价 - 最低价)（判断是否在高位）
            # 这个和强势度一样，保留是为了兼容性
            # price_position = strength_ratio
            # s['price_position'] = round(price_position, 3)

            # 3. 涨速 = 开盘后涨幅 / 交易时长（判断拉升速度）
            # 使用开盘价计算，更准确反映盘中拉升速度
            # A股交易时间：上午2小时 + 下午2小时 = 4小时
            # if o > 0:
            #     intraday_change = ((p - o) / o) * 100  # 开盘后涨幅（%）
            #     price_velocity = intraday_change / 4.0  # 每小时涨速（%/小时）
            # else:
            #     # 如果没有开盘价，降级使用涨幅/4
            #     price_velocity = pc / 4.0
            # s['price_velocity'] = round(price_velocity, 3)

            # ❌ 第三步：新增指标筛选（已禁用）
            # 这些条件对下跌股和震荡股过于严格,容易导致筛选结果为0
            # if strength_ratio < strength_ratio_min:
            #     continue
            # if price_position < price_position_min:
            #     continue
            # if price_velocity < price_velocity_min:
            #     continue

            # ❌ 第四步：强势股过滤（已禁用）
            # 这个条件要求强势度>=0.6且价格位置>=0.7,太严格了
            # if enable_strong_filter:
            #     # 强势股标准：强势度>0.6 且 价格位置>0.7
            #     if strength_ratio < 0.6 or price_position < 0.7:
            #         strong_filter_count += 1
            #         continue

            candidates.append(s)

        # 日志输出筛选统计
        if enable_strong_filter:
            logger.info(f"✅ 强势股过滤：基础筛选{filtered_count}只 → 过滤掉{strong_filter_count}只弱势股 → 剩余{len(candidates)}只")
        else:
            logger.info(f"✅ 基础筛选：{len(candidates)}只候选股")

        # ✅ 第五步：板块筛选（如果指定了板块或概念）- 智能匹配 + 实时API查询
        if sectors or concepts:
            logger.info(f"🔍 开始板块筛选：sectors={sectors}, concepts={concepts}")
            filtered_by_sector = []
            sector_filter_count = 0
            api_query_count = 0

            # 解析板块和概念列表
            sector_list = [s.strip() for s in sectors.split(',') if s.strip()] if sectors else []
            concept_list = [c.strip() for c in concepts.split(',') if c.strip()] if concepts else []
            all_user_concepts = sector_list + concept_list

            # 使用数据库中的板块数据
            from src.database.db_manager import DatabaseManager
            from src.database.models import StockConcepts

            db_manager = DatabaseManager()
            with db_manager.get_session() as db:
                # 🔴 批量查询所有候选股的板块信息（性能优化）
                stock_codes = [s.get('dm', '') for s in candidates if s.get('dm')]
                all_concepts = db.query(StockConcepts).filter(
                    StockConcepts.stock_code.in_(stock_codes)
                ).all()

                # 构建股票代码 -> 标签的映射
                stock_tags_map: Dict[str, str] = {}
                for c in all_concepts:
                    if c.stock_code not in stock_tags_map:
                        stock_tags_map[c.stock_code] = c.tag
                    else:
                        stock_tags_map[c.stock_code] += ' ' + c.tag

                for stock in candidates:
                    stock_code = stock.get('dm', '')
                    if not stock_code:
                        continue

                    try:
                        # 🔴 新逻辑：优先本地缓存，否则调用智兔API
                        stock_concepts = _get_stock_concepts(stock_code, stock_tags_map)

                        if not stock_concepts:
                            # 没有概念数据，尝试从API获取
                            api_query_count += 1
                            stock_concepts = _get_stock_concepts_from_api(stock_code)

                        if not stock_concepts:
                            # 仍然没有数据，跳过
                            sector_filter_count += 1
                            continue

                        # 🔴 使用简单匹配（子串 + 别名）
                        is_matched, matched_concept = _stock_matches_concepts_simple(
                            stock_concepts, all_user_concepts
                        )

                        if is_matched:
                            filtered_by_sector.append(stock)
                            stock['matched_concept'] = matched_concept
                            logger.debug(f"✅ {stock_code} 匹配概念: {matched_concept}, 概念列表: {stock_concepts[:5]}")
                        else:
                            sector_filter_count += 1
                            logger.debug(f"❌ {stock_code} 未匹配, 概念列表: {stock_concepts[:5]}")

                    except Exception as e:
                        logger.warning(f"⚠️ 匹配{stock_code}板块信息失败: {e}")
                        # 如果匹配失败，保留该股票（避免过度过滤）
                        filtered_by_sector.append(stock)

            logger.info(f"✅ 板块筛选：{len(candidates)}只 → 过滤掉{sector_filter_count}只 → 剩余{len(filtered_by_sector)}只 (API查询{api_query_count}次)")
            candidates = filtered_by_sector

        # ✅ 第六步：新闻过滤（如果启用）
        if enable_news_filter:
            from src.tools.news_source_manager import NewsSourceManager
            from src.tools.google_news_rss import GoogleNewsRSS

            logger.info(f"🔍 开始新闻过滤（时效性：最近{news_hours}小时）...")
            news_manager = NewsSourceManager()
            google_news = GoogleNewsRSS()

            filtered_by_news = []
            news_filter_count = 0
            stocks_with_news = {}  # 记录有新闻的股票及其新闻数量

            for stock in candidates:
                stock_code = stock.get('dm', '')
                stock_name = stock.get('name', '')

                if not stock_code or not stock_name:
                    continue

                # 获取股票相关新闻
                try:
                    news_list = google_news.get_news(query=f"{stock_name} {stock_code}", limit=5)

                    # 过滤时效性新闻
                    recent_news = []
                    for news in news_list:
                        if news_manager.is_recent_news(news, hours=news_hours):
                            recent_news.append(news)

                    # 如果有最近新闻，保留该股票
                    if len(recent_news) > 0:
                        filtered_by_news.append(stock)
                        stocks_with_news[stock_code] = len(recent_news)
                        logger.debug(f"  ✅ {stock_name}({stock_code}): {len(recent_news)}条最近新闻")
                    else:
                        news_filter_count += 1
                        logger.debug(f"  ❌ {stock_name}({stock_code}): 无最近{news_hours}小时新闻")

                except Exception as e:
                    logger.warning(f"  ⚠️ 获取{stock_name}({stock_code})新闻失败: {e}，保留该股票")
                    filtered_by_news.append(stock)  # 获取失败时保留股票

            logger.info(f"✅ 新闻过滤：{len(candidates)}只 → 过滤掉{news_filter_count}只无新闻股票 → 剩余{len(filtered_by_news)}只")
            logger.info(f"   有新闻的股票: {', '.join([f'{code}({count}条)' for code, count in stocks_with_news.items()])}")
            candidates = filtered_by_news

        # 根据排序字段排序
        if sort_by == 'turnover':
            # ✅ 使用准确的换手率排序（已通过流通股本计算）
            sort_key = 'turnover_rate'
        elif sort_by == 'strength':
            sort_key = 'strength_ratio'
        elif sort_by == 'position':
            sort_key = 'price_position'
        else:
            sort_key_map = {
                'price_change': 'pc',  # 涨跌幅
                'volume': 'cje',       # 成交额
                'amplitude': 'zf'      # 振幅
            }
            sort_key = sort_key_map.get(sort_by, 'pc')

        # 排序并取前max_results个
        candidates = sorted(
            candidates,
            key=lambda x: float(x.get(sort_key, 0)),
            reverse=True
        )[:max_results]

        if not candidates:
            filter_msg = f"涨幅{price_change_min}%-{price_change_max}%"
            if max_price > 0 or min_price > 0:
                filter_msg += f"，价格{min_price if min_price > 0 else '不限'}-{max_price if max_price > 0 else '不限'}元"
            if max_market_cap > 0 or min_market_cap > 0:
                filter_msg += f"，市值{min_market_cap/100000000 if min_market_cap > 0 else '不限'}-{max_market_cap/100000000 if max_market_cap > 0 else '不限'}亿"
            return f"未找到符合条件的候选股（{filter_msg}）\n过滤统计：价格过滤{price_filter_count}只，市值过滤{market_cap_filter_count}只"

        # 🔴 构建候选股列表（用于保存到AgentContext）
        candidate_stocks = []
        for stock in candidates:
            code = stock.get('dm', 'N/A')
            name = stock.get('name', 'N/A')
            current_price = float(stock.get('zxj', 0))  # 最新价
            price_change = float(stock.get('pc', 0))
            turnover_rate = stock.get('turnover_rate', 0)
            volume_yuan = float(stock.get('cje', 0))
            volume = volume_yuan / 100000000  # 转换为亿
            amplitude = float(stock.get('zf', 0))

            # ✅ 新增指标
            strength_ratio = stock.get('strength_ratio', 0)
            price_position = stock.get('price_position', 0)
            price_velocity = stock.get('price_velocity', 0)

            candidate_stocks.append({
                'code': code,
                'name': name,
                'current_price': current_price,
                'price_change': price_change,
                'turnover_rate': turnover_rate,
                'volume': volume,
                'amplitude': amplitude,
                'strength_ratio': strength_ratio,
                'price_position': price_position,
                'price_velocity': price_velocity
            })

        # 🔴 保存候选股到AgentContext（使用.func()调用Tool）
        try:
            screening_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_result = save_agent_context.func(
                context_type='candidate_stocks',
                context_data={
                    'stocks': candidate_stocks,
                    'count': len(candidate_stocks),
                    'screening_time': screening_time
                }
            )
            logger.info(f"✅ {save_result}")
        except Exception as e:
            logger.error(f"❌ 保存候选股到AgentContext失败: {e}")

        # 格式化输出
        result_lines = [f"=== 候选股票（共{len(candidates)}只）===\n"]
        for i, stock in enumerate(candidates, 1):
            name = stock.get('name', 'N/A')  # 券商数据使用'name'字段
            code = stock.get('dm', 'N/A')
            price_change = float(stock.get('pc', 0))
            volume_yuan = float(stock.get('cje', 0))  # 成交额（元）
            volume = volume_yuan / 100000000  # 转换为亿
            amplitude = float(stock.get('zf', 0))

            # ✅ 新增指标
            strength_ratio = stock.get('strength_ratio', 0)
            price_position = stock.get('price_position', 0)
            price_velocity = stock.get('price_velocity', 0)

            # ✅ 使用计算后的换手率（优先）或API返回的换手率
            turnover = stock.get('turnover_rate', 0)
            if turnover and turnover > 0:
                turnover_str = f"{turnover:.2f}%"
            else:
                turnover_str = "N/A"

            # ✅ 板块信息
            sector_info = ""
            if stock.get('matched_sector'):
                sector_info = f" - 板块:{stock.get('matched_sector')}"
            elif stock.get('matched_concept'):
                sector_info = f" - 概念:{stock.get('matched_concept')}"

            # ✅ 市值信息
            market_cap_info = ""
            if stock.get('market_cap'):
                market_cap_info = f" - 市值{stock.get('market_cap')/100000000:.2f}亿"

            # ✅ 价格信息
            current_price = float(stock.get('p', 0))
            price_info = f" - 价格{current_price:.2f}元"

            result_lines.append(
                f"{i}. {name}({code}){price_info}{market_cap_info} - "
                f"涨幅{price_change:.2f}% - "
                f"换手{turnover_str} - "
                f"成交{volume:.2f}亿 - "
                f"振幅{amplitude:.2f}% - "
                f"强势度{strength_ratio:.2f}"
                f"{sector_info} - "
                f"价格位置{price_position:.2f} - "
                f"涨速{price_velocity:.2f}%/h"
            )

        result_lines.append(f"\n筛选条件: 涨幅{price_change_min}%-{price_change_max}%, 成交额≥{volume_min}亿, 振幅≥{amplitude_min}%")
        if max_price > 0 or min_price > 0:
            result_lines.append(f"价格范围: {min_price if min_price > 0 else '不限'}-{max_price if max_price > 0 else '不限'}元")
        if max_market_cap > 0 or min_market_cap > 0:
            result_lines.append(f"市值范围: {min_market_cap/100000000 if min_market_cap > 0 else '不限'}-{max_market_cap/100000000 if max_market_cap > 0 else '不限'}亿")
        if strength_ratio_min > 0:
            result_lines.append(f"强势度≥{strength_ratio_min}")
        if price_position_min > 0:
            result_lines.append(f"价格位置≥{price_position_min}")
        if price_velocity_min > 0:
            result_lines.append(f"涨速≥{price_velocity_min}%/h")
        if enable_strong_filter:
            result_lines.append(f"✅ 已启用强势股过滤（过滤掉{strong_filter_count}只冲高回落的弱势股）")
        if price_filter_count > 0 or market_cap_filter_count > 0:
            result_lines.append(f"过滤统计: 价格过滤{price_filter_count}只，市值过滤{market_cap_filter_count}只")
        result_lines.append(f"排序方式: {sort_by}")
        result_lines.append(f"\n✅ 已保存{len(candidate_stocks)}只候选股到AgentContext")

        return "\n".join(result_lines)

    except Exception as e:
        return f"筛选候选股失败: {str(e)}"

def _get_all_broker_data_with_names(main_board_only: bool = True) -> List[Dict[str, Any]]:
    """
    获取券商实时数据并映射股票名称，使用数据库流通股本计算准确换手率

    Args:
        main_board_only: 是否只获取主板数据（默认True）
                        True: 只获取主板（沪市600/601/603 + 深市000/001）约2000只，速度快
                        False: 获取全市场（包括创业板/科创板/北交所）约5000只，速度慢

    Returns:
        包含股票名称和准确换手率的券商实时数据列表
    """
    from src.tools.zhitu_api import ZhituAPI
    import sqlite3
    from pathlib import Path

    try:
        zhitu = ZhituAPI()

        # 直接获取原始API数据，不经过字段映射
        data = zhitu._make_request('real_time_all_broker')

        if not data:
            return []

        # ✅ 如果只要主板数据，过滤掉创业板/科创板/北交所
        if main_board_only:
            original_count = len(data)
            data = [
                stock for stock in data
                if stock.get('dm', '').startswith(('600', '601', '603', '000', '001'))
            ]
            logger.info(f"✅ 主板筛选：{original_count}只 → {len(data)}只（过滤掉{original_count - len(data)}只非主板股票）")

        # 获取股票基本信息用于名称映射
        stock_info = zhitu.get_stock_list()
        if not stock_info:
            stock_info = []

        # 创建股票代码到名称的映射（处理带后缀的代码格式）
        name_mapping = {}
        for stock in stock_info:
            code = stock.get('stock_code', '')
            name = stock.get('stock_name', '')
            if code and name:
                # 存储完整代码（如 000001.SZ）
                name_mapping[code] = name
                # 同时存储纯数字代码（如 000001）
                clean_code = code.split('.')[0]  # 去掉 .SZ/.SH 后缀
                name_mapping[clean_code] = name

        # ✅ 从数据库缓存获取流通股本数据
        from src.utils.db_cache import get_db_cache

        db_cache = get_db_cache()
        float_shares_mapping = db_cache.get_all_float_shares()

        # ✅ 为每只股票添加名称和计算准确换手率
        accurate_count = 0
        fallback_count = 0

        for stock in data:
            stock_code = stock.get('dm', '')

            # 添加股票名称
            if stock_code in name_mapping:
                stock['name'] = name_mapping[stock_code]
            else:
                stock['name'] = stock_code  # 如果找不到名称，使用股票代码

            # ✅ 计算准确换手率
            # 优先使用API返回的成交量（股）pv字段，更准确（包含零股交易）
            volume_shares = stock.get('pv', 0)  # 成交量（股）- API直接返回
            if volume_shares == 0:
                # 降级方案1：使用成交量（手）计算
                volume_hands = stock.get('v', 0)
                volume_shares = volume_hands * 100 if volume_hands > 0 else 0

            float_shares = float_shares_mapping.get(stock_code, 0)  # 流通股本（股）

            if float_shares and float_shares > 0 and volume_shares > 0:
                # 手动计算准确换手率：(成交量(股) / 流通股本(股)) × 100%
                turnover_rate = (volume_shares / float_shares) * 100
                stock['turnover_rate'] = round(turnover_rate, 2)
                accurate_count += 1
            else:
                # 降级方案2：使用API返回的换手率（只有部分股票有）
                stock['turnover_rate'] = stock.get('tr', 0) or stock.get('hs', 0)
                fallback_count += 1

        logger.info(f"✅ 成功处理{len(data)}只股票的数据")
        logger.info(f"   准确计算: {accurate_count}只 | API降级: {fallback_count}只")
        return data

    except Exception as e:
        print(f"获取券商数据失败: {str(e)}")
        return []


@tool("批量获取实时价格")
def get_realtime_prices(stock_codes: str) -> str:
    """
    批量获取股票的实时价格（券商数据源，实时更新）

    Args:
        stock_codes: 股票代码列表，用逗号分隔，例如'600000,000001,600519'，最多20只

    Returns:
        实时价格数据
    """
    from src.tools.zhitu_api import ZhituAPI

    try:
        zhitu = ZhituAPI()

        # 分割股票代码
        codes = [code.strip() for code in stock_codes.split(',') if code.strip()]

        if len(codes) == 0:
            return "错误：未提供股票代码"

        if len(codes) > 20:
            return f"错误：最多支持20只股票，当前提供了{len(codes)}只"

        # ✅ 调用券商实时价格接口（实时更新）
        # 使用 get_real_time_multi_broker 方法，返回字典格式
        prices_data = zhitu.get_real_time_multi_broker(codes)

        if not prices_data or len(prices_data) == 0:
            return "未获取到实时价格数据"

        # 格式化输出
        output = [f"=== 实时价格（券商数据源，{len(prices_data)}只股票）===\n"]

        for i, code in enumerate(codes, 1):
            stock = prices_data.get(code, {})
            if not stock:
                output.append(f"{i}. {code} - 未获取到数据")
                continue

            # ✅ 修复：字段名已经被映射，优先使用映射后的字段名
            price = stock.get('current_price') or stock.get('p', 0)  # 最新价
            price_change = stock.get('change_pct') or stock.get('pc', 0)  # 涨跌幅
            volume_yuan = stock.get('turnover_amount') or stock.get('cje', 0)  # 成交额（元）
            volume = volume_yuan / 100000000 if volume_yuan else 0  # 转换为亿
            update_time = stock.get('update_time') or stock.get('t', 'N/A')  # 更新时间

            # ✅ 直接使用券商数据的换手率（避免逐个请求流通股本）
            turnover = stock.get('turnover_rate') or stock.get('tr', 0)

            output.append(
                f"{i}. {code} - "
                f"价格{price:.2f}元 - "
                f"涨幅{price_change:.2f}% - "
                f"成交{volume:.2f}亿 - "
                f"换手{turnover:.2f}% - "
                f"更新{update_time}"
            )

        return "\n".join(output)

    except Exception as e:
        logger.error(f"批量获取实时价格失败: {e}")
        return f"批量获取实时价格失败: {str(e)}"


@tool("获取股票技术指标")
def get_technical_indicators(stock_code: str) -> str:
    """
    获取股票的完整技术指标(MACD、KDJ、BOLL、MA等)

    Args:
        stock_code: 股票代码,如'600000'

    Returns:
        完整的技术指标数据（不含评分，让AI自己分析）
    """
    from src.tools.zhitu_api import ZhituAPI

    try:
        zhitu = ZhituAPI()

        # 转换股票代码格式(智兔API需要带市场后缀)
        if stock_code.startswith('6'):
            symbol = f"{stock_code}.SH"
        else:
            symbol = f"{stock_code}.SZ"

        # 获取多个技术指标
        indicators_data = {}

        # 1. MACD
        try:
            macd_data = zhitu.get_history_macd(symbol, 'd', 'n', latest_count=5)
            if macd_data and len(macd_data) > 0:
                indicators_data['macd'] = macd_data[-5:]  # 最近5天
        except Exception as e:
            logger.warning(f"获取MACD失败: {e}")
            indicators_data['macd'] = None

        # 2. KDJ
        try:
            # ✅ 取更多数据，避免最近几天都是null
            kdj_data = zhitu.get_history_kdj(symbol, 'd', 'n', latest_count=20)
            if kdj_data and len(kdj_data) > 0:
                # 过滤出有效数据（非null）
                valid_data = [item for item in kdj_data if item.get('k') is not None]
                if valid_data:
                    indicators_data['kdj'] = valid_data[-5:]  # 最近5个有效数据
                else:
                    indicators_data['kdj'] = None
            else:
                indicators_data['kdj'] = None
        except Exception as e:
            logger.warning(f"获取KDJ失败: {e}")
            indicators_data['kdj'] = None

        # 3. BOLL
        try:
            # ✅ 取更多数据，避免最近几天都是null
            boll_data = zhitu.get_history_boll(symbol, 'd', 'n', latest_count=20)
            if boll_data and len(boll_data) > 0:
                # 过滤出有效数据（非null）
                valid_data = [item for item in boll_data if item.get('u') is not None]
                if valid_data:
                    indicators_data['boll'] = valid_data[-5:]  # 最近5个有效数据
                else:
                    indicators_data['boll'] = None
            else:
                indicators_data['boll'] = None
        except Exception as e:
            logger.warning(f"获取BOLL失败: {e}")
            indicators_data['boll'] = None

        # 4. MA均线
        try:
            # ✅ 取更多数据，避免最近几天都是null
            ma_data = zhitu.get_history_ma(symbol, 'd', 'n', latest_count=20)
            if ma_data and len(ma_data) > 0:
                # 过滤出有效数据（非null）
                valid_data = [item for item in ma_data if item.get('ma5') is not None]
                if valid_data:
                    indicators_data['ma'] = valid_data[-5:]  # 最近5个有效数据
                else:
                    indicators_data['ma'] = None
            else:
                indicators_data['ma'] = None
        except Exception as e:
            logger.warning(f"获取MA失败: {e}")
            indicators_data['ma'] = None

        # 5. 获取当前价格（用于对比）
        try:
            from src.tools.data_source_manager import DataSourceManager
            dsm = DataSourceManager()
            real_data = dsm.get_real_time_data_sync(stock_code)
            current_price = real_data.get('current_price', 0) if real_data else 0
        except Exception:
            current_price = 0

        # 6. ✅ 新增：获取多周期K线数据（分钟级+日线级，全面覆盖超短线到中期）
        kline_data_dict = {}
        try:
            from datetime import datetime, timedelta

            # ✅ 优化：减少周期数量，避免超时（从9个减少到5个）
            timeframes = {
                # 分钟级别（超短线交易）- 只保留关键周期
                '60': 100,   # 60分钟K线，最近100根（约5个交易日）
                '15': 100,   # 15分钟K线，最近100根（约1.2个交易日）
                '5': 100,    # 5分钟K线，最近100根（约2个交易日）

                # 日线级别（短中期趋势）- 只保留关键周期
                'd_15': 15,  # 日K线，最近15天（短期）
                'd_60': 60,  # 日K线，最近60天（中期）
            }

            # 获取多个周期的K线数据
            for tf_key, limit in timeframes.items():
                try:
                    # 判断是日线还是分钟线
                    if tf_key.startswith('d_'):
                        # 日线：使用get_history_timeframe获取历史数据
                        tf = 'd'
                        # 计算时间范围（向前推limit*2天，确保有足够数据）
                        end_time = datetime.now().strftime('%Y%m%d')
                        start_time = (datetime.now() - timedelta(days=limit*2)).strftime('%Y%m%d')

                        kline = zhitu.get_history_timeframe(
                            stock_symbol=symbol,
                            timeframe=tf,
                            adjust_type='n',
                            start_time=start_time,
                            end_time=end_time
                        )
                        # 只取最近limit条
                        if kline and len(kline) > limit:
                            kline = kline[-limit:]
                    else:
                        # 分钟线：先尝试get_latest_timeframe
                        tf = tf_key
                        kline = zhitu.get_latest_timeframe(
                            stock_symbol=symbol,
                            timeframe=tf,
                            adjust_type='n',
                            limit=limit
                        )

                        # ✅ 如果数据不足（<10条），使用get_history_timeframe获取历史数据
                        if not kline or len(kline) < 10:
                            logger.debug(f"{tf_key}K线数据不足({len(kline) if kline else 0}条)，尝试获取历史数据")
                            # 计算时间范围（向前推10天，确保有足够数据）
                            end_time = datetime.now().strftime('%Y%m%d')
                            start_time = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')

                            kline = zhitu.get_history_timeframe(
                                stock_symbol=symbol,
                                timeframe=tf,
                                adjust_type='n',
                                start_time=start_time,
                                end_time=end_time
                            )
                            # 只取最近limit条
                            if kline and len(kline) > limit:
                                kline = kline[-limit:]

                    if kline and len(kline) > 0:
                        kline_data_dict[tf_key] = kline
                        logger.debug(f"获取{tf_key}K线成功: {len(kline)}条")
                    else:
                        logger.debug(f"{tf_key}K线数据为空")
                except Exception as e:
                    # ✅ 增强错误日志
                    import traceback
                    logger.debug(f"获取{tf_key}K线失败: {e}")
                    logger.debug(f"详细错误:\n{traceback.format_exc()}")

            if not kline_data_dict:
                logger.warning(f"所有周期K线数据获取失败")

        except Exception as e:
            logger.warning(f"获取K线数据失败: {e}")

        # 格式化输出
        output = [f"=== {stock_code} 完整技术指标 + K线形态分析 ===\n"]

        # MACD
        if indicators_data.get('macd'):
            latest = indicators_data['macd'][-1]
            prev = indicators_data['macd'][-2] if len(indicators_data['macd']) > 1 else None

            # 安全获取数值，确保不是None
            dif = latest.get('diff') or 0
            dea = latest.get('dea') or 0
            macd = latest.get('macd') or 0

            output.append("【MACD指标】")
            output.append(f"  DIF: {dif:.4f}")
            output.append(f"  DEA: {dea:.4f}")
            output.append(f"  MACD: {macd:.4f}")
            output.append(f"  当前状态: {'金叉' if dif > dea else '死叉'}")

            if prev:
                prev_dif = prev.get('diff') or 0
                prev_dea = prev.get('dea') or 0
                if prev_dif <= prev_dea and dif > dea:
                    output.append(f"  ⚡ 刚刚金叉（前一天死叉）")
                elif prev_dif >= prev_dea and dif < dea:
                    output.append(f"  ⚠️ 刚刚死叉（前一天金叉）")
            output.append("")

        # KDJ
        if indicators_data.get('kdj'):
            latest = indicators_data['kdj'][-1]

            # ✅ 修复：检查是否为null
            k = latest.get('k')
            d = latest.get('d')
            j = latest.get('j')

            output.append("【KDJ指标】")
            if k is not None and d is not None and j is not None:
                output.append(f"  K值: {k:.2f}")
                output.append(f"  D值: {d:.2f}")
                output.append(f"  J值: {j:.2f}")

                if j > 80:
                    output.append(f"  状态: 超买区（J={j:.0f}>80）")
                elif j < 20:
                    output.append(f"  状态: 超卖区（J={j:.0f}<20）")
                else:
                    output.append(f"  状态: 正常区间")
            else:
                output.append(f"  ⚠️ 数据暂无（非交易时间或数据未更新）")
            output.append("")

        # BOLL
        if indicators_data.get('boll'):
            latest = indicators_data['boll'][-1]

            # ✅ 修复：检查是否为null
            upper = latest.get('u')
            middle = latest.get('m')
            lower = latest.get('d')

            output.append("【BOLL指标】")
            if upper is not None and middle is not None and lower is not None:
                output.append(f"  上轨: {upper:.2f}")
                output.append(f"  中轨: {middle:.2f}")
                output.append(f"  下轨: {lower:.2f}")

                if current_price > 0:
                    output.append(f"  当前价: {current_price:.2f}")
                    if current_price > upper:
                        output.append(f"  位置: 突破上轨（超买）")
                    elif current_price < lower:
                        output.append(f"  位置: 跌破下轨（超卖）")
                    elif current_price > middle:
                        output.append(f"  位置: 中轨上方（偏强）")
                    else:
                        output.append(f"  位置: 中轨下方（偏弱）")
            else:
                output.append(f"  ⚠️ 数据暂无（非交易时间或数据未更新）")
            output.append("")

        # MA均线
        if indicators_data.get('ma'):
            latest = indicators_data['ma'][-1]

            # ✅ 修复：检查是否为null
            ma5 = latest.get('ma5')
            ma10 = latest.get('ma10')
            ma20 = latest.get('ma20')
            ma60 = latest.get('ma60')

            output.append("【MA均线】")
            if ma5 is not None:
                output.append(f"  MA5: {ma5:.2f}")
                output.append(f"  MA10: {ma10:.2f}" if ma10 is not None else "  MA10: N/A")
                output.append(f"  MA20: {ma20:.2f}" if ma20 is not None else "  MA20: N/A")
                output.append(f"  MA60: {ma60:.2f}" if ma60 is not None else "  MA60: N/A")

                if current_price > 0 and ma10 is not None and ma20 is not None:
                    output.append(f"  当前价: {current_price:.2f}")
                    if current_price > ma5 > ma10 > ma20:
                        output.append(f"  均线排列: 多头排列（强势）")
                    elif current_price < ma5 < ma10 < ma20:
                        output.append(f"  均线排列: 空头排列（弱势）")
                    else:
                        output.append(f"  均线排列: 混乱（震荡）")
            else:
                output.append(f"  ⚠️ 数据暂无（非交易时间或数据未更新）")
            output.append("")

        # ✅ 新增：多周期K线形态分析（分钟级+日线级）
        if kline_data_dict:
            output.append("【多周期K线形态分析】")

            # 定义周期显示名称
            timeframe_names = {
                '1': '1分钟',
                '5': '5分钟',
                '15': '15分钟',
                '30': '30分钟',
                '60': '60分钟',
                'd_5': '5日',
                'd_15': '15日',
                'd_30': '30日',
                'd_60': '60日'
            }

            # 按周期分析（从大周期到小周期）
            analysis_order = ['d_60', 'd_30', 'd_15', 'd_5', '60', '30', '15', '5', '1']

            for tf_key in analysis_order:
                if tf_key not in kline_data_dict:
                    continue

                kline_data = kline_data_dict[tf_key]
                if not kline_data or len(kline_data) < 3:
                    continue

                tf_name = timeframe_names.get(tf_key, tf_key)
                output.append(f"\n  【{tf_name}周期】")

                # 获取最近的K线数据
                latest = kline_data[-1]
                prev_1 = kline_data[-2] if len(kline_data) > 1 else None
                prev_2 = kline_data[-3] if len(kline_data) > 2 else None

                # 1. 趋势分析
                if len(kline_data) >= 10:
                    close_prices = [k.get('c', 0) for k in kline_data[-10:]]
                    up_count = sum(1 for i in range(1, len(close_prices)) if close_prices[i] > close_prices[i-1])
                    down_count = sum(1 for i in range(1, len(close_prices)) if close_prices[i] < close_prices[i-1])

                    # 计算涨跌幅
                    first_price = close_prices[0]
                    last_price = close_prices[-1]
                    change_pct = (last_price - first_price) / first_price * 100 if first_price > 0 else 0

                    if up_count >= 7:
                        trend = "强势上升"
                    elif up_count >= 5:
                        trend = "上升"
                    elif down_count >= 7:
                        trend = "强势下降"
                    elif down_count >= 5:
                        trend = "下降"
                    else:
                        trend = "横盘震荡"

                    output.append(f"    趋势: {trend}（{up_count}涨{down_count}跌，涨跌幅{change_pct:+.1f}%）")

                # 2. 支撑位和压力位
                if len(kline_data) >= 20:
                    high_prices = [k.get('h', 0) for k in kline_data[-20:]]
                    low_prices = [k.get('l', 0) for k in kline_data[-20:]]

                    resistance = max(high_prices)
                    support = min(low_prices)

                    output.append(f"    压力位: {resistance:.2f}, 支撑位: {support:.2f}")

                    # 当前价格位置
                    if current_price > 0:
                        price_range = resistance - support
                        if price_range > 0:
                            position_pct = (current_price - support) / price_range * 100
                            output.append(f"    当前价格: {current_price:.2f}（区间{position_pct:.1f}%位置）")


                # 3. K线形态识别
                if prev_1 and prev_2:
                    patterns = []

                    # 获取K线数据
                    latest_close = latest.get('c', 0)
                    latest_open = latest.get('o', 0)
                    latest_high = latest.get('h', 0)
                    latest_low = latest.get('l', 0)

                    prev_1_close = prev_1.get('c', 0)
                    prev_1_open = prev_1.get('o', 0)

                    prev_2_close = prev_2.get('c', 0)

                    # 阳线/阴线
                    is_yang = latest_close > latest_open

                    # 实体大小
                    total_range = latest_high - latest_low
                    body_size = abs(latest_close - latest_open)
                    upper_shadow = latest_high - max(latest_close, latest_open)
                    lower_shadow = min(latest_close, latest_open) - latest_low

                    # 形态1：大阳线/大阴线
                    if total_range > 0 and body_size > total_range * 0.7:
                        if is_yang:
                            patterns.append("大阳线")
                        else:
                            patterns.append("大阴线")

                    # 形态2：十字星
                    elif total_range > 0 and body_size < total_range * 0.1:
                        patterns.append("十字星")

                    # 形态3：锤子线/倒锤子线
                    elif lower_shadow > body_size * 2 and upper_shadow < body_size * 0.5:
                        patterns.append("锤子线")
                    elif upper_shadow > body_size * 2 and lower_shadow < body_size * 0.5:
                        patterns.append("倒锤子线")

                    # 形态4：连续上涨/下跌
                    if latest_close > prev_1_close > prev_2_close:
                        patterns.append("三连阳")
                    elif latest_close < prev_1_close < prev_2_close:
                        patterns.append("三连阴")

                    # 形态5：突破/跌破
                    if len(kline_data) >= 20:
                        recent_highs = [k.get('h', 0) for k in kline_data[-20:-1]]
                        recent_lows = [k.get('l', 0) for k in kline_data[-20:-1]]

                        if latest_high > max(recent_highs):
                            patterns.append("突破新高")
                        if latest_low < min(recent_lows):
                            patterns.append("跌破新低")

                    if patterns:
                        output.append(f"    形态: {', '.join(patterns)}")

            output.append("")

        output.append("💡 提示: 请综合分析以上指标和K线形态，不要简单判断金叉/死叉好坏")
        output.append("      考虑市场环境、趋势强度、多个指标共振、K线形态等因素")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"获取技术指标失败: {e}")
        return f"获取{stock_code}技术指标失败: {str(e)}"


@tool("获取股票资金流向")
def get_fund_flow(stock_code: str) -> str:
    """
    获取股票的资金流向数据（主力资金、大单、中单、小单）

    Args:
        stock_code: 股票代码

    Returns:
        资金流向描述
    """
    from src.tools.zhitu_api import ZhituAPI

    try:
        zhitu = ZhituAPI()

        # ✅ 调用历史资金流向API，获取最新1条数据
        fund_flow_data = zhitu.get_fund_flow(stock_code, latest_count=1)

        if not fund_flow_data or len(fund_flow_data) == 0:
            return f"=== {stock_code} 资金流向 ===\n\n⚠️ 暂无资金流向数据"

        # 获取最新一条数据
        latest = fund_flow_data[0]

        # ✅ 提取正确的字段（根据API实际返回）
        # 主买（流入）
        zmbtdcje = latest.get('zmbtdcje', 0)  # 主买特大单成交额
        zmbddcje = latest.get('zmbddcje', 0)  # 主买大单成交额
        zmbzdcje = latest.get('zmbzdcje', 0)  # 主买中单成交额
        zmbxdcje = latest.get('zmbxdcje', 0)  # 主买小单成交额

        # 主卖（流出）
        zmstdcje = latest.get('zmstdcje', 0)  # 主卖特大单成交额
        zmsddcje = latest.get('zmsddcje', 0)  # 主卖大单成交额
        zmszdcje = latest.get('zmszdcje', 0)  # 主卖中单成交额
        zmsxdcje = latest.get('zmsxdcje', 0)  # 主卖小单成交额

        # ✅ 计算净流入（主买 - 主卖）
        super_net_inflow = zmbtdcje - zmstdcje  # 超大单净流入
        big_net_inflow = zmbddcje - zmsddcje    # 大单净流入
        mid_net_inflow = zmbzdcje - zmszdcje    # 中单净流入
        small_net_inflow = zmbxdcje - zmsxdcje  # 小单净流入

        # 主力资金净流入（超大单+大单）
        main_net_inflow = super_net_inflow + big_net_inflow

        # 转换为万元
        main_net_inflow_wan = main_net_inflow / 10000
        super_inflow_wan = super_net_inflow / 10000
        big_inflow_wan = big_net_inflow / 10000
        mid_inflow_wan = mid_net_inflow / 10000
        small_inflow_wan = small_net_inflow / 10000

        # 判断资金流向
        if main_net_inflow > 0:
            flow_direction = "主力资金净流入"
        elif main_net_inflow < 0:
            flow_direction = "主力资金净流出"
        else:
            flow_direction = "主力资金持平"

        return f"""
=== {stock_code} 资金流向 ===

主力资金净流入: {main_net_inflow_wan:.2f}万元
  - 超大单净流入: {super_inflow_wan:.2f}万元
  - 大单净流入: {big_inflow_wan:.2f}万元

散户资金:
  - 中单净流入: {mid_inflow_wan:.2f}万元
  - 小单净流入: {small_inflow_wan:.2f}万元

资金流向: {flow_direction}

💡 提示: 数据更新时间为每日21:30，反映当日资金流向情况
"""

    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        return f"获取资金流向失败: {str(e)}"


@tool("获取股票基本面")
def get_fundamental_data(stock_code: str, cached_data=None) -> str:
    """
    获取股票基本面数据（不含评分，让AI自己分析）

    返回原始数据，包括：
    - 股票名称、交易所、市场
    - 实时数据：涨幅、换手率、成交额
    - 财务数据：ROE、净利润增长率等
    - 行业信息

    Args:
        stock_code: 股票代码
        cached_data: 保留参数（兼容性），不再使用

    Returns:
        基本面数据（不含评分）
    """
    from src.tools.data_source_manager import DataSourceManager

    try:
        dsm = DataSourceManager()

        # 方法1: 尝试从DataSourceManager获取股票信息
        try:
            # ✅ 修复：直接使用 asyncio.run()，它会自动处理事件循环
            # 如果在线程池中运行，asyncio.run() 会创建新的事件循环
            response = asyncio.run(dsm.get_stock_info(stock_code))

            # 检查响应是否成功
            if response and response.success and response.data:
                stock_info = response.data
                stock_name = stock_info.get('stock_name', 'N/A')
                exchange = stock_info.get('exchange', 'N/A')
                market = stock_info.get('market', 'N/A')

                # 🔴 优先使用传入的缓存数据（避免重复查询）
                price_change = 0
                turnover = 0
                volume = 0

                if cached_data:
                    # ✅ 使用传入的缓存数据
                    price_change = float(cached_data.price_change or 0)
                    turnover = float(cached_data.turnover_rate or 0)
                    volume = float(cached_data.volume or 0)
                    if stock_name == 'N/A' or stock_name.startswith('股票'):
                        stock_name = cached_data.stock_name or stock_name
                    logger.info(f"  ✅ 基本面分析使用传入的缓存数据: {stock_code}, 涨幅{price_change:+.2f}%, 换手{turnover:.2f}%")
                else:
                    # 如果没有传入缓存数据，从券商数据获取
                    all_stocks = _get_all_broker_data_with_names()
                    realtime_stock = next((s for s in all_stocks if s.get('dm') == stock_code), None)

                    # 如果stock_name是默认值，尝试从券商数据获取
                    if stock_name == 'N/A' or stock_name.startswith('股票'):
                        if realtime_stock:
                            stock_name = realtime_stock.get('name', stock_name)

                    if realtime_stock:
                        price_change = float(realtime_stock.get('pc', 0))
                        # ✅ 使用准确的换手率（已经通过流通股本计算过）
                        turnover = float(realtime_stock.get('turnover_rate', 0))
                        volume_yuan = float(realtime_stock.get('cje', 0))  # 成交额（元）
                        volume = volume_yuan / 100000000  # 转换为亿
                        logger.info(f"  ✅ 基本面分析使用券商数据: {stock_code}, 涨幅{price_change:+.2f}%, 换手{turnover:.2f}%")

                # ✅ 从数据库获取概念板块
                concepts = []
                try:
                    from src.database.db_manager import get_db
                    db = get_db()
                    with db.get_session() as session:
                        from src.database.models import StockConcepts
                        concept_records = session.query(StockConcepts).filter(
                            StockConcepts.stock_code == stock_code
                        ).limit(10).all()  # 只取前10个概念
                        concepts = [c.tag for c in concept_records]
                except Exception as e:
                    logger.debug(f"获取概念板块失败: {e}")

                industry_name = "、".join(concepts) if concepts else "未知"

                # 获取财务数据
                roe = 0
                net_profit_growth = 0
                pe_ratio = 0

                try:
                    # 获取财务指标
                    from src.tools.zhitu_api import create_zhitu_client
                    zhitu_client = create_zhitu_client()

                    # ✅ 获取财务指标（使用正确的字段名）
                    financial_data = zhitu_client.get_financial_indicators(stock_code)
                    if financial_data and len(financial_data) > 0:
                        latest = financial_data[0]
                        # ✅ 使用API实际返回的字段名，安全转换（处理'--'等无效值）
                        def safe_float(value, default=0):
                            """安全转换为float，处理'--'、None等无效值"""
                            if value is None or value == '' or value == '--':
                                return default
                            try:
                                return float(value)
                            except (ValueError, TypeError):
                                return default

                        roe = safe_float(latest.get('jzsy'))  # 净资产收益率
                        net_profit_growth = safe_float(latest.get('jlzz'))  # 净利润增长率
                        pe_ratio = safe_float(latest.get('pe_ratio'))  # 市盈率（如果有）

                    zhitu_client.close()
                except Exception as e:
                    logger.warning(f"获取财务数据失败: {e}")

                return f"""
=== {stock_code} {stock_name} 基本面数据 ===

【基本信息】
股票名称: {stock_name}
交易所: {exchange}
市场: {market}
行业: {industry_name}

【实时数据】
涨跌幅: {price_change:.2f}%
换手率: {turnover:.2f}%
成交额: {volume:.2f}亿

【财务数据】
ROE（净资产收益率）: {roe:.2f}%
净利润增长率: {net_profit_growth:.2f}%
市盈率: {pe_ratio:.2f}

💡 提示: 请根据以上数据综合分析，不要简单套用固定规则
      考虑行业特性、市场环境、公司成长性等因素

数据来源: {response.source.value} + 智兔财务数据
"""
        except Exception as e:
            logger.warning(f"从DataSourceManager获取股票信息失败: {e}")

        # 方法2: 从券商实时数据推断
        all_stocks = _get_all_broker_data_with_names()
        stock = next((s for s in all_stocks if s.get('dm') == stock_code), None)

        if not stock:
            return f"""
=== {stock_code} 基本面数据 ===

⚠️ 未找到该股票的基本面数据
建议：检查股票代码是否正确
"""

        stock_name = stock.get('name', 'N/A')
        price_change = float(stock.get('pc', 0))
        turnover = float(stock.get('tr_accurate', stock.get('tr', 0)))  # 使用准确的换手率
        volume_yuan = float(stock.get('cje', 0))  # 成交额（元）
        volume = volume_yuan / 100000000  # 转换为亿

        # ✅ 从数据库获取概念板块
        concepts = []
        try:
            from src.database.db_manager import get_db
            db = get_db()
            with db.get_session() as session:
                from src.database.models import StockConcepts
                concept_records = session.query(StockConcepts).filter(
                    StockConcepts.stock_code == stock_code
                ).limit(10).all()  # 只取前10个概念
                concepts = [c.tag for c in concept_records]
        except Exception as e:
            logger.debug(f"获取概念板块失败: {e}")

        industry_name = "、".join(concepts) if concepts else "未知"

        # 获取财务数据
        roe = 0
        net_profit_growth = 0
        pe_ratio = 0

        # ✅ 定义安全转换函数（处理'--'等无效值）
        def safe_float(value, default=0):
            """安全转换为float，处理'--'、None等无效值"""
            if value is None or value == '' or value == '--':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        try:
            from src.tools.zhitu_api import create_zhitu_client
            zhitu_client = create_zhitu_client()

            # ✅ 获取财务指标（使用正确的字段名）
            financial_data = zhitu_client.get_financial_indicators(stock_code)
            if financial_data and len(financial_data) > 0:
                latest = financial_data[0]
                # ✅ 使用API实际返回的字段名，安全转换
                roe = safe_float(latest.get('jzsy'))  # 净资产收益率
                net_profit_growth = safe_float(latest.get('jlzz'))  # 净利润增长率
                # 市盈率从券商实时数据获取
                pe_ratio = safe_float(stock.get('pe_ratio')) if stock else 0

            zhitu_client.close()
        except Exception as e:
            logger.warning(f"获取财务数据失败: {e}")

        return f"""
=== {stock_code} {stock_name} 基本面数据 ===

【基本信息】
股票名称: {stock_name}
行业: {industry_name}

【实时数据】
涨跌幅: {price_change:.2f}%
换手率: {turnover:.2f}%
成交额: {volume:.2f}亿

【财务数据】
ROE（净资产收益率）: {roe:.2f}%
净利润增长率: {net_profit_growth:.2f}%
市盈率: {pe_ratio:.2f}

💡 提示: 请根据以上数据综合分析，不要简单套用固定规则
      考虑行业特性、市场环境、公司成长性等因素

数据来源: 券商实时数据 + 智兔财务数据
"""

    except Exception as e:
        return f"""
=== {stock_code} 基本面数据 ===

获取基本面数据失败: {str(e)}
"""


@tool("并行分析多只股票")
def analyze_stocks_parallel(stock_codes: str, compact_mode: bool = False) -> str:
    """
    并行分析多只股票的技术、资金、基本面、新闻、逐笔交易、社区情绪六个维度

    Args:
        stock_codes: 股票代码列表，逗号分隔，如'600000,000001,002163'
        compact_mode: 是否使用紧凑模式（默认False，输出完整信息）

    Returns:
        所有股票的综合分析结果
    """
    try:
        # 解析股票代码列表
        codes = [code.strip() for code in stock_codes.split(',') if code.strip()]

        if not codes:
            return "错误: 未提供有效的股票代码"

        logger.info(f"开始并行分析{len(codes)}只股票: {codes}")

        # ==================== 信号分析函数（不做硬判断，提供多维度信号）====================

        def calculate_atr(stock_code: str, period: int = 14) -> float:
            """
            计算ATR（Average True Range）指标

            使用多种方式估算波动率

            Args:
                stock_code: 股票代码
                period: 周期（默认14）

            Returns:
                ATR值（或波动率估算值）
            """
            try:
                from src.tools.zhitu_api import ZhituAPI
                zhitu = ZhituAPI()

                # 方案1：使用BOLL指标估算波动率
                try:
                    boll_data = zhitu.get_history_boll(stock_code, 'd', 'n', latest_count=1)
                    if boll_data and len(boll_data) > 0:
                        latest_boll = boll_data[-1]
                        upper = latest_boll.get('u') or latest_boll.get('upper')
                        lower = latest_boll.get('d') or latest_boll.get('lower')

                        if upper is not None and lower is not None:
                            upper = float(upper)
                            lower = float(lower)
                            if upper > 0 and lower > 0:
                                estimated_atr = (upper - lower) / 4
                                logger.debug(f"ATR估算（BOLL）: {estimated_atr:.2f}")
                                return estimated_atr
                except Exception as e:
                    logger.debug(f"BOLL方式计算ATR失败: {e}")

                # 方案2：使用当日振幅作为fallback
                try:
                    kline_data = zhitu.get_latest_timeframe(stock_code, timeframe='d', limit=1)
                    if kline_data and len(kline_data) > 0:
                        today = kline_data[-1]
                        high = float(today.get('h', 0))
                        low = float(today.get('l', 0))
                        close = float(today.get('c', 0))

                        if high > 0 and low > 0:
                            daily_range = high - low
                            # 用振幅占收盘价的比例来估算ATR
                            # 一般股票日均振幅约2-3%，所以用当日振幅作为ATR估算
                            logger.debug(f"ATR估算（当日振幅）: {daily_range:.2f}")
                            return daily_range
                except Exception as e:
                    logger.debug(f"振幅方式计算ATR失败: {e}")

                return 0

            except Exception as e:
                logger.error(f"ATR计算失败: {e}")
                return 0

        def analyze_upper_shadow_signal(kline_data: Dict, stock_code: str, volume_ratio: float = 1.0, price_position: str = 'UNKNOWN') -> Dict:
            """
            分析上影线信号（不做硬判断，提供多维度信号）

            Args:
                kline_data: K线数据，包含o/h/l/c
                stock_code: 股票代码（用于计算ATR）
                volume_ratio: 成交量比率（今日/昨日）
                price_position: 价格位置（LOW/MEDIUM/HIGH）

            Returns:
                上影线信号分析结果
            """
            try:
                open_price = float(kline_data.get('o', 0))
                high_price = float(kline_data.get('h', 0))
                low_price = float(kline_data.get('l', 0))
                close_price = float(kline_data.get('c', 0))

                if high_price <= low_price:
                    return {'signal_type': 'upper_shadow', 'signal_strength': 'NONE', 'description': '数据异常'}

                # 实体部分
                body_top = max(open_price, close_price)

                # 上影线长度
                upper_shadow = high_price - body_top

                # 总振幅
                total_range = high_price - low_price

                # 上影线占比
                upper_shadow_ratio = upper_shadow / total_range if total_range > 0 else 0

                # 计算ATR（使用当日振幅作为估算）
                atr = calculate_atr(stock_code)
                upper_shadow_atr_ratio = upper_shadow / atr if atr > 0 else 0

                # 信号强度判断
                # 由于ATR使用当日振幅，所以阈值调整为：
                # - 上影线占振幅60%以上 → STRONG（明显冲高回落）
                # - 上影线占振幅40%以上 → MEDIUM（有冲高回落迹象）
                # - 否则 → WEAK
                if upper_shadow_atr_ratio > 0.6:
                    signal_strength = 'STRONG'
                elif upper_shadow_atr_ratio > 0.4:
                    signal_strength = 'MEDIUM'
                else:
                    signal_strength = 'WEAK'

                # 提供多种解读（不做结论）
                interpretations = []

                if signal_strength in ['STRONG', 'MEDIUM']:
                    # 根据位置和成交量提供不同解读
                    if price_position == 'HIGH' and volume_ratio > 2.0:
                        interpretations.append('高位放量长上影 → 主力出货（概率60%）')
                        interpretations.append('高位放量长上影 → 主力试盘（概率30%）')
                        interpretations.append('高位放量长上影 → 主力洗盘（概率10%）')
                    elif price_position == 'LOW' and volume_ratio > 2.0:
                        interpretations.append('低位放量长上影 → 主力试盘（概率50%）')
                        interpretations.append('低位放量长上影 → 主力洗盘（概率30%）')
                        interpretations.append('低位放量长上影 → 主力出货（概率20%）')
                    else:
                        interpretations.append('上影线异常 → 需结合位置和成交量判断')

                return {
                    'signal_type': 'upper_shadow',
                    'signal_strength': signal_strength,
                    'metrics': {
                        'upper_shadow_length': round(upper_shadow, 2),
                        'upper_shadow_ratio': round(upper_shadow_ratio, 3),
                        'atr_14': round(atr, 2),
                        'upper_shadow_atr_ratio': round(upper_shadow_atr_ratio, 2),
                        'volume_ratio': round(volume_ratio, 2),
                        'price_position': price_position
                    },
                    'interpretations': interpretations,
                    'description': f'📊 上影线{upper_shadow:.2f}元（占振幅{upper_shadow_ratio*100:.1f}%），ATR倍数{upper_shadow_atr_ratio:.2f}倍'
                }
            except Exception as e:
                logger.error(f"上影线信号分析失败: {e}")
                return {'signal_type': 'upper_shadow', 'signal_strength': 'NONE', 'description': '分析失败'}

        def detect_main_force_selling(main_net_inflow: float, buy_sell_ratio: float, turnover_rate: float) -> Dict:
            """
            检测主力出货

            Args:
                main_net_inflow: 主力资金净流入（万元，负数表示流出）
                buy_sell_ratio: 买卖比
                turnover_rate: 换手率（%）

            Returns:
                主力出货检测结果
            """
            try:
                # 主力资金净流出（取绝对值）
                main_outflow = abs(main_net_inflow) if main_net_inflow < 0 else 0

                # 判断逻辑
                if main_outflow > 5000 and buy_sell_ratio < 1.0 and turnover_rate > 15:
                    return {
                        'is_selling': True,
                        'risk_level': 'HIGH',
                        'description': f'🔴 主力净流出{main_outflow:.0f}万，买卖比{buy_sell_ratio:.2f}，换手率{turnover_rate:.1f}%，明显出货'
                    }
                elif main_outflow > 3000 and buy_sell_ratio < 0.95:
                    return {
                        'is_selling': True,
                        'risk_level': 'MEDIUM',
                        'description': f'⚠️ 主力净流出{main_outflow:.0f}万，买卖比{buy_sell_ratio:.2f}，疑似出货'
                    }
                elif main_outflow > 5000:
                    return {
                        'is_selling': True,
                        'risk_level': 'MEDIUM',
                        'description': f'⚠️ 主力净流出{main_outflow:.0f}万，资金流出较大'
                    }
                else:
                    return {
                        'is_selling': False,
                        'risk_level': 'LOW',
                        'description': '✅ 主力资金正常'
                    }
            except Exception as e:
                logger.error(f"主力出货检测失败: {e}")
                return {'is_selling': False, 'risk_level': 'LOW', 'description': '检测失败'}

        def detect_trend_conflict(kline_60d: str, kline_60m: str, kline_15m: str, kline_5m: str) -> list:
            """
            检测多周期趋势冲突

            Args:
                kline_60d: 60日趋势描述
                kline_60m: 60分钟趋势描述
                kline_15m: 15分钟趋势描述
                kline_5m: 5分钟趋势描述

            Returns:
                趋势冲突列表
            """
            try:
                conflicts = []

                # 日线上升 + 60分钟下降 = 短期转弱
                if '上升' in kline_60d and '下降' in kline_60m:
                    conflicts.append({
                        'type': '日线-60分钟冲突',
                        'risk_level': 'MEDIUM',
                        'description': '⚠️ 日线上升但60分钟转弱，短期回调风险'
                    })

                # 日线上升 + 15分钟下降 + 5分钟下降 = 短期趋势转弱
                if '上升' in kline_60d and '下降' in kline_15m and '下降' in kline_5m:
                    conflicts.append({
                        'type': '多周期转弱',
                        'risk_level': 'HIGH',
                        'description': '🔴 日线上升但分钟级全面转弱，警惕回调'
                    })

                return conflicts
            except Exception as e:
                logger.error(f"趋势冲突检测失败: {e}")
                return []

        def analyze_sentiment_reverse_indicator(all_comments: list) -> Dict:
            """
            分析社区情绪反向指标

            Args:
                all_comments: 所有评论列表

            Returns:
                反向指标分析结果
            """
            try:
                # 关键词检测
                negative_keywords = ['追高', '被套', '回本', '割肉', '站岗', '解套', '亏损', '套牢']
                panic_keywords = ['暴跌', '崩盘', '完了', '跑路', '血亏']
                euphoria_keywords = ['暴涨', '起飞', '翻倍', '牛市', '梭哈', '满仓', '冲天']

                negative_count = 0
                panic_count = 0
                euphoria_count = 0

                for comment in all_comments:
                    content = str(comment.get('content', ''))
                    for kw in negative_keywords:
                        if kw in content:
                            negative_count += 1
                            break
                    for kw in panic_keywords:
                        if kw in content:
                            panic_count += 1
                            break
                    for kw in euphoria_keywords:
                        if kw in content:
                            euphoria_count += 1
                            break

                total_comments = len(all_comments) if all_comments else 1

                # 判断
                if negative_count > total_comments * 0.3:
                    return {
                        'is_reverse_signal': True,
                        'signal_type': '散户被套',
                        'risk_level': 'HIGH',
                        'description': f'🔴 评论中{negative_count}/{total_comments}条提到追高被套，散户接盘信号'
                    }
                elif euphoria_count > total_comments * 0.5:
                    return {
                        'is_reverse_signal': True,
                        'signal_type': '散户狂热',
                        'risk_level': 'HIGH',
                        'description': f'🔴 评论中{euphoria_count}/{total_comments}条过度乐观，可能是顶部信号'
                    }
                else:
                    return {
                        'is_reverse_signal': False,
                        'signal_type': '正常',
                        'risk_level': 'LOW',
                        'description': '✅ 社区情绪正常'
                    }
            except Exception as e:
                logger.error(f"反向指标分析失败: {e}")
                return {'is_reverse_signal': False, 'signal_type': '正常', 'risk_level': 'LOW', 'description': '分析失败'}

        # 定义分析任务
        def analyze_single_stock(stock_code: str) -> Dict[str, str]:
            """
            分析单只股票的所有维度

            注意：此函数必须保证不会抛出异常，所有错误都应该被捕获并返回错误信息
            """
            # 🔴 最外层try-except保护，确保任何异常都不会导致整个并行分析崩溃
            try:
                logger.info(f"🔍 开始分析股票: {stock_code}")

                result = {
                    'code': stock_code,
                    'technical': '',
                    'fund_flow': '',
                    'fundamental': '',
                    'news': '',
                    'tick_analysis': '',  # ✅ 新增：逐笔交易分析
                    'community_sentiment': '',  # ✅ 新增：社区情绪分析
                    'cached_data': ''  # 🔴 新增：缓存数据
                }

                # 🔴 从AgentContext读取候选股数据（优先使用缓存，提升性能）
                stock_name = 'N/A'
                candidate_info = None
                try:
                    from src.agents.tools.context_tools import load_agent_context
                    import json

                    # 读取候选股列表（使用.func()调用Tool）
                    context_data = load_agent_context.func('candidate_stocks')
                    if context_data and 'error' not in context_data:
                        candidate_stocks = json.loads(context_data).get('stocks', [])
                        # 查找当前股票
                        for stock in candidate_stocks:
                            if stock.get('code') == stock_code:
                                candidate_info = stock
                                stock_name = stock.get('name', 'N/A')
                                result['cached_data'] = f"""
【候选股数据】
股票名称: {stock.get('name')}
当前价格: {stock.get('current_price', 0):.2f}元
涨跌幅: {stock.get('price_change', 0):+.2f}%
换手率: {stock.get('turnover_rate', 0):.2f}%
成交额: {stock.get('volume', 0):.2f}亿
振幅: {stock.get('amplitude', 0):.2f}%
"""
                                logger.info(f"  ✅ 从AgentContext读取{stock_code}数据: {stock_name}, 涨幅{stock.get('price_change', 0):+.2f}%")
                                break

                        if not candidate_info:
                            logger.debug(f"  📝 AgentContext中未找到{stock_code}的数据，将从券商数据获取")
                    else:
                        logger.debug(f"  📝 未找到candidate_stocks上下文，将从券商数据获取")
                except Exception as e:
                    logger.debug(f"  📝 读取AgentContext失败: {e}，将从券商数据获取")

                # 如果AgentContext中没有，从券商数据获取股票名称
                if stock_name == 'N/A':
                    try:
                        logger.debug(f"  获取{stock_code}的股票名称...")
                        broker_stocks = _get_all_broker_data_with_names()
                        for stock in broker_stocks:
                            if stock.get('dm') == stock_code:
                                stock_name = stock.get('name', 'N/A')
                                logger.info(f"  ✅ 股票名称: {stock_name}")
                                break
                    except Exception as e:
                        logger.warning(f"  ⚠️ 获取股票名称失败: {e}")

                # 并行执行6个维度的分析
                try:
                    with ThreadPoolExecutor(max_workers=6) as executor:
                        futures = {}

                        # 提交任务
                        try:
                            futures['technical'] = executor.submit(get_technical_indicators.func, stock_code)
                        except Exception as e:
                            if "interpreter shutdown" not in str(e):
                                logger.error(f"    ❌ 提交技术指标分析失败: {e}")

                        try:
                            futures['fund_flow'] = executor.submit(get_fund_flow.func, stock_code)
                        except Exception as e:
                            if "interpreter shutdown" not in str(e):
                                logger.error(f"    ❌ 提交资金流向分析失败: {e}")

                        try:
                            # ✅ 传入候选股信息（如果有的话）
                            futures['fundamental'] = executor.submit(get_fundamental_data.func, stock_code, candidate_info)
                        except Exception as e:
                            if "interpreter shutdown" not in str(e):
                                logger.error(f"    ❌ 提交基本面分析失败: {e}")

                        # 新闻分析需要股票名称
                        try:
                            from src.agents.tools.news_tools import search_stock_news
                            futures['news'] = executor.submit(search_stock_news.func, stock_code, stock_name)
                        except Exception as e:
                            if "interpreter shutdown" not in str(e):
                                logger.warning(f"    ⚠️ 新闻分析工具导入失败: {e}")

                        # ✅ 新增：逐笔交易分析
                        try:
                            from src.agents.tools.tick_data_tools import get_smart_tick_analysis
                            futures['tick_analysis'] = executor.submit(get_smart_tick_analysis.func, stock_code)
                        except Exception as e:
                            if "interpreter shutdown" not in str(e):
                                logger.warning(f"    ⚠️ 逐笔交易分析工具导入失败: {e}")

                        # ✅ 新增：社区情绪分析
                        try:
                            from src.agents.tools.community_sentiment_tools import get_stock_community_comments
                            # 🔴 修复：只传入stock_code，不传入stock_name（max_items参数是整数）
                            futures['community_sentiment'] = executor.submit(get_stock_community_comments.func, stock_code)
                        except Exception as e:
                            if "interpreter shutdown" not in str(e):
                                logger.warning(f"    ⚠️ 社区情绪分析工具导入失败: {e}")

                        # 收集结果（✅ 增加超时时间：30秒 → 60秒）
                        for dimension, future in futures.items():
                            try:
                                result[dimension] = future.result(timeout=60)
                            except TimeoutError:
                                result[dimension] = f"{dimension}分析超时（60秒）"
                                logger.error(f"    ❌ {stock_code} {dimension}分析超时")
                            except Exception as e:
                                # ✅ 增强错误日志：显示异常类型和详细信息
                                import traceback
                                error_msg = str(e) if str(e) else repr(e)
                                error_detail = traceback.format_exc()
                                result[dimension] = f"{dimension}分析失败: {error_msg}"
                                logger.error(f"    ❌ {stock_code} {dimension}分析失败: {error_msg}")
                                logger.debug(f"    详细错误信息:\n{error_detail}")

                except RuntimeError as e:
                    # 捕获解释器关闭时的错误，静默处理
                    if "interpreter shutdown" in str(e):
                        logger.debug(f"  程序正在关闭，跳过{stock_code}的并行分析")
                        return {
                            'code': stock_code,
                            'technical': '程序关闭中',
                            'fund_flow': '程序关闭中',
                            'fundamental': '程序关闭中',
                            'news': '程序关闭中',
                            'tick_analysis': '程序关闭中'
                        }
                    else:
                        raise

                # ==================== 风险检测集成 ====================
                risk_signals = []

                try:
                    # 1. 上影线检测（从技术指标中提取日线数据）
                    import re
                    import json

                    # 从技术指标中提取日线K线数据
                    technical_text = result.get('technical', '')

                    # 尝试从候选股数据中获取涨跌幅和换手率
                    price_change = 0
                    turnover_rate = 0
                    if candidate_info:
                        price_change = candidate_info.get('price_change', 0)
                        turnover_rate = candidate_info.get('turnover_rate', 0)

                    # 从技术指标中提取K线形态信息
                    if '【60日周期】' in technical_text:
                        # 提取60日周期的形态描述
                        pattern_match = re.search(r'形态:\s*([^\n]+)', technical_text)
                        if pattern_match:
                            pattern = pattern_match.group(1)
                            # 检测倒锤子线、射击之星等冲高回落形态
                            if '倒锤子' in pattern or '射击之星' in pattern or '长上影' in pattern:
                                risk_signals.append({
                                    'type': 'K线形态风险',
                                    'risk_level': 'HIGH',
                                    'description': f'🔴 K线形态：{pattern}，警惕冲高回落'
                                })

                    # 🔴 新增：使用ATR计算上影线信号（精确检测冲高回落）
                    try:
                        # 获取当日K线数据
                        from src.tools.zhitu_api import ZhituAPI
                        zhitu = ZhituAPI()

                        # 转换股票代码格式
                        if stock_code.startswith('6'):
                            symbol = f"{stock_code}.SH"
                        else:
                            symbol = f"{stock_code}.SZ"

                        # 获取最近1天日线数据
                        kline_data = zhitu.get_latest_timeframe(symbol, timeframe='d', limit=1)
                        if kline_data and len(kline_data) > 0:
                            today_kline = kline_data[-1]

                            # 计算成交量比率（简化处理，假设为1.0）
                            volume_ratio = 1.0

                            # 判断价格位置
                            price_position = 'UNKNOWN'
                            if candidate_info:
                                pc = candidate_info.get('price_change', 0)
                                if pc > 5:
                                    price_position = 'HIGH'
                                elif pc > 2:
                                    price_position = 'MEDIUM'
                                else:
                                    price_position = 'LOW'

                            # 调用上影线分析函数（使用ATR）
                            shadow_result = analyze_upper_shadow_signal(
                                today_kline,
                                symbol,
                                volume_ratio,
                                price_position
                            )

                            # 如果上影线信号强度为STRONG或MEDIUM，添加风险信号
                            if shadow_result.get('signal_strength') == 'STRONG':
                                risk_signals.append({
                                    'type': '上影线ATR风险',
                                    'risk_level': 'HIGH',
                                    'description': shadow_result.get('description', '🔴 上影线异常，ATR倍数超过2.5')
                                })
                            elif shadow_result.get('signal_strength') == 'MEDIUM':
                                risk_signals.append({
                                    'type': '上影线ATR风险',
                                    'risk_level': 'MEDIUM',
                                    'description': shadow_result.get('description', '⚠️ 上影线较长，ATR倍数超过1.5')
                                })
                    except Exception as e:
                        logger.debug(f"ATR上影线分析失败: {e}")

                    # 2. 主力出货检测（从资金流向和逐笔数据中提取）
                    fund_flow_text = result.get('fund_flow', '')
                    tick_text = result.get('tick_analysis', '')

                    # 提取主力资金净流入
                    main_net_inflow = 0
                    main_match = re.search(r'主力资金净流入:\s*([-\d.]+)万元', fund_flow_text)
                    if main_match:
                        main_net_inflow = float(main_match.group(1))

                    # 提取买卖比
                    buy_sell_ratio = 1.0
                    ratio_match = re.search(r'买卖比:\s*([\d.]+)', tick_text)
                    if ratio_match:
                        buy_sell_ratio = float(ratio_match.group(1))

                    # 执行主力出货检测
                    if main_net_inflow != 0 or buy_sell_ratio != 1.0:
                        selling_result = detect_main_force_selling(main_net_inflow, buy_sell_ratio, turnover_rate)
                        if selling_result['is_selling']:
                            risk_signals.append({
                                'type': '主力出货风险',
                                'risk_level': selling_result['risk_level'],
                                'description': selling_result['description']
                            })

                    # 3. 多周期趋势冲突检测
                    kline_60d = ''
                    kline_60m = ''
                    kline_15m = ''
                    kline_5m = ''

                    if '【60日周期】' in technical_text:
                        trend_match = re.search(r'【60日周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                        if trend_match:
                            kline_60d = trend_match.group(1)

                    if '【60分钟周期】' in technical_text:
                        trend_match = re.search(r'【60分钟周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                        if trend_match:
                            kline_60m = trend_match.group(1)

                    if '【15分钟周期】' in technical_text:
                        trend_match = re.search(r'【15分钟周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                        if trend_match:
                            kline_15m = trend_match.group(1)

                    if '【5分钟周期】' in technical_text:
                        trend_match = re.search(r'【5分钟周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                        if trend_match:
                            kline_5m = trend_match.group(1)

                    # 执行趋势冲突检测
                    conflicts = detect_trend_conflict(kline_60d, kline_60m, kline_15m, kline_5m)
                    risk_signals.extend(conflicts)

                    # 4. 社区情绪反向指标检测
                    sentiment_text = result.get('community_sentiment', '')

                    # 尝试从社区情绪中提取评论列表
                    all_comments = []
                    try:
                        # 查找comments部分
                        if 'comments:' in sentiment_text:
                            # 简单提取：查找所有包含"content"的行
                            for line in sentiment_text.split('\n'):
                                if 'content' in line.lower() or '追高' in line or '被套' in line or '回本' in line:
                                    all_comments.append({'content': line})
                    except:
                        pass

                    # 执行反向指标检测
                    if all_comments:
                        reverse_result = analyze_sentiment_reverse_indicator(all_comments)
                        if reverse_result['is_reverse_signal']:
                            risk_signals.append({
                                'type': '情绪反向指标',
                                'risk_level': reverse_result['risk_level'],
                                'description': reverse_result['description']
                            })

                    # 5. 涨幅回撤分析（如果有价格数据）
                    if price_change > 5:  # 涨幅超过5%才分析
                        # 从技术指标中提取最高价和当前价
                        high_match = re.search(r'压力位:\s*([\d.]+)', technical_text)
                        if high_match:
                            high_price = float(high_match.group(1))
                            # 简单估算：如果压力位明显高于当前涨幅，说明有回撤
                            # 这里需要更精确的数据，暂时用简单逻辑
                            pass

                    # 将风险信号添加到结果中
                    if risk_signals:
                        result['risk_signals'] = risk_signals
                        logger.info(f"  🚨 {stock_code} 检测到{len(risk_signals)}个风险信号")

                except Exception as e:
                    logger.error(f"  ⚠️ {stock_code} 风险检测失败: {e}")

                logger.info(f"✅ 完成{stock_code}的分析")
                return result

            except Exception as e:
                # 🔴 捕获所有未预期的异常，返回错误结果而不是抛出异常
                logger.exception(f"💥 {stock_code}分析过程发生严重错误: {e}")
                return {
                    'code': stock_code,
                    'technical': f'严重错误: {str(e)}',
                    'fund_flow': f'严重错误: {str(e)}',
                    'fundamental': f'严重错误: {str(e)}',
                    'news': f'严重错误: {str(e)}',
                    'tick_analysis': f'严重错误: {str(e)}',
                    'community_sentiment': f'严重错误: {str(e)}'
                }

        # 并行分析所有股票
        all_results = []
        with ThreadPoolExecutor(max_workers=min(len(codes), 5)) as executor:
            future_to_code = {executor.submit(analyze_single_stock, code): code for code in codes}

            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    result = future.result(timeout=60)
                    all_results.append(result)
                    logger.info(f"完成{code}的分析")
                except Exception as e:
                    logger.error(f"{code}分析失败: {e}")
                    all_results.append({
                        'code': code,
                        'technical': f'分析失败: {str(e)}',
                        'fund_flow': f'分析失败: {str(e)}',
                        'fundamental': f'分析失败: {str(e)}',
                        'news': f'分析失败: {str(e)}',
                        'tick_analysis': f'分析失败: {str(e)}',
                        'community_sentiment': f'分析失败: {str(e)}'
                    })

        # 格式化输出
        output_lines = [f"=== 并行分析完成（共{len(all_results)}只股票）===\n"]

        if compact_mode:
            # 🔴 紧凑模式：只输出关键信息，减少上下文长度
            for result in all_results:
                output_lines.append(f"\n【{result['code']}】")
                # 只保留缓存数据（包含基本信息）
                if result.get('cached_data'):
                    output_lines.append(result['cached_data'].strip())
                # 其他维度只保留前100字符
                output_lines.append(f"技术: {result['technical'][:100]}...")
                output_lines.append(f"资金: {result['fund_flow'][:100]}...")
                output_lines.append(f"基本面: {result['fundamental'][:100]}...")
                output_lines.append(f"新闻: {result['news'][:100]}...")
                output_lines.append(f"逐笔: {result['tick_analysis'][:100]}...")
                output_lines.append(f"社区: {result['community_sentiment'][:100]}...")
        else:
            # 完整模式：输出所有信息
            for result in all_results:
                output_lines.append(f"\n{'='*60}")
                output_lines.append(f"股票代码: {result['code']}")
                output_lines.append(f"{'='*60}\n")

                # 🔴 新增：优先显示缓存数据
                if result.get('cached_data'):
                    output_lines.append(result['cached_data'])

                # 🚨 新增：风险信号（最优先显示）
                if result.get('risk_signals'):
                    output_lines.append("\n🚨🚨🚨 【风险信号】 🚨🚨🚨")
                    for signal in result['risk_signals']:
                        risk_level = signal.get('risk_level', 'UNKNOWN')
                        signal_type = signal.get('type', '未知风险')
                        description = signal.get('description', '')

                        # 根据风险等级添加emoji
                        if risk_level == 'HIGH':
                            prefix = '🔴 高风险'
                        elif risk_level == 'MEDIUM':
                            prefix = '⚠️ 中风险'
                        else:
                            prefix = '⚡ 低风险'

                        output_lines.append(f"{prefix} - {signal_type}: {description}")
                    output_lines.append("")

                output_lines.append("【技术指标】")
                output_lines.append(result['technical'])
                output_lines.append("\n【资金流向】")
                output_lines.append(result['fund_flow'])
                output_lines.append("\n【基本面】")
                output_lines.append(result['fundamental'])
                output_lines.append("\n【新闻分析】")
                output_lines.append(result['news'])
                output_lines.append("\n【逐笔交易分析】")
                output_lines.append(result['tick_analysis'])
                output_lines.append("\n【社区情绪分析】")
                output_lines.append(result['community_sentiment'])

        return "\n".join(output_lines)

    except Exception as e:
        logger.error(f"并行分析失败: {e}")
        return f"并行分析失败: {str(e)}"


@tool("自动分批并行分析所有股票")
def analyze_all_stocks_auto_batch(stock_codes: str, batch_size: int = 5) -> str:
    """
    自动分批并行分析所有股票（多批次并行执行，大幅提升速度）

    🚀 性能优势：
    - 传统方式：35只股票 = 7批 × 串行等待 = 很慢
    - 新方式：35只股票 = 7批并行执行 = 接近单批耗时

    Args:
        stock_codes: 所有股票代码，逗号分隔，如'600000,000001,002163,...'
        batch_size: 每批股票数量（默认5只，避免单批上下文过长）

    Returns:
        所有股票的分析结果（按批次汇总）
    """
    try:
        # 1. 解析股票代码
        codes = [code.strip() for code in stock_codes.split(',') if code.strip()]

        if not codes:
            return "错误: 未提供有效的股票代码"

        total_stocks = len(codes)
        logger.info(f"🚀 开始自动分批并行分析{total_stocks}只股票（每批{batch_size}只）")

        # 2. 分批
        batches = [codes[i:i+batch_size] for i in range(0, len(codes), batch_size)]
        total_batches = len(batches)
        logger.info(f"📦 分为{total_batches}批，准备并行处理...")

        # 3. 定义批次处理函数（复用 analyze_single_stock 逻辑）
        def process_batch(batch_index: int, batch_codes: List[str]) -> List[Dict[str, str]]:
            """处理单个批次的股票"""
            batch_num = batch_index + 1
            logger.info(f"  📦 批次{batch_num}/{total_batches} 开始处理（{len(batch_codes)}只股票）: {batch_codes}")

            results = []

            # 定义分析任务（复用现有的 analyze_single_stock 函数）
            def analyze_single_stock(stock_code: str) -> Dict[str, str]:
                """
                分析单只股票的所有维度

                注意：此函数必须保证不会抛出异常，所有错误都应该被捕获并返回错误信息
                """
                # 🔴 最外层try-except保护，确保任何异常都不会导致整个并行分析崩溃
                try:
                    logger.info(f"    🔍 批次{batch_num} - 开始分析股票: {stock_code}")

                    result = {
                        'code': stock_code,
                        'technical': '',
                        'fund_flow': '',
                        'fundamental': '',
                        'news': '',
                        'tick_analysis': '',
                        'community_sentiment': '',
                        'cached_data': ''
                    }

                    # 🔴 从AgentContext读取候选股数据（优先使用缓存，提升性能）
                    stock_name = 'N/A'
                    candidate_info = None
                    try:
                        from src.agents.tools.context_tools import load_agent_context
                        import json

                        # 读取候选股列表（使用.func()调用Tool）
                        context_data = load_agent_context.func('candidate_stocks')
                        if context_data and 'error' not in context_data:
                            candidate_stocks = json.loads(context_data).get('stocks', [])
                            # 查找当前股票
                            for stock in candidate_stocks:
                                if stock.get('code') == stock_code:
                                    candidate_info = stock
                                    stock_name = stock.get('name', 'N/A')
                                    result['cached_data'] = f"""
【候选股数据】
股票名称: {stock.get('name')}
当前价格: {stock.get('current_price', 0):.2f}元
涨跌幅: {stock.get('price_change', 0):+.2f}%
换手率: {stock.get('turnover_rate', 0):.2f}%
成交额: {stock.get('volume', 0):.2f}亿
振幅: {stock.get('amplitude', 0):.2f}%
"""
                                    logger.info(f"      ✅ 从AgentContext读取{stock_code}数据: {stock_name}, 涨幅{stock.get('price_change', 0):+.2f}%")
                                    break

                            if not candidate_info:
                                logger.debug(f"      📝 AgentContext中未找到{stock_code}的数据，将从券商数据获取")
                        else:
                            logger.debug(f"      📝 未找到candidate_stocks上下文，将从券商数据获取")
                    except Exception as e:
                        logger.debug(f"      📝 读取AgentContext失败: {e}，将从券商数据获取")

                    # 如果AgentContext中没有，从券商数据获取股票名称
                    if stock_name == 'N/A':
                        try:
                            logger.debug(f"      获取{stock_code}的股票名称...")
                            broker_stocks = _get_all_broker_data_with_names()
                            for stock in broker_stocks:
                                if stock.get('dm') == stock_code:
                                    stock_name = stock.get('name', 'N/A')
                                    logger.info(f"      ✅ 股票名称: {stock_name}")
                                    break
                        except Exception as e:
                            logger.warning(f"      ⚠️ 获取股票名称失败: {e}")

                    # 并行执行6个维度的分析
                    try:
                        with ThreadPoolExecutor(max_workers=6) as executor:
                            futures = {}

                            # 提交任务
                            try:
                                futures['technical'] = executor.submit(get_technical_indicators.func, stock_code)
                            except Exception as e:
                                if "interpreter shutdown" not in str(e):
                                    logger.error(f"        ❌ 提交技术指标分析失败: {e}")

                            try:
                                futures['fund_flow'] = executor.submit(get_fund_flow.func, stock_code)
                            except Exception as e:
                                if "interpreter shutdown" not in str(e):
                                    logger.error(f"        ❌ 提交资金流向分析失败: {e}")

                            try:
                                futures['fundamental'] = executor.submit(get_fundamental_data.func, stock_code, candidate_info)
                            except Exception as e:
                                if "interpreter shutdown" not in str(e):
                                    logger.error(f"        ❌ 提交基本面分析失败: {e}")

                            # 新闻分析需要股票名称
                            try:
                                from src.agents.tools.news_tools import search_stock_news
                                futures['news'] = executor.submit(search_stock_news.func, stock_code, stock_name)
                            except Exception as e:
                                if "interpreter shutdown" not in str(e):
                                    logger.warning(f"        ⚠️ 新闻分析工具导入失败: {e}")

                            # 逐笔交易分析
                            try:
                                from src.agents.tools.tick_data_tools import get_smart_tick_analysis
                                futures['tick_analysis'] = executor.submit(get_smart_tick_analysis.func, stock_code)
                            except Exception as e:
                                if "interpreter shutdown" not in str(e):
                                    logger.warning(f"        ⚠️ 逐笔交易分析工具导入失败: {e}")

                            # 社区情绪分析
                            try:
                                from src.agents.tools.community_sentiment_tools import get_stock_community_comments
                                futures['community_sentiment'] = executor.submit(get_stock_community_comments.func, stock_code)
                            except Exception as e:
                                if "interpreter shutdown" not in str(e):
                                    logger.warning(f"        ⚠️ 社区情绪分析工具导入失败: {e}")

                            # 收集结果
                            for dimension, future in futures.items():
                                try:
                                    result[dimension] = future.result(timeout=60)
                                except TimeoutError:
                                    result[dimension] = f"{dimension}分析超时（60秒）"
                                    logger.error(f"        ❌ {stock_code} {dimension}分析超时")
                                except Exception as e:
                                    import traceback
                                    error_msg = str(e) if str(e) else repr(e)
                                    error_detail = traceback.format_exc()
                                    result[dimension] = f"{dimension}分析失败: {error_msg}"
                                    logger.error(f"        ❌ {stock_code} {dimension}分析失败: {error_msg}")
                                    logger.debug(f"        详细错误信息:\n{error_detail}")

                    except RuntimeError as e:
                        # 捕获解释器关闭时的错误，静默处理
                        if "interpreter shutdown" in str(e):
                            logger.debug(f"      程序正在关闭，跳过{stock_code}的并行分析")
                            return {
                                'code': stock_code,
                                'technical': '程序关闭中',
                                'fund_flow': '程序关闭中',
                                'fundamental': '程序关闭中',
                                'news': '程序关闭中',
                                'tick_analysis': '程序关闭中',
                                'community_sentiment': '程序关闭中'
                            }
                        else:
                            raise

                    # ==================== 风险检测集成（与外层函数相同逻辑）====================
                    risk_signals = []

                    try:
                        import re
                        import json

                        # 从候选股数据中获取涨跌幅和换手率
                        price_change = 0
                        turnover_rate = 0
                        if candidate_info:
                            price_change = candidate_info.get('price_change', 0)
                            turnover_rate = candidate_info.get('turnover_rate', 0)

                        technical_text = result.get('technical', '')

                        # 1. K线形态风险检测
                        if '【60日周期】' in technical_text:
                            pattern_match = re.search(r'形态:\s*([^\n]+)', technical_text)
                            if pattern_match:
                                pattern = pattern_match.group(1)
                                if '倒锤子' in pattern or '射击之星' in pattern or '长上影' in pattern:
                                    risk_signals.append({
                                        'type': 'K线形态风险',
                                        'risk_level': 'HIGH',
                                        'description': f'🔴 K线形态：{pattern}，警惕冲高回落'
                                    })

                        # 2. 主力出货检测
                        fund_flow_text = result.get('fund_flow', '')
                        tick_text = result.get('tick_analysis', '')

                        main_net_inflow = 0
                        main_match = re.search(r'主力资金净流入:\s*([-\d.]+)万元', fund_flow_text)
                        if main_match:
                            main_net_inflow = float(main_match.group(1))

                        buy_sell_ratio = 1.0
                        ratio_match = re.search(r'买卖比:\s*([\d.]+)', tick_text)
                        if ratio_match:
                            buy_sell_ratio = float(ratio_match.group(1))

                        if main_net_inflow != 0 or buy_sell_ratio != 1.0:
                            selling_result = detect_main_force_selling(main_net_inflow, buy_sell_ratio, turnover_rate)
                            if selling_result['is_selling']:
                                risk_signals.append({
                                    'type': '主力出货风险',
                                    'risk_level': selling_result['risk_level'],
                                    'description': selling_result['description']
                                })

                        # 3. 多周期趋势冲突检测
                        kline_60d = ''
                        kline_60m = ''
                        kline_15m = ''
                        kline_5m = ''

                        if '【60日周期】' in technical_text:
                            trend_match = re.search(r'【60日周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                            if trend_match:
                                kline_60d = trend_match.group(1)

                        if '【60分钟周期】' in technical_text:
                            trend_match = re.search(r'【60分钟周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                            if trend_match:
                                kline_60m = trend_match.group(1)

                        if '【15分钟周期】' in technical_text:
                            trend_match = re.search(r'【15分钟周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                            if trend_match:
                                kline_15m = trend_match.group(1)

                        if '【5分钟周期】' in technical_text:
                            trend_match = re.search(r'【5分钟周期】.*?趋势:\s*([^\n]+)', technical_text, re.DOTALL)
                            if trend_match:
                                kline_5m = trend_match.group(1)

                        conflicts = detect_trend_conflict(kline_60d, kline_60m, kline_15m, kline_5m)
                        risk_signals.extend(conflicts)

                        # 4. 社区情绪反向指标检测
                        sentiment_text = result.get('community_sentiment', '')
                        all_comments = []
                        try:
                            if 'comments:' in sentiment_text:
                                for line in sentiment_text.split('\n'):
                                    if 'content' in line.lower() or '追高' in line or '被套' in line or '回本' in line:
                                        all_comments.append({'content': line})
                        except:
                            pass

                        if all_comments:
                            reverse_result = analyze_sentiment_reverse_indicator(all_comments)
                            if reverse_result['is_reverse_signal']:
                                risk_signals.append({
                                    'type': '情绪反向指标',
                                    'risk_level': reverse_result['risk_level'],
                                    'description': reverse_result['description']
                                })

                        # 将风险信号添加到结果中
                        if risk_signals:
                            result['risk_signals'] = risk_signals
                            logger.info(f"      🚨 {stock_code} 检测到{len(risk_signals)}个风险信号")

                    except Exception as e:
                        logger.error(f"      ⚠️ {stock_code} 风险检测失败: {e}")

                    logger.info(f"    ✅ 批次{batch_num} - 完成{stock_code}的分析")
                    return result

                except Exception as e:
                    # 🔴 捕获所有未预期的异常，返回错误结果而不是抛出异常
                    logger.exception(f"    💥 批次{batch_num} - {stock_code}分析过程发生严重错误: {e}")
                    return {
                        'code': stock_code,
                        'technical': f'严重错误: {str(e)}',
                        'fund_flow': f'严重错误: {str(e)}',
                        'fundamental': f'严重错误: {str(e)}',
                        'news': f'严重错误: {str(e)}',
                        'tick_analysis': f'严重错误: {str(e)}',
                        'community_sentiment': f'严重错误: {str(e)}'
                    }

            # 并行分析批次内的所有股票
            with ThreadPoolExecutor(max_workers=min(len(batch_codes), 5)) as executor:
                future_to_code = {executor.submit(analyze_single_stock, code): code for code in batch_codes}

                for future in as_completed(future_to_code):
                    code = future_to_code[future]
                    try:
                        result = future.result(timeout=60)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"    ❌ 批次{batch_num} - {code}分析失败: {e}")
                        results.append({
                            'code': code,
                            'technical': f'分析失败: {str(e)}',
                            'fund_flow': f'分析失败: {str(e)}',
                            'fundamental': f'分析失败: {str(e)}',
                            'news': f'分析失败: {str(e)}',
                            'tick_analysis': f'分析失败: {str(e)}',
                            'community_sentiment': f'分析失败: {str(e)}'
                        })

            logger.info(f"  ✅ 批次{batch_num}/{total_batches} 完成（{len(results)}只股票）")
            return results

        # 4. 并行处理所有批次（关键优化点！）
        all_results = []
        with ThreadPoolExecutor(max_workers=min(total_batches, 3)) as executor:
            # 提交所有批次任务
            batch_futures = {
                executor.submit(process_batch, i, batch): i
                for i, batch in enumerate(batches)
            }

            # 收集结果
            for future in as_completed(batch_futures):
                batch_index = batch_futures[future]
                try:
                    batch_results = future.result(timeout=180)  # 每批最多3分钟
                    all_results.extend(batch_results)
                except Exception as e:
                    logger.error(f"❌ 批次{batch_index+1}处理失败: {e}")

        # 5. 保存详细分析到 AgentContext（避免上下文超长）
        try:
            from src.agents.tools.context_tools import save_agent_context
            import json

            # 构建详细分析字典
            analysis_details = {}
            for result in all_results:
                stock_code = result['code']
                analysis_details[stock_code] = {
                    'code': stock_code,
                    'cached_data': result.get('cached_data', ''),
                    'technical': result.get('technical', ''),
                    'fund_flow': result.get('fund_flow', ''),
                    'fundamental': result.get('fundamental', ''),
                    'news': result.get('news', ''),
                    'tick_analysis': result.get('tick_analysis', ''),
                    'community_sentiment': result.get('community_sentiment', ''),
                    'risk_signals': result.get('risk_signals', [])  # 🚨 新增：保存风险信号
                }

            # 保存到 AgentContext（🔴 修复：传入dict而不是JSON字符串）
            save_agent_context.func('stock_analysis_details', analysis_details)
            logger.info(f"✅ 已保存{len(analysis_details)}只股票的详细分析到 AgentContext")
        except Exception as e:
            logger.error(f"❌ 保存详细分析到 AgentContext 失败: {e}")

        # 6. 只返回极简信息（避免上下文超长）
        # 🚨 关键：不输出任何表格，只输出统计信息
        output_lines = [
            f"✅ 自动分批并行分析完成",
            f"",
            f"📊 分析统计：",
            f"  - 总股票数: {total_stocks}只",
            f"  - 总批次数: {total_batches}批（每批{batch_size}只）",
            f"  - 成功分析: {len(all_results)}只",
            f"  - 执行方式: 多批次并行（接近单批耗时）",
            f"",
            f"� 详细分析已保存到 AgentContext",
            f"  - Context Key: 'stock_analysis_details'",
            f"  - 数据格式: JSON（包含所有6维分析详情）",
            f"",
            f"🔴 下一步操作：",
            f"  1. 调用 load_agent_context('stock_analysis_details') 读取详细分析",
            f"  2. 根据详细分析给出每只股票的6维评分",
            f"  3. 保存评分结果到 AgentContext",
            f"  4. 只输出简洁的评分表格（不包含详细理由）",
            f"",
            f"⚠️ 严禁在输出中包含详细分析内容（会导致上下文超长）"
        ]

        return "\n".join(output_lines)

    except Exception as e:
        logger.error(f"自动分批并行分析失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"自动分批并行分析失败: {str(e)}"


@tool("获取五档盘口数据")
def get_five_level_quotes(stock_code: str) -> str:
    """
    获取股票的实时五档盘口数据，用于分析买卖力量对比

    Args:
        stock_code: 股票代码（如600000）

    Returns:
        五档盘口数据的自然语言描述，包括：
        - 买一到买五的价格和数量
        - 卖一到卖五的价格和数量
        - 买卖力量对比分析
        - 盘口压力分析
    """
    from src.tools.zhitu_api import ZhituAPI

    try:
        zhitu = ZhituAPI()
        data = zhitu.get_five_level_quotes(stock_code)

        if not data:
            return f"❌ 无法获取{stock_code}的五档盘口数据"

        # 解析五档数据
        # 数据格式：ps(委卖价数组), pb(委买价数组), vs(委卖量数组), vb(委买量数组), t(更新时间)
        sell_prices = data.get('ps', [])  # 卖一到卖五价格
        buy_prices = data.get('pb', [])   # 买一到买五价格
        sell_volumes = data.get('vs', []) # 卖一到卖五量
        buy_volumes = data.get('vb', [])  # 买一到买五量
        update_time = data.get('t', '')

        if not sell_prices or not buy_prices:
            return f"❌ {stock_code}的五档盘口数据不完整"

        # 计算买卖力量
        total_buy_volume = sum(buy_volumes) if buy_volumes else 0
        total_sell_volume = sum(sell_volumes) if sell_volumes else 0

        # 买卖力量对比
        if total_buy_volume > 0 and total_sell_volume > 0:
            buy_sell_ratio = total_buy_volume / total_sell_volume
            if buy_sell_ratio > 1.5:
                power_analysis = "买盘力量强劲，多方占优"
            elif buy_sell_ratio > 1.0:
                power_analysis = "买盘略强，多方稍占优"
            elif buy_sell_ratio > 0.67:
                power_analysis = "买卖力量均衡"
            elif buy_sell_ratio > 0.5:
                power_analysis = "卖盘略强，空方稍占优"
            else:
                power_analysis = "卖盘力量强劲，空方占优"
        else:
            power_analysis = "无法判断买卖力量"

        # 格式化输出
        result_lines = [
            f"=== {stock_code} 五档盘口 ===",
            f"更新时间: {update_time}",
            "",
            "【卖盘】",
        ]

        # 卖五到卖一（倒序显示）
        for i in range(min(5, len(sell_prices)) - 1, -1, -1):
            level = i + 1
            price = sell_prices[i] if i < len(sell_prices) else 0
            volume = sell_volumes[i] if i < len(sell_volumes) else 0
            result_lines.append(f"卖{level}: {price:.2f}元 × {volume}手")

        result_lines.append("")
        result_lines.append("【买盘】")

        # 买一到买五
        for i in range(min(5, len(buy_prices))):
            level = i + 1
            price = buy_prices[i] if i < len(buy_prices) else 0
            volume = buy_volumes[i] if i < len(buy_volumes) else 0
            result_lines.append(f"买{level}: {price:.2f}元 × {volume}手")

        result_lines.append("")
        result_lines.append("【力量对比】")
        result_lines.append(f"买盘总量: {total_buy_volume}手")
        result_lines.append(f"卖盘总量: {total_sell_volume}手")
        result_lines.append(f"买卖比: {buy_sell_ratio:.2f}" if total_sell_volume > 0 else "买卖比: N/A")
        result_lines.append(f"分析: {power_analysis}")

        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"获取五档盘口失败: {e}")
        return f"❌ 获取{stock_code}五档盘口失败: {str(e)}"


@tool("获取逐笔交易数据")
def get_tick_by_tick(stock_code: str, limit: int = 20) -> str:
    """
    获取股票的当天逐笔交易数据，用于分析资金流向和交易活跃度

    Args:
        stock_code: 股票代码（如600000）
        limit: 返回最近N笔交易，默认20笔

    Returns:
        逐笔交易数据的自然语言描述，包括：
        - 最近N笔交易的时间、价格、成交量、方向
        - 主动买入和主动卖出的统计
        - 大单交易分析
        - 资金流向判断
    """
    from src.tools.zhitu_api import ZhituAPI

    try:
        zhitu = ZhituAPI()
        data = zhitu.get_tick_by_tick(stock_code)

        if not data:
            return f"❌ 无法获取{stock_code}的逐笔交易数据"

        # ✅ 取最近N笔交易（倒序，最新的在前面）
        if isinstance(data, list):
            # 取最后N笔（最新的），然后倒序显示
            ticks = data[-limit:] if len(data) > limit else data
            # 倒序，让最新的在最前面
            ticks = list(reversed(ticks))
        else:
            ticks = []

        if not ticks:
            return f"❌ {stock_code}暂无逐笔交易数据"

        # ✅ 第一步：统计所有交易（用于统计分析）
        buy_count = 0
        sell_count = 0
        buy_volume = 0
        sell_volume = 0
        big_buy_count = 0  # 大单买入（>100手）
        big_sell_count = 0  # 大单卖出（>100手）

        # 数据格式：d(日期), t(时间), v(成交量), p(成交价), ts(交易方向: 1=主动买入, 2=主动卖出, 0=中性)
        for tick in ticks:
            direction = tick.get('ts', 0)
            volume = tick.get('v', 0)

            if direction == 1:
                buy_count += 1
                buy_volume += volume
                if volume > 100:
                    big_buy_count += 1
            elif direction == 2:
                sell_count += 1
                sell_volume += volume
                if volume > 100:
                    big_sell_count += 1

        # ✅ 第二步：显示前10笔交易明细
        result_lines = [
            f"=== {stock_code} 逐笔交易（最近{len(ticks)}笔）===",
            "",
            "【交易明细】",
        ]

        for i, tick in enumerate(ticks[:10], 1):  # 只显示前10笔
            trade_time = tick.get('t', '')
            volume = tick.get('v', 0)
            price = tick.get('p', 0)
            direction = tick.get('ts', 0)

            # 判断方向
            if direction == 1:
                direction_str = "买入"
            elif direction == 2:
                direction_str = "卖出"
            else:
                direction_str = "中性"

            # 标记大单
            size_mark = "🔥" if volume > 100 else ""

            result_lines.append(
                f"{i}. {trade_time} | {price:.2f}元 × {volume}手 | {direction_str} {size_mark}"
            )

        # 资金流向分析
        if buy_volume > sell_volume * 1.5:
            flow_analysis = "资金大幅流入，买盘活跃"
        elif buy_volume > sell_volume:
            flow_analysis = "资金净流入，买盘占优"
        elif sell_volume > buy_volume * 1.5:
            flow_analysis = "资金大幅流出，卖盘活跃"
        elif sell_volume > buy_volume:
            flow_analysis = "资金净流出，卖盘占优"
        else:
            flow_analysis = "资金流向均衡"

        result_lines.append("")
        result_lines.append("【统计分析】")
        result_lines.append(f"主动买入: {buy_count}笔，共{buy_volume}手")
        result_lines.append(f"主动卖出: {sell_count}笔，共{sell_volume}手")
        result_lines.append(f"大单买入: {big_buy_count}笔（>100手）")
        result_lines.append(f"大单卖出: {big_sell_count}笔（>100手）")
        result_lines.append(f"资金流向: {flow_analysis}")

        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"获取逐笔交易失败: {e}")
        return f"❌ 获取{stock_code}逐笔交易失败: {str(e)}"
