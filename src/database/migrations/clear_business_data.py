#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清空业务数据，保留配置数据

清空的表（业务数据）：
1. candidates - 推荐候选股票
2. positions - 持仓记录
3. transactions - 交易记录
4. reviews - 复盘记录
5. agent_memory - Agent记忆
6. agent_decision_logs - Agent决策日志
7. meeting_logs - 会议日志
8. strategy_executions - 策略执行记录
9. strategy_performance - 策略绩效记录

保留的表（配置数据）：
1. system_config - 系统配置（账户资金等）
2. market_sentiment - 市场情绪（可选）
3. strategy_weights - 策略权重配置
"""

from sqlalchemy import create_engine, text
from loguru import logger
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

def clear_business_data():
    """清空业务数据，保留配置数据"""
    
    # 数据库路径
    db_path = os.path.join(os.path.dirname(__file__), '../../../data/stock_trading.db')
    db_url = f'sqlite:///{db_path}'
    
    logger.info("=" * 60)
    logger.info("🗑️  开始清空业务数据...")
    logger.info("=" * 60)
    
    engine = create_engine(db_url, echo=False)
    
    with engine.connect() as conn:
        try:
            # 需要清空的表（业务数据）
            tables_to_clear = [
                'candidates',
                'positions',
                'transactions',
                'strategy_executions',
                'market_sentiment'
            ]

            # 需要清空的表（未使用的预留表）
            tables_to_clear_unused = [
                'reviews',
                'agent_memory',
                'agent_decision_logs',
                'meeting_logs',
                'strategy_performance'
            ]

            # 需要清空的表（策略权重 - 完全自由化）
            tables_to_clear_strategy = [
                'strategy_weights'
            ]

            # 合并所有需要清空的表
            all_tables_to_clear = tables_to_clear + tables_to_clear_unused + tables_to_clear_strategy
            
            # 统计清空前的数据量
            logger.info("\n📊 清空前数据统计:")
            total_records = 0
            for table in all_tables_to_clear:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                total_records += count
                if count > 0:
                    logger.info(f"  - {table}: {count} 条记录")
            
            logger.info(f"\n总计: {total_records} 条记录")
            
            if total_records == 0:
                logger.info("\n✅ 数据库已经是空的，无需清空")
                return
            
            # 清空数据
            logger.info("\n🗑️  开始清空数据...")
            cleared_count = 0

            for table in all_tables_to_clear:
                logger.info(f"  清空表: {table}")
                conn.execute(text(f"DELETE FROM {table}"))
                cleared_count += 1

            # 重置自增ID（SQLite特有）
            logger.info("\n🔄 重置自增ID...")
            conn.execute(text("DELETE FROM sqlite_sequence WHERE name IN ({})".format(
                ','.join([f"'{t}'" for t in all_tables_to_clear])
            )))
            
            # 提交事务
            conn.commit()
            
            logger.success("\n" + "=" * 60)
            logger.success(f"✅ 成功清空 {cleared_count} 张表的数据！")
            logger.success("=" * 60)
            
            # 验证清空结果
            logger.info("\n📊 清空后数据统计:")
            for table in all_tables_to_clear:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                logger.info(f"  - {table}: {count} 条记录")

            # 显示保留的表
            logger.info("\n✅ 保留的配置表:")
            preserved_tables = ['system_config', 'stock_basic_info', 'stock_concepts']
            for table in preserved_tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                logger.info(f"  - {table}: {count} 条记录")
            
        except Exception as e:
            logger.error(f"❌ 清空数据失败: {e}")
            raise

if __name__ == '__main__':
    # 二次确认
    print("\n" + "=" * 60)
    print("⚠️  警告：此操作将清空以下数据表：")
    print("\n【业务数据表】")
    print("  - candidates (推荐候选)")
    print("  - positions (持仓记录)")
    print("  - transactions (交易记录)")
    print("  - strategy_executions (策略执行)")
    print("  - market_sentiment (市场情绪)")
    print("\n【未使用的预留表】")
    print("  - reviews (复盘记录)")
    print("  - agent_memory (Agent记忆)")
    print("  - agent_decision_logs (决策日志)")
    print("  - meeting_logs (会议日志)")
    print("  - strategy_performance (策略绩效)")
    print("\n【策略权重表 - 完全自由化】")
    print("  - strategy_weights (清空8大预设策略，让AI自主创建)")
    print("\n✅ 保留的配置表：")
    print("  - system_config (系统配置)")
    print("  - stock_basic_info (5161只股票基础信息)")
    print("  - stock_concepts (64445条概念数据)")
    print("=" * 60)

    confirm = input("\n确认清空业务数据？(yes/no): ")
    if confirm.lower() == 'yes':
        clear_business_data()
    else:
        print("❌ 操作已取消")

