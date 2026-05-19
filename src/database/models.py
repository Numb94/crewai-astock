#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock V2.0 - 数据库 ORM 模型

作者: AI Architect
版本: v2.0.5-db-complete
日期: 2025-10-21
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Time,
    Text, Boolean, JSON, ForeignKey, Index, DECIMAL
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ========================================
# 1. 候选股票池表
# ========================================
class Candidate(Base):
    """候选股票池 - 系统推荐的股票"""
    __tablename__ = 'candidates'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50))
    recommend_time = Column(DateTime, nullable=False, default=datetime.now)
    recommend_track = Column(String(20))  # track1_tail / track2_next

    # 推荐信息
    expected_buy_time = Column(DateTime)
    can_sell_date = Column(Date)
    strategy_name = Column(String(50), index=True)

    # 评分信息
    final_score = Column(DECIMAL(5, 2))
    cto_score = Column(DECIMAL(5, 2))
    cfo_score = Column(DECIMAL(5, 2))
    cmo_score = Column(DECIMAL(5, 2))
    cso_score = Column(DECIMAL(5, 2))

    # CEO 决策
    ceo_decision = Column(String(20))  # STRONG_BUY/BUY/HOLD/PASS
    ceo_reason = Column(Text)

    # CRO 审核
    cro_approved = Column(Boolean, default=False)
    cro_risk_level = Column(String(20))  # low/medium/high

    # 推荐价格
    recommend_price = Column(DECIMAL(10, 3))  # ✅ 修改为3位小数
    target_price = Column(DECIMAL(10, 3))  # ✅ 修改为3位小数

    # ✅ 新增：买入时机建议
    buy_timing = Column(String(50))  # tomorrow_open/today_now/wait_dip
    buy_timing_cn = Column(String(50))  # 明日开盘买入/立即买入/等待回调买入
    buy_urgency = Column(String(20))  # high/medium/low
    buy_price_range_min = Column(DECIMAL(10, 3))  # ✅ 建议买入价格区间（最低）修改为3位小数
    buy_price_range_max = Column(DECIMAL(10, 3))  # ✅ 建议买入价格区间（最高）修改为3位小数
    buy_timing_reason = Column(Text)  # 买入时机理由

    # ✅ 新增：操作建议（考虑当前持仓）
    operation_suggestion = Column(Text)  # 操作建议：直接买入/先卖出XXX再买入/保留XXX用剩余资金买入
    position_comparison = Column(Text)  # 持仓对比分析（如果有持仓）

    # ✅ 新增：绩效跟踪字段（2025-11-12）
    next_day_open_price = Column(DECIMAL(10, 3))  # ✅ 次日开盘价（修改为3位小数）
    next_day_high_price = Column(DECIMAL(10, 3))  # ✅ 次日最高价（修改为3位小数）
    next_day_close_price = Column(DECIMAL(10, 3))  # ✅ 次日收盘价（修改为3位小数）
    actual_open_profit_pct = Column(DECIMAL(10, 2))  # 开盘价收益率
    actual_high_profit_pct = Column(DECIMAL(10, 2))  # 最高价收益率
    actual_close_profit_pct = Column(DECIMAL(10, 2))  # 收盘价收益率
    is_rush_high_pullback = Column(Boolean, default=False)  # 是否冲高回落
    performance_updated_at = Column(DateTime)  # 绩效更新时间

    created_at = Column(DateTime, default=datetime.now)


# ========================================
# 2. 持仓表
# ========================================
class Position(Base):
    """当前持仓"""
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50))

    # 买入信息
    buy_date = Column(Date, nullable=False)
    buy_time = Column(Time)
    buy_price = Column(DECIMAL(10, 3), nullable=False)  # ✅ 修改为3位小数
    quantity = Column(Integer, nullable=False)
    buy_amount = Column(DECIMAL(15, 2))  # 买入金额

    # T+1 约束
    can_sell_date = Column(Date, nullable=False, index=True)  # 最早可卖日期

    # 使用策略
    strategy_used = Column(String(50))
    recommend_track = Column(String(20))  # track1_tail / track2_next

    # 当前状态
    current_price = Column(DECIMAL(10, 3))  # ✅ 修改为3位小数
    profit_loss = Column(DECIMAL(15, 2))  # 浮动盈亏金额
    profit_loss_pct = Column(DECIMAL(5, 2))  # 浮动盈亏百分比

    # 持仓状态
    status = Column(String(20), default='holding', index=True)  # holding/sold

    # 卖出信息（当status='sold'时填充）
    sell_date = Column(Date)  # 卖出日期
    sell_time = Column(Time)  # 卖出时间
    sell_price = Column(DECIMAL(10, 3))  # ✅ 卖出价格（修改为3位小数）

    # CFO 仓位管理
    position_pct = Column(DECIMAL(5, 2))  # 占总资金百分比

    # AI分析结果（缓存）
    ai_sell_suggestion = Column(String(50))  # 强烈建议卖出/建议卖出/建议持有/建议观望
    ai_sell_reason = Column(Text)  # AI分析理由
    ai_urgency = Column(String(20))  # high/medium/low
    ai_analysis_time = Column(DateTime)  # AI分析时间

    # 五档盘口分析      
    ai_bid_ask_ratio = Column(DECIMAL(5, 2))  # 买卖比
    ai_bid_ask_analysis = Column(Text)  # 盘口分析

    # 逐笔交易分析
    ai_fund_flow = Column(String(50))  # 资金流向：净流入/净流出/均衡
    ai_fund_flow_analysis = Column(Text)  # 资金流向分析

    # 技术指标分析
    ai_technical_analysis = Column(Text)  # 技术指标分析

    # ✅ 推送去重机制
    last_push_time = Column(DateTime)  # 上次推送时间
    last_push_suggestion = Column(String(50))  # 上次推送的建议
    push_count_today = Column(Integer, default=0)  # 今日推送次数

    # ✅ 移动止盈机制（T+1）
    today_open_price = Column(DECIMAL(10, 3))  # ✅ 可卖日期当天的开盘价（修改为3位小数）
    today_highest_price = Column(DECIMAL(10, 3))  # ✅ 可卖日期当天的最高价（修改为3位小数）
    today_highest_time = Column(DateTime)  # 最高价出现时间
    trailing_stop_triggered = Column(Boolean, default=False)  # 移动止盈是否已触发

    # ✅ 新增：生命周期跟踪字段（2025-11-12）
    stop_loss_triggered = Column(Boolean, default=False)  # 止损是否触发
    stop_loss_price = Column(DECIMAL(10, 3))  # ✅ 止损触发价格（修改为3位小数）
    stop_loss_time = Column(DateTime)  # 止损触发时间
    sell_reason = Column(String(50))  # 卖出原因：止盈/止损/手动/其他
    max_profit_pct = Column(DECIMAL(10, 2))  # 持仓期间最大盈利百分比
    max_loss_pct = Column(DECIMAL(10, 2))  # 持仓期间最大亏损百分比

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


# ========================================
# 3. 交易记录表
# ========================================
class Transaction(Base):
    """交易记录 - 所有买卖操作"""
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50))

    # 交易类型
    trade_type = Column(String(10), nullable=False)  # BUY/SELL
    trade_date = Column(Date, nullable=False, index=True)
    trade_time = Column(Time)

    # 交易详情
    price = Column(DECIMAL(10, 3), nullable=False)  # ✅ 修改为3位小数
    quantity = Column(Integer, nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)  # 交易金额
    fee = Column(DECIMAL(10, 2))  # 手续费

    # 策略信息
    strategy_used = Column(String(50))

    # 卖出时的盈亏 (仅 SELL 类型)
    profit_loss = Column(DECIMAL(15, 2))
    profit_loss_pct = Column(DECIMAL(5, 2))

    # 关联持仓
    position_id = Column(Integer, ForeignKey('positions.id'))

    # ✅ 新增：决策依据字段（2025-11-12）
    decision_reason = Column(String(200))  # 交易决策依据
    decision_agent = Column(String(50))  # 决策Agent名称
    related_recommendation_id = Column(Integer)  # 关联推荐ID

    created_at = Column(DateTime, default=datetime.now)


# ========================================
# 4. 复盘记录表
# ========================================
class Review(Base):
    """复盘记录 - 每日盘后复盘"""
    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    review_date = Column(Date, nullable=False, index=True)  # ✅ 移除unique，改为联合唯一索引
    review_time = Column(DateTime, default=datetime.now)

    # 交易数据统计
    total_trades = Column(Integer, default=0)
    win_trades = Column(Integer, default=0)
    loss_trades = Column(Integer, default=0)
    win_rate = Column(DECIMAL(5, 2))

    # 收益指标
    total_profit_loss = Column(DECIMAL(15, 2))
    total_profit_loss_pct = Column(DECIMAL(5, 2))
    daily_return = Column(DECIMAL(15, 2))
    daily_return_pct = Column(DECIMAL(5, 2))

    # 策略表现 (JSON)
    strategy_performance = Column(JSON)
    # {
    #   "龙头战法": {"trades": 5, "win_rate": 80, "return_pct": 15.2},
    #   "低吸埋伏": {"trades": 3, "win_rate": 66.7, "return_pct": 8.5}
    # }

    # 风险指标
    max_drawdown = Column(DECIMAL(5, 2))
    sharpe_ratio = Column(DECIMAL(5, 2))

    # 复盘总结
    ceo_summary = Column(Text)
    cso_suggestions = Column(Text)
    cro_risk_events = Column(Text)

    # 次日推荐 (Track 2 盘后推荐)
    next_day_recommendations = Column(JSON)

    created_at = Column(DateTime, default=datetime.now)


# ========================================
# 5. Agent 记忆表
# ========================================
class AgentMemory(Base):
    """Agent 记忆 - 记录 Agent 的历史决策"""
    __tablename__ = 'agent_memory'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    agent_name = Column(String(50), nullable=False, index=True)
    memory_date = Column(Date, nullable=False, index=True)

    # 记忆内容
    memory_type = Column(String(50))  # decision/learning/reflection
    memory_content = Column(Text)

    # 关联信息
    stock_code = Column(String(10))
    strategy_name = Column(String(50))

    # 决策结果
    decision_result = Column(String(20))  # success/failed/pending

    created_at = Column(DateTime, default=datetime.now)


# ========================================
# 6. 市场情绪表
# ========================================
class MarketSentiment(Base):
    """市场情绪 - 每日市场状态记录"""
    __tablename__ = 'market_sentiment'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    sentiment_date = Column(Date, nullable=False, index=True)  # ✅ 移除unique，改为联合唯一索引

    # 市场状态
    market_state = Column(String(20), nullable=False, index=True)  # hot/warm/neutral/cold/panic
    sentiment_score = Column(DECIMAL(5, 2), nullable=False)

    # 市场数据
    limit_up_count = Column(Integer)
    limit_down_count = Column(Integer)
    gain_count = Column(Integer)
    loss_count = Column(Integer)
    gain_loss_ratio = Column(DECIMAL(5, 2))
    turnover_rate = Column(DECIMAL(5, 2))

    # 热点题材
    hot_topics = Column(JSON)
    # [{"topic": "AI", "count": 15, "strength": 95}, ...]

    # CMO 分析
    cmo_analysis = Column(Text)

    created_at = Column(DateTime, default=datetime.now)

    # ✅ 联合唯一索引
    __table_args__ = (
        Index('idx_market_sentiment_unique', 'session_id', 'sentiment_date', unique=True),
    )


# ========================================
# 7. 系统配置表
# ========================================
class SystemConfig(Base):
    """系统配置 - 动态配置参数"""
    __tablename__ = 'system_config'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    config_key = Column(String(100), nullable=False, index=True)  # ✅ 移除unique，改为联合唯一索引
    config_value = Column(Text, nullable=False)
    config_type = Column(String(20))  # string/int/float/bool/json
    description = Column(Text)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    # ✅ 联合唯一索引
    __table_args__ = (
        Index('idx_system_config_unique', 'session_id', 'config_key', unique=True),
    )


# ========================================
# 8. 策略执行记录表
# ========================================
class StrategyExecution(Base):
    """策略执行记录"""
    __tablename__ = 'strategy_executions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    execution_date = Column(Date, nullable=False, index=True)
    market_state = Column(String(20))
    sentiment_score = Column(DECIMAL(5, 2))

    # 策略组合
    primary_strategy = Column(String(50))
    secondary_strategy = Column(String(50))
    primary_weight = Column(DECIMAL(3, 2))
    secondary_weight = Column(DECIMAL(3, 2))

    # CEO 决策
    ceo_decision = Column(Text)
    recommended_stocks = Column(JSON)

    # 执行结果
    actual_buy_stocks = Column(JSON)
    execution_result = Column(String(20))  # success/partial/failed

    created_at = Column(DateTime, default=datetime.now)

    # 索引
    __table_args__ = (
        Index('idx_strategy_exec_date', 'execution_date'),
        Index('idx_strategy_exec_state', 'market_state'),
    )


# ========================================
# 9. 策略绩效表
# ========================================
class StrategyPerformance(Base):
    """策略绩效"""
    __tablename__ = 'strategy_performance'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    strategy_name = Column(String(50), nullable=False, index=True)

    # 统计周期
    period_start = Column(Date)
    period_end = Column(Date)

    # 绩效指标
    total_trades = Column(Integer, default=0)
    win_trades = Column(Integer, default=0)
    loss_trades = Column(Integer, default=0)
    win_rate = Column(DECIMAL(5, 2))

    avg_profit = Column(DECIMAL(10, 2))
    avg_loss = Column(DECIMAL(10, 2))
    profit_loss_ratio = Column(DECIMAL(5, 2))

    total_return = Column(DECIMAL(10, 2))
    total_return_pct = Column(DECIMAL(5, 2))

    max_drawdown = Column(DECIMAL(5, 2))
    sharpe_ratio = Column(DECIMAL(5, 2))

    # 策略权重 (自适应调整)
    current_weight = Column(DECIMAL(3, 2), default=1.0)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ========================================
# 10. 策略权重表
# ========================================
class StrategyWeight(Base):
    """策略权重 - 用于自进化"""
    __tablename__ = 'strategy_weights'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    strategy_name = Column(String(50), nullable=False, index=True)

    # 权重数据
    current_weight = Column(DECIMAL(3, 2), default=1.0)
    previous_weight = Column(DECIMAL(3, 2))
    weight_change = Column(DECIMAL(3, 2))

    # 30日滚动绩效
    rolling_30d_win_rate = Column(DECIMAL(5, 2))
    rolling_30d_return_pct = Column(DECIMAL(5, 2))
    rolling_30d_sharpe_ratio = Column(DECIMAL(5, 2))
    rolling_30d_trades = Column(Integer, default=0)

    # 权重调整原因
    adjustment_reason = Column(Text)

    # 状态控制
    is_enabled = Column(Boolean, default=True)
    is_forbidden = Column(Boolean, default=False)

    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_review_date = Column(Date, index=True)

    # ✅ 联合唯一索引
    __table_args__ = (
        Index('idx_strategy_weights_name', 'strategy_name'),
        Index('idx_strategy_weights_unique', 'session_id', 'strategy_name', 'last_review_date', unique=True),
    )


# ========================================
# 11. Agent 决策日志表
# ========================================
class AgentDecisionLog(Base):
    """Agent 决策日志"""
    __tablename__ = 'agent_decision_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    agent_name = Column(String(50), nullable=False, index=True)
    decision_time = Column(DateTime, nullable=False, index=True)

    # 决策内容
    stock_code = Column(String(10))
    decision_type = Column(String(20))  # score/approve/reject/warning
    decision_content = Column(Text)

    # 评分 (如果是评分型决策)
    score = Column(DECIMAL(5, 2))
    confidence = Column(DECIMAL(3, 2))

    # 关联信息
    strategy_execution_id = Column(Integer, ForeignKey('strategy_executions.id'))

    created_at = Column(DateTime, default=datetime.now)


# ========================================
# 12. 会议日志表
# ========================================
class MeetingLog(Base):
    """会议日志"""
    __tablename__ = 'meeting_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    meeting_type = Column(String(20), nullable=False, index=True)  # morning/emergency/evening
    meeting_date = Column(Date, nullable=False, index=True)
    meeting_start_time = Column(DateTime, nullable=False)
    meeting_end_time = Column(DateTime)

    # 会议参与者
    participants = Column(String(200))
    host_agent = Column(String(50))

    # 会议内容
    meeting_topic = Column(String(200))
    meeting_transcript = Column(Text)  # 完整会议记录

    # 会议决策 (JSON)
    decisions = Column(JSON)

    # 关联策略执行记录
    strategy_execution_id = Column(Integer, ForeignKey('strategy_executions.id'))

    created_at = Column(DateTime, default=datetime.now)


# ========================================
# 股票概念板块表
# ========================================
class StockConcepts(Base):
    """股票概念板块表"""
    __tablename__ = 'stock_concepts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, index=True)
    tag = Column(String(100), nullable=False)
    category = Column(String(50))  # 所属板块/概念/行业
    weight = Column(Float)  # 权重
    extra = Column(Text)  # 额外信息（JSON格式）
    updated_at = Column(DateTime, default=datetime.now)


# ========================================
# 19. Agent上下文表（新增）
# ========================================
class AgentContext(Base):
    """Agent上下文表 - 存储Agent间传递的结构化数据"""
    __tablename__ = 'agent_context'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ✅ 多用户支持：Session ID
    session_id = Column(String(100), nullable=False, index=True, default='default')

    # 上下文类型
    # 可选值：
    # - 'recommended_count': 推荐数量
    # - 'strategy_name': 策略名称
    # - 'screening_params': 筛选参数
    # - 'market_state': 市场状态
    # - 'candidate_stocks': 候选股列表
    context_type = Column(String(50), nullable=False, index=True)

    # 上下文数据（JSON格式）
    # 示例：
    # - recommended_count: {"count": 2, "reason": "总资产15万，推荐2只"}
    # - strategy_name: {"name": "龙头战法", "reason": "市场HOT，历史胜率75%"}
    # - screening_params: {"price_change_min": 5, "price_change_max": 9, ...}
    context_data = Column(JSON, nullable=False)

    # 创建时间
    created_at = Column(DateTime, default=datetime.now, index=True)

    # 索引：session_id + context_type 联合索引
    __table_args__ = (
        Index('idx_session_type', 'session_id', 'context_type'),
    )


# ========================================
# 14. 市场新闻表
# ========================================
class MarketNews(Base):
    """市场新闻表 - 存储监控到的市场新闻（全局共享，不区分用户）"""
    __tablename__ = 'market_news'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 新闻基本信息
    title = Column(String(500), nullable=False)
    content = Column(Text)
    source = Column(String(100))  # 新闻来源
    url = Column(String(500))

    # 时间信息
    publish_time = Column(DateTime, index=True)  # 发布时间
    monitor_time = Column(DateTime, default=datetime.now, index=True)  # 监控时间

    # 紧急程度
    urgency = Column(String(20), index=True)  # critical/high/medium/low
    urgency_score = Column(Integer)  # 紧急程度评分
    time_weight = Column(DECIMAL(3, 2))  # 时效性权重

    # 关键词
    matched_keywords = Column(JSON)  # 匹配的关键词列表

    # 处理状态
    is_pushed = Column(Boolean, default=False, index=True)  # 是否已推送
    push_time = Column(DateTime)  # 推送时间
    is_analyzed = Column(Boolean, default=False)  # 是否已被AI分析

    # 关联信息
    related_stocks = Column(JSON)  # 相关股票代码列表
    related_topics = Column(JSON)  # 相关主题/板块

    created_at = Column(DateTime, default=datetime.now)

    # ✅ 联合唯一索引（防止重复新闻）
    __table_args__ = (
        Index('idx_news_unique', 'title', 'source', unique=True),
        Index('idx_news_urgency_time', 'urgency', 'monitor_time'),  # 按紧急程度和时间查询
    )


# ========================================
# 导出所有模型和数据库连接
# ========================================
__all__ = [
    # ORM Base
    'Base',

    # 所有模型类
    'Candidate',
    'Position',
    'Transaction',
    'Review',
    'AgentMemory',
    'MarketSentiment',
    'SystemConfig',
    'StrategyExecution',
    'StrategyPerformance',
    'StrategyWeight',
    'AgentDecisionLog',
    'MeetingLog',
    'StockConcepts',
    'AgentContext',  # Agent上下文表
    'MarketNews',  # 市场新闻表
]
