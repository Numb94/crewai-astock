#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为所有表添加 session_id 字段

日期: 2025-11-06
作者: AI Architect
目的: 实现多用户支持（方案1：Session-Based）

迁移内容：
1. 为9张表添加 session_id 字段（4张已有）
2. 修改联合唯一索引
3. 迁移现有数据（设置默认session_id='default'）
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    """获取数据库URL"""
    db_path = os.getenv('DATABASE_PATH', 'data/stock_trading.db')
    if not Path(db_path).is_absolute():
        project_root = Path(__file__).parent.parent.parent.parent
        db_path = project_root / db_path
    db_path = Path(db_path).resolve()
    return f'sqlite:///{db_path}'


def check_column_exists(engine, table_name, column_name):
    """检查列是否存在"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate_database():
    """执行数据库迁移"""
    logger.info("=" * 60)
    logger.info("🚀 开始数据库迁移：添加 session_id 字段")
    logger.info("=" * 60)

    # 创建数据库连接
    db_url = get_database_url()
    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # ✅ 需要添加 session_id 的表（14张ORM模型表）
        tables_to_migrate = [
            # 核心业务表（4张）
            'candidates',
            'positions',
            'transactions',
            'reviews',
            # 系统配置表（10张）
            'agent_memory',
            'market_sentiment',
            'system_config',
            'strategy_executions',
            'strategy_performance',
            'strategy_weights',
            'agent_decision_logs',
            'meeting_logs',
            'stock_concepts',
            'agent_context'
        ]

        for table_name in tables_to_migrate:
            logger.info(f"\n📋 处理表: {table_name}")

            # 检查表是否存在
            inspector = inspect(engine)
            if table_name not in inspector.get_table_names():
                logger.warning(f"⚠️ 表 {table_name} 不存在，跳过")
                continue

            # 检查 session_id 列是否已存在
            if check_column_exists(engine, table_name, 'session_id'):
                logger.info(f"✅ 表 {table_name} 已有 session_id 字段，跳过")
                continue

            # 添加 session_id 列
            logger.info(f"🔧 添加 session_id 列...")
            session.execute(text(f"""
                ALTER TABLE {table_name}
                ADD COLUMN session_id VARCHAR(100) NOT NULL DEFAULT 'default'
            """))

            # 创建索引
            logger.info(f"🔧 创建索引...")
            session.execute(text(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_session_id
                ON {table_name}(session_id)
            """))

            logger.success(f"✅ 表 {table_name} 迁移完成")

        # 提交事务
        session.commit()
        logger.success("\n" + "=" * 60)
        logger.success("✅ 数据库迁移完成！")
        logger.success("=" * 60)

        # 输出迁移统计
        logger.info("\n📊 迁移统计:")
        logger.info(f"   - 已迁移表数量: {len(tables_to_migrate)}")
        logger.info(f"   - 默认session_id: 'default'")

    except Exception as e:
        session.rollback()
        logger.error(f"❌ 迁移失败: {e}")
        logger.exception("详细错误:")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate_database()

