#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock V2.0 - 数据库初始化脚本

用法:
    python -m src.database.init_db              # 创建所有表
    python -m src.database.init_db --drop       # 删除并重建所有表
    python -m src.database.init_db --check      # 检查表结构

作者: AI Architect
版本: v2.0.5-db-complete
日期: 2025-10-21
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
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
    MeetingLog,
    StockConcepts,
    AgentContext,
    MarketNews,  # ✅ 新增：市场新闻表
)

# 加载环境变量
load_dotenv()


def get_database_url():
    """获取数据库 URL"""
    db_path = os.getenv('DATABASE_PATH', 'data/stock_trading.db')

    # 确保 data 目录存在
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    return f'sqlite:///{db_path}'


def init_database(drop_existing=False):
    """初始化数据库

    Args:
        drop_existing: 是否删除已存在的表
    """
    logger.info("=" * 60)
    logger.info("开始初始化数据库")
    logger.info("=" * 60)

    # 创建数据库连接
    database_url = get_database_url()
    logger.info(f"数据库路径: {database_url}")

    engine = create_engine(
        database_url,
        echo=False,  # 设置为 True 可查看 SQL 语句
        connect_args={'check_same_thread': False}  # SQLite 多线程支持
    )

    if drop_existing:
        logger.warning("⚠️ 删除所有已存在的表...")
        Base.metadata.drop_all(engine)
        logger.success("✅ 所有表已删除")

    # 创建所有表
    logger.info("创建数据库表...")
    Base.metadata.create_all(engine)
    logger.success("✅ 数据库表创建完成")

    # 验证表结构
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    logger.info(f"\n已创建 {len(tables)} 张表:")
    for i, table in enumerate(tables, 1):
        logger.info(f"  {i}. {table}")

    # 初始化默认配置
    logger.info("\n初始化系统配置...")
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 检查是否已有配置
        existing_config = session.query(SystemConfig).first()
        if not existing_config:
            # 初始化默认配置
            default_configs = [
                SystemConfig(
                    config_key='initial_capital',
                    config_value='100000',
                    config_type='float',
                    description='初始资金'
                ),
                SystemConfig(
                    config_key='current_capital',
                    config_value='100000',
                    config_type='float',
                    description='当前总资金'
                ),
                SystemConfig(
                    config_key='target_monthly_return',
                    config_value='50',
                    config_type='float',
                    description='月度收益目标(%)'
                ),
                SystemConfig(
                    config_key='system_version',
                    config_value='v2.0.5-db-complete',
                    config_type='string',
                    description='系统版本'
                ),
                SystemConfig(
                    config_key='last_init_time',
                    config_value=str(Path(__file__).stat().st_mtime),
                    config_type='string',
                    description='最后初始化时间'
                ),
            ]

            session.add_all(default_configs)
            session.commit()
            logger.success(f"✅ 已初始化 {len(default_configs)} 条系统配置")
        else:
            logger.info("ℹ️ 系统配置已存在，跳过初始化")

        # ✅ 策略完全自由化：不再预设8大策略
        # AI会根据市场情况自主创建策略，策略记录会在推荐时动态生成
        logger.info("ℹ️ 策略权重表已创建，等待AI自主创建策略记录")

    except Exception as e:
        logger.error(f"❌ 初始化配置失败: {e}")
        session.rollback()
    finally:
        session.close()

    logger.info("\n" + "=" * 60)
    logger.success("✅ 数据库初始化完成!")
    logger.info("=" * 60)


def check_database():
    """检查数据库表结构"""
    logger.info("=" * 60)
    logger.info("检查数据库表结构")
    logger.info("=" * 60)

    database_url = get_database_url()
    engine = create_engine(database_url, echo=False)
    inspector = inspect(engine)

    tables = inspector.get_table_names()

    if not tables:
        logger.warning("⚠️ 数据库中没有表，请先运行初始化")
        return

    logger.info(f"\n数据库中共有 {len(tables)} 张表:\n")

    expected_tables = [
        'candidates',
        'positions',
        'transactions',
        'reviews',
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

    for i, table in enumerate(expected_tables, 1):
        if table in tables:
            columns = inspector.get_columns(table)
            indexes = inspector.get_indexes(table)

            logger.success(f"{i}. ✅ {table}")
            logger.info(f"   - 字段数: {len(columns)}")
            logger.info(f"   - 索引数: {len(indexes)}")

            # 显示前5个字段
            logger.info(f"   - 主要字段:")
            for col in columns[:5]:
                logger.info(f"     • {col['name']}: {col['type']}")
            if len(columns) > 5:
                logger.info(f"     ... 还有 {len(columns) - 5} 个字段")
        else:
            logger.error(f"{i}. ❌ {table} (缺失)")

    logger.info("\n" + "=" * 60)
    logger.success("✅ 表结构检查完成")
    logger.info("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='CrewAI Stock V2.0 - 数据库初始化')
    parser.add_argument(
        '--drop',
        action='store_true',
        help='删除并重建所有表 (⚠️ 危险操作，会丢失所有数据)'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='检查数据库表结构'
    )

    args = parser.parse_args()

    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    try:
        if args.check:
            check_database()
        elif args.drop:
            # 二次确认
            logger.warning("\n⚠️ 警告: 此操作将删除所有数据库表和数据!")
            confirm = input("请输入 'YES' 确认删除: ")
            if confirm == 'YES':
                init_database(drop_existing=True)
            else:
                logger.info("操作已取消")
        else:
            init_database(drop_existing=False)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断操作")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"❌ 操作失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
