#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock V2.0 - Database Module

Unified exports for database-related content
"""

# Import all models
from .models import (
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
    MeetingLog,
    StockConcepts,
    AgentContext,    # ✅ Agent上下文表
    MarketNews,      # ✅ 市场新闻表
)

# Import database connection
from .connection import (
    engine,
    SessionLocal,
    ScopedSession,
    get_db,
    get_session,
    close_db_connection,
    get_database_url,
)

# Export all content
__all__ = [
    # ORM Base
    'Base',

    # All model classes
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
    'AgentContext',    # ✅ Agent上下文表
    'MarketNews',    # ✅ 市场新闻表

    # Database connection
    'engine',
    'SessionLocal',
    'ScopedSession',
    'get_db',
    'get_session',
    'close_db_connection',
    'get_database_url',
]
