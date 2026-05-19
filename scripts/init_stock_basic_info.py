#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化股票基础信息表 - 用于换手率计算

功能：
1. 创建 stock_basic_info 表
2. 批量获取所有股票的流通股本数据
3. 存储到数据库中供快速查询

作者: AI Architect
日期: 2025-11-05
"""

import sys
import sqlite3
import time
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.zhitu_api import ZhituAPI


def create_table(conn):
    """创建 stock_basic_info 表"""
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_basic_info (
            stock_code TEXT PRIMARY KEY,
            stock_name TEXT,
            float_shares REAL,
            total_shares REAL,
            list_date TEXT,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    logger.info("✅ stock_basic_info 表创建成功")


def fetch_and_save_basic_info(conn):
    """批量获取并保存股票基础信息"""
    zhitu = ZhituAPI()
    cursor = conn.cursor()
    
    # 1. 获取所有股票列表
    logger.info("📊 获取股票列表...")
    stock_list = zhitu.get_stock_list()
    
    if not stock_list:
        logger.error("❌ 获取股票列表失败")
        return
    
    logger.info(f"✅ 获取到 {len(stock_list)} 只股票")
    
    # 2. 批量获取基础信息
    success_count = 0
    fail_count = 0
    
    for i, stock in enumerate(stock_list, 1):
        stock_code = stock.get('stock_code', '')
        stock_name = stock.get('stock_name', '')
        
        if not stock_code:
            continue
        
        # 去掉后缀（如 .SZ, .SH）
        clean_code = stock_code.split('.')[0]
        
        try:
            # 获取基础信息
            basic_info = zhitu.get_stock_basic_info(stock_code)
            
            if basic_info:
                float_shares = basic_info.get('fv', 0)  # 流通股本
                total_shares = basic_info.get('tv', 0)  # 总股本
                list_date = basic_info.get('od', '')    # 上市日期
                
                # 插入或更新数据
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_basic_info 
                    (stock_code, stock_name, float_shares, total_shares, list_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (clean_code, stock_name, float_shares, total_shares, list_date))
                
                success_count += 1
                
                # 每100只提交一次
                if i % 100 == 0:
                    conn.commit()
                    logger.info(f"进度: {i}/{len(stock_list)} ({success_count}成功, {fail_count}失败)")
                    time.sleep(1)  # 避免限流
            else:
                fail_count += 1
                
        except Exception as e:
            fail_count += 1
            logger.warning(f"获取 {stock_code} 失败: {e}")
            continue
    
    # 最后提交
    conn.commit()
    
    logger.info(f"✅ 完成！成功: {success_count}只, 失败: {fail_count}只")


def main():
    """主函数"""
    # 数据库路径
    db_path = Path('data/stock_trading.db')
    
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True)
        logger.info(f"✅ 创建目录: {db_path.parent}")
    
    # 连接数据库
    conn = sqlite3.connect(str(db_path))
    logger.info(f"✅ 连接数据库: {db_path}")
    
    try:
        # 1. 创建表
        create_table(conn)
        
        # 2. 获取并保存数据
        fetch_and_save_basic_info(conn)
        
        # 3. 验证数据
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stock_basic_info")
        count = cursor.fetchone()[0]
        logger.info(f"✅ 数据库中共有 {count} 只股票的基础信息")
        
    finally:
        conn.close()
        logger.info("✅ 数据库连接已关闭")


if __name__ == '__main__':
    main()

