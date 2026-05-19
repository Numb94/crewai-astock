#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
社区情绪分析示例

演示如何使用社区评论工具分析股票的散户情绪
"""

import asyncio
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


def example1_get_all_comments():
    """示例1: 获取所有平台评论"""
    logger.info("=" * 80)
    logger.info("示例1: 获取所有平台评论（雪球+东财+淘股吧）")
    logger.info("=" * 80)
    
    from src.tools.stock_mcp_community import get_community_client
    
    client = get_community_client()
    
    # 获取平安银行的社区评论
    stock_code = "000001"
    logger.info(f"正在获取 {stock_code} 的社区评论...")
    
    comments = asyncio.run(client.get_all_platforms_comments(
        symbol=stock_code,
        max_items=10  # 每个平台最多10条
    ))
    
    logger.info(f"\n{comments}\n")
    logger.info("=" * 80)


def example2_analyze_sentiment():
    """示例2: 使用Agent工具分析情绪"""
    logger.info("=" * 80)
    logger.info("示例2: 使用Agent工具分析情绪")
    logger.info("=" * 80)
    
    from src.agents.tools.community_sentiment_tools import get_stock_community_comments
    
    stock_code = "000001"
    logger.info(f"正在分析 {stock_code} 的社区情绪...")
    
    # 使用Agent工具（包含格式化输出和使用建议）
    result = get_stock_community_comments.func(stock_code, max_items=10)
    
    logger.info(f"\n{result}\n")
    logger.info("=" * 80)


def example3_compare_platforms():
    """示例3: 对比三个平台的评论"""
    logger.info("=" * 80)
    logger.info("示例3: 对比三个平台的评论")
    logger.info("=" * 80)
    
    from src.agents.tools.community_sentiment_tools import (
        get_xueqiu_comments,
        get_eastmoney_comments,
        get_taoguba_comments
    )
    
    stock_code = "000001"
    
    # 雪球评论
    logger.info(f"\n【雪球评论】")
    xq = get_xueqiu_comments.func(stock_code, max_items=5)
    logger.info(xq[:500] + "...\n")
    
    # 东财股吧评论
    logger.info(f"\n【东财股吧评论】")
    em = get_eastmoney_comments.func(stock_code, max_items=5)
    logger.info(em[:500] + "...\n")
    
    # 淘股吧评论
    logger.info(f"\n【淘股吧评论】")
    tgb = get_taoguba_comments.func(stock_code, max_items=5)
    logger.info(tgb[:500] + "...\n")
    
    logger.info("=" * 80)


def example4_batch_analysis():
    """示例4: 批量分析多只股票"""
    logger.info("=" * 80)
    logger.info("示例4: 批量分析多只股票")
    logger.info("=" * 80)
    
    from src.tools.stock_mcp_community import get_community_client
    
    client = get_community_client()
    
    # 分析多只股票
    stocks = ["000001", "000002", "600519"]
    
    for stock_code in stocks:
        logger.info(f"\n正在分析 {stock_code}...")
        
        comments = asyncio.run(client.get_all_platforms_comments(
            symbol=stock_code,
            max_items=5
        ))
        
        # 简单统计
        comment_length = len(comments)
        logger.info(f"  评论数据长度: {comment_length} 字符")
        
        # 可以在这里添加更多分析逻辑
        # 例如：情绪分析、关键词提取等
    
    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    # 运行示例
    logger.info("🚀 社区情绪分析示例\n")
    
    # 示例1: 获取所有平台评论
    example1_get_all_comments()
    
    # 示例2: 使用Agent工具分析情绪
    example2_analyze_sentiment()
    
    # 示例3: 对比三个平台的评论
    example3_compare_platforms()
    
    # 示例4: 批量分析多只股票
    example4_batch_analysis()
    
    logger.info("\n✅ 所有示例运行完成！")

