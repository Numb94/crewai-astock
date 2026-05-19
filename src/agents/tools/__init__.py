#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - Agent工具包

为CrewAI Agent提供各种数据查询和操作工具
"""

# 数据库工具
from .database_tools import (
    # query_yesterday_performance,  # ❌ 已删除：功能与analyze_recommendation_performance(days=-1)重复
    query_strategy_performance,
    query_total_assets,  # ✅ 查询总资产
    calculate_recommended_count,  # ✅ 新增：自动计算推荐数量
    save_recommendations_to_db
)
from .recommendation_performance import analyze_recommendation_performance  # ✅ 新增：推荐绩效分析

# 市场数据工具
from .market_tools import (
    get_market_sentiment,
    dynamic_screen_stocks,
    get_technical_indicators,
    get_fund_flow,
    get_fundamental_data,
    analyze_stocks_parallel,
    analyze_all_stocks_auto_batch,  # 🚀 自动分批并行分析（多批次并行）
    get_realtime_prices,  # 批量获取实时价格
    get_five_level_quotes,  # 五档盘口
    get_tick_by_tick  # 逐笔交易（用于候选股分析）
)
from .market_phase_analyzer import identify_market_phase  # 市场阶段分析

# 持仓管理工具
from .position_tools import (
    query_current_positions,
    query_recently_sold_positions,  # 🔴 查询最近卖出的股票
    calculate_portfolio_risk,
    update_trailing_stop_data,  # ✅ 移动止盈数据更新
    # 🆕 隔夜短线策略工具
    check_opening_signal,  # 检查开盘信号（集合竞价/开盘价）
    calculate_5min_atr,  # 5分钟ATR计算（短线波动判断）
    check_morning_time_window  # 早盘时间窗口检查（10:30前强制提醒）
)

# 新闻分析工具
from .news_tools import (
    search_market_news,
    search_stock_news,
    analyze_news_sentiment
)

# 社区情绪分析工具
from .community_sentiment_tools import (
    get_stock_community_comments,
    get_xueqiu_comments,
    get_eastmoney_comments,
    get_taoguba_comments
)

# 推送通知工具
from .notification_tools import (
    send_push_notification,
    send_stock_recommendation,
    send_alert_notification
)

# Agent上下文管理工具
from .context_tools import (
    save_agent_context,
    load_agent_context,
    clear_agent_context
)

# 逐笔数据分析工具
from .tick_data_tools import (
    get_smart_tick_analysis,  # 智能逐笔数据分析（优先当天，无数据则历史）
    get_today_tick_analysis   # 当天逐笔数据分析（仅当天，用于持仓监控）
)

__all__ = [
    # 数据库工具
    # 'query_yesterday_performance',  # ❌ 已删除：功能与analyze_recommendation_performance(days=-1)重复
    'query_strategy_performance',
    'analyze_recommendation_performance',  # ✅ 推荐绩效分析
    'query_total_assets',  # ✅ 查询总资产
    'calculate_recommended_count',  # ✅ 新增：自动计算推荐数量
    'save_recommendations_to_db',

    # 市场数据工具
    'get_market_sentiment',
    'identify_market_phase',  # 市场阶段分析
    'dynamic_screen_stocks',
    'get_technical_indicators',
    'get_fund_flow',
    'get_fundamental_data',
    'analyze_stocks_parallel',
    'analyze_all_stocks_auto_batch',  # 🚀 自动分批并行分析（多批次并行）
    'get_realtime_prices',  # 批量获取实时价格
    'get_five_level_quotes',  # 五档盘口
    'get_tick_by_tick',  # 逐笔交易（用于候选股分析）

    # 持仓管理工具
    'query_current_positions',
    'query_recently_sold_positions',  # 🔴 查询最近卖出的股票
    'calculate_portfolio_risk',
    'update_trailing_stop_data',  # ✅ 移动止盈数据更新
    # 🆕 隔夜短线策略工具
    'check_opening_signal',  # 检查开盘信号
    'calculate_5min_atr',  # 5分钟ATR计算
    'check_morning_time_window',  # 早盘时间窗口检查

    # 新闻分析工具
    'search_market_news',
    'search_stock_news',
    'analyze_news_sentiment',

    # 社区情绪分析工具
    'get_stock_community_comments',
    'get_xueqiu_comments',
    'get_eastmoney_comments',
    'get_taoguba_comments',

    # 推送通知工具
    'send_push_notification',
    'send_stock_recommendation',
    'send_alert_notification',

    # Agent上下文管理工具
    'save_agent_context',
    'load_agent_context',
    'clear_agent_context',

    # 逐笔数据分析工具
    'get_smart_tick_analysis',  # 智能逐笔数据分析（用于选股）
    'get_today_tick_analysis',  # 当天逐笔数据分析（用于持仓监控）
]
