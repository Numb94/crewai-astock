#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复唯一索引：将单字段唯一索引改为复合唯一索引（session_id + 原字段）

需要修复的表：
1. system_config: config_key → (session_id, config_key)
2. market_sentiment: sentiment_date → (session_id, sentiment_date)
3. strategy_weights: (strategy_name, last_review_date) → (session_id, strategy_name, last_review_date)
"""

from sqlalchemy import create_engine, text, inspect
from loguru import logger
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

def fix_unique_indexes():
    """修复唯一索引"""
    
    # 数据库路径
    db_path = os.path.join(os.path.dirname(__file__), '../../../data/stock_trading.db')
    db_url = f'sqlite:///{db_path}'
    
    logger.info("=" * 60)
    logger.info("🚀 开始修复唯一索引...")
    logger.info("=" * 60)
    
    engine = create_engine(db_url, echo=False)
    
    with engine.connect() as conn:
        try:
            # ========================================
            # 1. 修复 system_config 表
            # ========================================
            logger.info("\n📋 修复表: system_config")
            
            # 删除旧的唯一索引
            logger.info("🔧 删除旧索引: ix_system_config_config_key")
            conn.execute(text("DROP INDEX IF EXISTS ix_system_config_config_key"))
            
            # 创建新的复合唯一索引
            logger.info("🔧 创建新索引: idx_system_config_unique (session_id, config_key)")
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_system_config_unique 
                ON system_config (session_id, config_key)
            """))
            
            logger.success("✅ system_config 索引修复完成")
            
            # ========================================
            # 2. 修复 market_sentiment 表
            # ========================================
            logger.info("\n📋 修复表: market_sentiment")
            
            # 检查是否有旧索引
            inspector = inspect(engine)
            indexes = inspector.get_indexes('market_sentiment')
            
            # 删除可能存在的旧唯一索引
            for idx in indexes:
                if idx.get('unique') and 'sentiment_date' in idx.get('column_names', []):
                    if 'session_id' not in idx.get('column_names', []):
                        logger.info(f"🔧 删除旧索引: {idx['name']}")
                        conn.execute(text(f"DROP INDEX IF EXISTS {idx['name']}"))
            
            # 创建新的复合唯一索引
            logger.info("🔧 创建新索引: idx_market_sentiment_unique (session_id, sentiment_date)")
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_market_sentiment_unique 
                ON market_sentiment (session_id, sentiment_date)
            """))
            
            logger.success("✅ market_sentiment 索引修复完成")
            
            # ========================================
            # 3. 修复 strategy_weights 表
            # ========================================
            logger.info("\n📋 修复表: strategy_weights")
            
            # 检查是否有旧索引
            indexes = inspector.get_indexes('strategy_weights')
            
            # 删除可能存在的旧唯一索引
            for idx in indexes:
                if idx.get('unique'):
                    cols = idx.get('column_names', [])
                    if 'strategy_name' in cols and 'session_id' not in cols:
                        logger.info(f"🔧 删除旧索引: {idx['name']}")
                        conn.execute(text(f"DROP INDEX IF EXISTS {idx['name']}"))
            
            # 创建新的复合唯一索引
            logger.info("🔧 创建新索引: idx_strategy_weights_unique (session_id, strategy_name, last_review_date)")
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_weights_unique 
                ON strategy_weights (session_id, strategy_name, last_review_date)
            """))
            
            logger.success("✅ strategy_weights 索引修复完成")
            
            # 提交事务
            conn.commit()
            
            logger.success("\n" + "=" * 60)
            logger.success("✅ 所有唯一索引修复完成！")
            logger.success("=" * 60)
            
            # 验证索引
            logger.info("\n📊 验证索引:")
            for table in ['system_config', 'market_sentiment', 'strategy_weights']:
                indexes = inspector.get_indexes(table)
                logger.info(f"\n表 {table} 的索引:")
                for idx in indexes:
                    logger.info(f"  - {idx['name']}: {idx['column_names']} (unique={idx.get('unique', False)})")
            
        except Exception as e:
            logger.error(f"❌ 修复索引失败: {e}")
            raise

if __name__ == '__main__':
    fix_unique_indexes()

