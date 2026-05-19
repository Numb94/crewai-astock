#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock V2.0 - 数据库管理器 (CRUD 工具)

提供数据库操作的统一接口

作者: AI Architect
版本: v2.0.5-db-complete
日期: 2025-10-21
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from contextlib import contextmanager

from sqlalchemy import create_engine, desc, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger
from dotenv import load_dotenv

from src.database.models import (
    Base,
    Candidate,
    Position,
    Transaction,
    Review,
    AgentMemory,
    MarketSentiment,
    SystemConfig,
    StrategyExecution,
    StrategyPerformance,
    StrategyWeight,
    AgentDecisionLog,
    MeetingLog
)

load_dotenv()


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_url: str = None):
        """初始化数据库管理器

        Args:
            db_url: 数据库 URL，默认从环境变量读取
        """
        if db_url is None:
            db_path = os.getenv('DATABASE_PATH', 'data/stock_trading.db')
            # 确保数据库所在目录存在
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            db_url = f'sqlite:///{db_path}'

        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={'check_same_thread': False}
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        # ✅ 自动建表（幂等：已存在的表不会被修改 / 重建）
        # 避免开源用户首次启动时遇到 "no such table" 错误
        try:
            from sqlalchemy import inspect
            inspector = inspect(self.engine)
            existing_tables = set(inspector.get_table_names())
            expected_tables = set(Base.metadata.tables.keys())
            missing = expected_tables - existing_tables
            if missing:
                logger.info(f"📦 检测到 {len(missing)} 张表缺失，自动建表: {sorted(missing)}")
                Base.metadata.create_all(self.engine)
                logger.success(f"✅ 数据库表已就绪（共 {len(expected_tables)} 张）")
        except Exception as e:
            logger.error(f"⚠️ 自动建表失败: {e}（请手动运行 python -m src.database.init_db）")

    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话 (上下文管理器)

        用法:
            with db.get_session() as session:
                session.add(obj)
                session.commit()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()

    # ========================================
    # 候选股票池 (Candidate) CRUD
    # ========================================

    def add_candidate(self, **kwargs) -> Candidate:
        """添加候选股票"""
        with self.get_session() as session:
            candidate = Candidate(**kwargs)
            session.add(candidate)
            session.flush()
            return candidate

    def get_candidates(
        self,
        recommend_date: date = None,
        track: str = None,
        strategy: str = None,
        limit: int = 10
    ) -> List[Candidate]:
        """查询候选股票"""
        with self.get_session() as session:
            query = session.query(Candidate)

            if recommend_date:
                query = query.filter(
                    Candidate.recommend_time >= datetime.combine(recommend_date, datetime.min.time()),
                    Candidate.recommend_time < datetime.combine(recommend_date, datetime.max.time())
                )
            if track:
                query = query.filter(Candidate.recommend_track == track)
            if strategy:
                query = query.filter(Candidate.strategy_name == strategy)

            return query.order_by(desc(Candidate.final_score)).limit(limit).all()

    # ========================================
    # 持仓 (Position) CRUD
    # ========================================

    def add_position(self, **kwargs) -> Position:
        """添加持仓"""
        with self.get_session() as session:
            position = Position(**kwargs)
            session.add(position)
            session.flush()
            return position

    def get_positions(self, status: str = 'holding') -> List[Position]:
        """查询持仓"""
        with self.get_session() as session:
            return session.query(Position).filter(Position.status == status).all()

    def update_position(self, position_id: int, **kwargs) -> Position:
        """更新持仓"""
        with self.get_session() as session:
            position = session.query(Position).filter(Position.id == position_id).first()
            if position:
                for key, value in kwargs.items():
                    setattr(position, key, value)
                session.flush()
            return position

    def close_position(self, position_id: int) -> Position:
        """平仓"""
        return self.update_position(position_id, status='sold')

    # ========================================
    # 交易记录 (Transaction) CRUD
    # ========================================

    def add_transaction(self, **kwargs) -> Transaction:
        """添加交易记录"""
        with self.get_session() as session:
            transaction = Transaction(**kwargs)
            session.add(transaction)
            session.flush()
            return transaction

    def get_transactions(
        self,
        trade_date: date = None,
        trade_type: str = None,
        stock_code: str = None
    ) -> List[Transaction]:
        """查询交易记录"""
        with self.get_session() as session:
            query = session.query(Transaction)

            if trade_date:
                query = query.filter(Transaction.trade_date == trade_date)
            if trade_type:
                query = query.filter(Transaction.trade_type == trade_type)
            if stock_code:
                query = query.filter(Transaction.stock_code == stock_code)

            return query.order_by(desc(Transaction.trade_time)).all()

    # ========================================
    # 复盘记录 (Review) CRUD
    # ========================================

    def add_review(self, **kwargs) -> Review:
        """添加复盘记录"""
        with self.get_session() as session:
            review = Review(**kwargs)
            session.add(review)
            session.flush()
            return review

    def get_review(self, review_date: date) -> Optional[Review]:
        """获取指定日期的复盘记录"""
        with self.get_session() as session:
            return session.query(Review).filter(Review.review_date == review_date).first()

    def get_reviews(self, limit: int = 30) -> List[Review]:
        """获取最近的复盘记录"""
        with self.get_session() as session:
            return session.query(Review).order_by(desc(Review.review_date)).limit(limit).all()

    # ========================================
    # 市场情绪 (MarketSentiment) CRUD
    # ========================================

    def add_market_sentiment(self, **kwargs) -> MarketSentiment:
        """添加市场情绪记录"""
        with self.get_session() as session:
            sentiment = MarketSentiment(**kwargs)
            session.add(sentiment)
            session.flush()
            return sentiment

    def get_market_sentiment(self, sentiment_date: date) -> Optional[MarketSentiment]:
        """获取指定日期的市场情绪"""
        with self.get_session() as session:
            return session.query(MarketSentiment).filter(
                MarketSentiment.sentiment_date == sentiment_date
            ).first()

    def get_latest_market_state(self) -> Optional[str]:
        """获取最新的市场状态"""
        with self.get_session() as session:
            sentiment = session.query(MarketSentiment).order_by(
                desc(MarketSentiment.sentiment_date)
            ).first()
            return sentiment.market_state if sentiment else None

    # ========================================
    # 系统配置 (SystemConfig) CRUD
    # ========================================

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self.get_session() as session:
            config = session.query(SystemConfig).filter(SystemConfig.config_key == key).first()
            if not config:
                return default

            # 根据类型转换
            if config.config_type == 'int':
                return int(config.config_value)
            elif config.config_type == 'float':
                return float(config.config_value)
            elif config.config_type == 'bool':
                return config.config_value.lower() in ('true', '1', 'yes')
            else:
                return config.config_value

    def set_config(self, key: str, value: Any, config_type: str = 'string', description: str = ''):
        """设置配置值"""
        with self.get_session() as session:
            config = session.query(SystemConfig).filter(SystemConfig.config_key == key).first()

            if config:
                config.config_value = str(value)
                config.updated_at = datetime.now()
            else:
                config = SystemConfig(
                    config_key=key,
                    config_value=str(value),
                    config_type=config_type,
                    description=description
                )
                session.add(config)

    # ========================================
    # 策略权重 (StrategyWeight) CRUD
    # ========================================

    def get_strategy_weights(self) -> List[StrategyWeight]:
        """获取所有策略权重"""
        with self.get_session() as session:
            return session.query(StrategyWeight).filter(StrategyWeight.is_enabled == True).all()

    def update_strategy_weight(self, strategy_name: str, **kwargs) -> StrategyWeight:
        """更新策略权重"""
        with self.get_session() as session:
            weight = session.query(StrategyWeight).filter(
                StrategyWeight.strategy_name == strategy_name
            ).order_by(desc(StrategyWeight.updated_at)).first()

            if weight:
                for key, value in kwargs.items():
                    setattr(weight, key, value)
                session.flush()
            return weight

    # ========================================
    # 会议日志 (MeetingLog) CRUD
    # ========================================

    def add_meeting_log(self, **kwargs) -> MeetingLog:
        """添加会议日志"""
        with self.get_session() as session:
            meeting = MeetingLog(**kwargs)
            session.add(meeting)
            session.flush()
            return meeting

    def get_meeting_logs(
        self,
        meeting_type: str = None,
        meeting_date: date = None,
        limit: int = 10
    ) -> List[MeetingLog]:
        """查询会议日志"""
        with self.get_session() as session:
            query = session.query(MeetingLog)

            if meeting_type:
                query = query.filter(MeetingLog.meeting_type == meeting_type)
            if meeting_date:
                query = query.filter(MeetingLog.meeting_date == meeting_date)

            return query.order_by(desc(MeetingLog.meeting_start_time)).limit(limit).all()

    # ========================================
    # Agent 决策日志 (AgentDecisionLog) CRUD
    # ========================================

    def add_agent_decision(self, **kwargs) -> AgentDecisionLog:
        """添加 Agent 决策日志"""
        with self.get_session() as session:
            decision = AgentDecisionLog(**kwargs)
            session.add(decision)
            session.flush()
            return decision

    def get_agent_decisions(
        self,
        agent_name: str = None,
        stock_code: str = None,
        limit: int = 100
    ) -> List[AgentDecisionLog]:
        """查询 Agent 决策日志"""
        with self.get_session() as session:
            query = session.query(AgentDecisionLog)

            if agent_name:
                query = query.filter(AgentDecisionLog.agent_name == agent_name)
            if stock_code:
                query = query.filter(AgentDecisionLog.stock_code == stock_code)

            return query.order_by(desc(AgentDecisionLog.decision_time)).limit(limit).all()

    # ========================================
    # 统计查询
    # ========================================

    def get_total_capital(self) -> float:
        """获取当前总资金"""
        return self.get_config('current_capital', 100000.0)

    def update_total_capital(self, new_capital: float):
        """更新总资金"""
        self.set_config('current_capital', new_capital, 'float', '当前总资金')

    def get_today_profit_loss(self, today: date = None) -> float:
        """获取今日盈亏"""
        if today is None:
            today = date.today()

        with self.get_session() as session:
            transactions = session.query(Transaction).filter(
                Transaction.trade_date == today,
                Transaction.trade_type == 'SELL'
            ).all()

            return sum(t.profit_loss or 0 for t in transactions)


# 全局数据库管理器实例
db_manager = DatabaseManager()


# 便捷函数
def get_db() -> DatabaseManager:
    """获取数据库管理器实例"""
    return db_manager


def get_db_connection():
    """获取数据库连接 (兼容性函数)"""
    return db_manager


# 为 Trader Agent 添加的便捷函数

def insert_transaction(transaction: Dict[str, Any]) -> Transaction:
    """便捷函数: 插入交易记录

    Args:
        transaction: 交易数据字典
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "action": "buy",  # buy/sell
                "price": 15.50,
                "quantity": 6400,
                "amount": 99200,
                "strategy": "龙头战法",
                "reason": "3连板龙头",
                "timestamp": "2025-10-21 09:35:00",
                ...
            }

    Returns:
        Transaction 对象
    """
    # 映射字段名
    trade_data = {
        "stock_code": transaction.get("stock_code"),
        "stock_name": transaction.get("stock_name"),
        "trade_type": transaction.get("action", "").upper(),  # buy->BUY, sell->SELL
        "trade_price": transaction.get("price"),
        "trade_quantity": transaction.get("quantity"),
        "trade_amount": transaction.get("amount"),
        "trade_fee": transaction.get("fee", 0),
        "profit_loss": transaction.get("profit", 0),
        "strategy_name": transaction.get("strategy", ""),
        "trade_reason": transaction.get("reason", ""),
        "trade_time": datetime.strptime(transaction["timestamp"], "%Y-%m-%d %H:%M:%S") if isinstance(transaction.get("timestamp"), str) else datetime.now(),
        "trade_date": date.today()
    }

    return db_manager.add_transaction(**trade_data)


def insert_candidate(candidate: Dict[str, Any]) -> Candidate:
    """便捷函数: 插入候选股票

    Args:
        candidate: 候选股票数据字典
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "strategy": "龙头战法",
                "score": 85,
                "reason": "3连板龙头",
                "status": "bought",  # pending/bought/rejected
                "recommended_date": "2025-10-21"
            }

    Returns:
        Candidate 对象
    """
    # ✅ 过滤非交易日：如果当前是周末，调整到下一个交易日
    from src.utils.trading_calendar import is_trading_day, get_next_trading_day
    from datetime import date

    current_date = date.today()
    current_time = datetime.now()
    recommend_date = current_date

    if not is_trading_day(current_date):
        recommend_date = get_next_trading_day(from_date=current_date)
        logger.info(f"📅 当前是非交易日，推荐日期已调整: {current_date} -> {recommend_date}")
        # 非交易日：设置推荐时间为下一个交易日的开盘时间（9:30）
        recommend_time = datetime.combine(recommend_date, datetime.min.time().replace(hour=9, minute=30))
    else:
        # ✅ 交易日：使用当前实际时间
        recommend_time = current_time
        logger.info(f"📅 当前是交易日，推荐时间: {recommend_time.strftime('%Y-%m-%d %H:%M:%S')}")

    candidate_data = {
        "stock_code": candidate.get("stock_code"),
        "stock_name": candidate.get("stock_name"),
        "strategy_name": candidate.get("strategy", ""),
        "final_score": candidate.get("score", 0),
        "recommend_reason": candidate.get("reason", ""),
        "recommend_track": candidate.get("status", "pending"),  # 使用 recommend_track 存储状态
        "recommend_time": recommend_time  # ✅ 使用调整后的交易日时间
    }

    return db_manager.add_candidate(**candidate_data)


def update_position(stock_code: str, updates: Dict[str, Any]):
    """便捷函数: 更新持仓

    Args:
        stock_code: 股票代码
        updates: 更新字段 {"quantity": 0, "status": "sold", ...}
    """
    # 查找持仓ID
    with db_manager.get_session() as session:
        position = session.query(Position).filter(
            Position.stock_code == stock_code,
            Position.status == 'holding'
        ).first()

        if position:
            for key, value in updates.items():
                setattr(position, key, value)
            session.flush()
        else:
            logger.warning(f"未找到持仓: {stock_code}")


def insert_position(position: Dict[str, Any]) -> Position:
    """便捷函数: 插入新持仓

    Args:
        position: 持仓数据字典
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "quantity": 6400,
                "buy_price": 15.50,
                "buy_date": "2025-10-21",
                ...
            }

    Returns:
        Position 对象
    """
    position_data = {
        "stock_code": position.get("stock_code"),
        "stock_name": position.get("stock_name"),
        "quantity": position.get("quantity"),
        "buy_price": position.get("buy_price"),
        "buy_date": datetime.strptime(position["buy_date"], "%Y-%m-%d").date() if isinstance(position.get("buy_date"), str) else date.today(),
        "current_price": position.get("buy_price"),  # 初始时当前价 = 买入价
        "profit_loss": 0,
        "profit_loss_ratio": 0,
        "status": "holding"
    }

    return db_manager.add_position(**position_data)
