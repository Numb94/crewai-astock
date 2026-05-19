#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移：为Position表添加移动止盈字段

新增字段：
- today_open_price: 可卖日期当天的开盘价
- today_highest_price: 可卖日期当天的最高价
- today_highest_time: 最高价出现时间
- trailing_stop_triggered: 移动止盈是否已触发
"""
import os
import sys
from sqlalchemy import text
from loguru import logger

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database.db_manager import DatabaseManager

def add_trailing_stop_fields():
    """添加移动止盈相关字段"""
    logger.info("开始添加移动止盈字段...")

    db = DatabaseManager()

    try:
        with db.get_session() as session:
            # 检查字段是否已存在
            result = session.execute(text("PRAGMA table_info(positions)"))
            columns = [row[1] for row in result.fetchall()]
            
            fields_to_add = [
                ("today_open_price", "DECIMAL(10, 2)"),
                ("today_highest_price", "DECIMAL(10, 2)"),
                ("today_highest_time", "DATETIME"),
                ("trailing_stop_triggered", "BOOLEAN DEFAULT 0")
            ]
            
            for field_name, field_type in fields_to_add:
                if field_name not in columns:
                    logger.info(f"添加字段: {field_name} {field_type}")
                    session.execute(text(f"ALTER TABLE positions ADD COLUMN {field_name} {field_type}"))
                    session.commit()
                else:
                    logger.info(f"字段已存在: {field_name}")
            
            logger.success("✅ 移动止盈字段添加完成")
            
    except Exception as e:
        logger.error(f"❌ 添加字段失败: {e}")
        raise

if __name__ == "__main__":
    add_trailing_stop_fields()

