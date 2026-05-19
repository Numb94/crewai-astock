#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock V2.0 - 数据库连接管理

作者: AI Architect
版本: v2.0.6
日期: 2025-10-22
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def get_database_url():
    """获取数据库 URL"""
    db_path = os.getenv('DATABASE_PATH', 'data/stock_trading.db')

    # 转换为绝对路径(相对于项目根目录)
    if not Path(db_path).is_absolute():
        # 获取项目根目录(connection.py的上上上级目录)
        project_root = Path(__file__).parent.parent.parent
        db_path = project_root / db_path

    # 解析为规范化的绝对路径
    db_path = Path(db_path).resolve()

    # 确保 data 目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return f'sqlite:///{db_path}'


# 创建全局数据库引擎
engine = create_engine(
    get_database_url(),
    echo=False,
    connect_args={'check_same_thread': False},  # SQLite 多线程支持
    pool_pre_ping=True,  # 自动检查连接有效性
    pool_recycle=3600,  # 1小时后回收连接
)

# 创建 Session 工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 线程安全的 Session
ScopedSession = scoped_session(SessionLocal)


def get_db():
    """
    获取数据库会话（推荐用于依赖注入）

    用法:
        db = get_db()
        try:
            # 使用 db 进行查询
            ...
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session():
    """
    直接获取数据库会话（简单用法）

    用法:
        session = get_session()
        try:
            result = session.query(Candidate).all()
        finally:
            session.close()

    Returns:
        Session: SQLAlchemy 会话对象
    """
    return SessionLocal()


def close_db_connection():
    """关闭数据库连接（清理资源）"""
    engine.dispose()


# 导出常用对象
__all__ = [
    'engine',
    'SessionLocal',
    'ScopedSession',
    'get_db',
    'get_session',
    'close_db_connection',
    'get_database_url'
]
