#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移：添加操作建议和推送去重字段

新增字段：
1. candidates表：
   - operation_suggestion: 操作建议
   - position_comparison: 持仓对比分析

2. positions表：
   - last_push_time: 上次推送时间
   - last_push_suggestion: 上次推送的建议
   - push_count_today: 今日推送次数

作者: AI Architect
日期: 2025-11-06
"""

from sqlalchemy import text
from src.database.db_manager import get_db
from loguru import logger


def upgrade():
    """添加新字段"""
    import sqlite3

    try:
        conn = sqlite3.connect('crewai_stock.db')
        cursor = conn.cursor()

        # 1. candidates表添加字段
        logger.info("正在为candidates表添加operation_suggestion字段...")
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN operation_suggestion TEXT")
            logger.success("✅ operation_suggestion字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.warning("⚠️ operation_suggestion字段已存在，跳过")
            else:
                raise

        logger.info("正在为candidates表添加position_comparison字段...")
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN position_comparison TEXT")
            logger.success("✅ position_comparison字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.warning("⚠️ position_comparison字段已存在，跳过")
            else:
                raise

        # 2. positions表添加字段
        logger.info("正在为positions表添加last_push_time字段...")
        try:
            cursor.execute("ALTER TABLE positions ADD COLUMN last_push_time DATETIME")
            logger.success("✅ last_push_time字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.warning("⚠️ last_push_time字段已存在，跳过")
            else:
                raise

        logger.info("正在为positions表添加last_push_suggestion字段...")
        try:
            cursor.execute("ALTER TABLE positions ADD COLUMN last_push_suggestion VARCHAR(50)")
            logger.success("✅ last_push_suggestion字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.warning("⚠️ last_push_suggestion字段已存在，跳过")
            else:
                raise

        logger.info("正在为positions表添加push_count_today字段...")
        try:
            cursor.execute("ALTER TABLE positions ADD COLUMN push_count_today INTEGER DEFAULT 0")
            logger.success("✅ push_count_today字段添加成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.warning("⚠️ push_count_today字段已存在，跳过")
            else:
                raise

        conn.commit()
        conn.close()
        logger.success("✅ 数据库迁移成功！")

    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}")
        raise


def downgrade():
    """删除新字段"""
    db = get_db()
    
    try:
        with db.get_session() as session:
            # 1. candidates表删除字段
            logger.info("正在删除candidates表的operation_suggestion字段...")
            session.execute(text("""
                ALTER TABLE candidates 
                DROP COLUMN operation_suggestion
            """))
            
            logger.info("正在删除candidates表的position_comparison字段...")
            session.execute(text("""
                ALTER TABLE candidates 
                DROP COLUMN position_comparison
            """))
            
            # 2. positions表删除字段
            logger.info("正在删除positions表的last_push_time字段...")
            session.execute(text("""
                ALTER TABLE positions 
                DROP COLUMN last_push_time
            """))
            
            logger.info("正在删除positions表的last_push_suggestion字段...")
            session.execute(text("""
                ALTER TABLE positions 
                DROP COLUMN last_push_suggestion
            """))
            
            logger.info("正在删除positions表的push_count_today字段...")
            session.execute(text("""
                ALTER TABLE positions 
                DROP COLUMN push_count_today
            """))
            
            session.commit()
            logger.success("✅ 数据库回滚成功！")
            
    except Exception as e:
        logger.error(f"❌ 数据库回滚失败: {e}")
        raise


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        logger.info("开始回滚数据库...")
        downgrade()
    else:
        logger.info("开始迁移数据库...")
        upgrade()

