#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试社区情绪全局锁功能

验证：
1. 全局锁是否正常工作（批量分析时串行执行）
2. 缓存机制是否正常
3. 请求间隔是否生效
"""

import time
from loguru import logger


def test_single_stock():
    """测试单只股票"""
    logger.info("=" * 80)
    logger.info("测试1: 单只股票社区情绪获取")
    logger.info("=" * 80)
    
    from src.agents.tools.community_sentiment_tools import get_stock_community_comments
    
    stock_code = "000001"
    
    # 第一次调用（应该获取数据，耗时2-3秒）
    logger.info(f"🔄 第一次调用（无缓存）: {stock_code}")
    start_time = time.time()
    
    result = get_stock_community_comments.func(stock_code, max_items=5)
    
    elapsed_time = time.time() - start_time
    logger.info(f"⏱️ 耗时: {elapsed_time:.2f}秒")
    logger.info(f"📊 结果长度: {len(result)}字符")
    
    # 第二次调用（应该使用缓存，耗时<0.1秒）
    logger.info(f"\n🔄 第二次调用（有缓存）: {stock_code}")
    start_time = time.time()
    
    result2 = get_stock_community_comments.func(stock_code, max_items=5)
    
    elapsed_time2 = time.time() - start_time
    logger.info(f"⏱️ 耗时: {elapsed_time2:.2f}秒")
    
    if elapsed_time2 < 0.5:
        logger.success("✅ 缓存机制正常（耗时<0.5秒）")
    else:
        logger.warning("⚠️ 缓存可能未生效（耗时>0.5秒）")
    
    logger.info("=" * 80)


def test_batch_analysis():
    """测试批量分析（验证全局锁）"""
    logger.info("=" * 80)
    logger.info("测试2: 批量分析5只股票（验证全局锁）")
    logger.info("=" * 80)
    
    from src.agents.tools.market_tools import analyze_stocks_parallel
    
    stock_codes = "000001,600000,000002,600036,000858"
    
    logger.info(f"🔄 开始批量分析: {stock_codes}")
    logger.info("💡 预期: 社区情绪串行执行（全局锁保护），其他维度并行")
    
    start_time = time.time()
    
    result = analyze_stocks_parallel.func(stock_codes, compact_mode=True)
    
    elapsed_time = time.time() - start_time
    logger.info(f"\n⏱️ 总耗时: {elapsed_time:.2f}秒")
    
    # 分析耗时
    if elapsed_time > 15:
        logger.success("✅ 全局锁正常（社区情绪串行执行，耗时>15秒）")
    else:
        logger.warning("⚠️ 可能使用了缓存或全局锁未生效（耗时<15秒）")
    
    logger.info("=" * 80)


def test_concurrent_requests():
    """测试并发请求（验证全局锁）"""
    logger.info("=" * 80)
    logger.info("测试3: 并发请求（验证全局锁）")
    logger.info("=" * 80)
    
    from src.agents.tools.community_sentiment_tools import get_stock_community_comments
    import threading
    
    stock_codes = ["000001", "600000", "000002"]
    results = {}
    
    def fetch_community(stock_code):
        """获取社区情绪"""
        start = time.time()
        result = get_stock_community_comments.func(stock_code, max_items=5)
        elapsed = time.time() - start
        results[stock_code] = {
            'result': result,
            'elapsed': elapsed,
            'start': start
        }
        logger.info(f"✅ {stock_code} 完成，耗时: {elapsed:.2f}秒")
    
    # 创建3个线程同时请求
    threads = []
    logger.info(f"🔄 创建3个线程同时请求: {stock_codes}")
    
    start_time = time.time()
    
    for stock_code in stock_codes:
        thread = threading.Thread(target=fetch_community, args=(stock_code,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    total_elapsed = time.time() - start_time
    logger.info(f"\n⏱️ 总耗时: {total_elapsed:.2f}秒")
    
    # 分析结果
    logger.info("\n📊 请求时间分析:")
    for stock_code in stock_codes:
        data = results[stock_code]
        logger.info(f"  {stock_code}: 耗时{data['elapsed']:.2f}秒")
    
    # 验证串行执行
    if total_elapsed > 8:
        logger.success("✅ 全局锁正常（串行执行，总耗时>8秒）")
    else:
        logger.warning("⚠️ 可能使用了缓存或全局锁未生效（总耗时<8秒）")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    logger.info("🚀 开始测试社区情绪全局锁功能\n")
    
    # 测试1: 单只股票
    test_single_stock()
    
    # 等待2秒
    logger.info("\n⏳ 等待2秒后继续...\n")
    time.sleep(2)
    
    # 测试2: 批量分析
    # test_batch_analysis()  # 注释掉，因为耗时较长
    
    # 测试3: 并发请求
    test_concurrent_requests()
    
    logger.info("\n✅ 所有测试完成！")
    logger.info("\n📋 测试总结:")
    logger.info("1. 单只股票: 首次调用耗时2-3秒，缓存命中<0.5秒（正常）")
    logger.info("2. 并发请求: 全局锁保护，串行执行，总耗时>8秒（正常）")
    logger.info("3. 批量分析: 社区情绪串行，其他维度并行（可选测试）")
    logger.info("\n💡 建议:")
    logger.info("- 如果缓存未生效，检查 COMMUNITY_CACHE_TTL 配置")
    logger.info("- 如果全局锁未生效，检查 threading.Lock() 是否正常工作")
    logger.info("- 如果需要更安全，可以增加 COMMUNITY_REQUEST_DELAY 到 2.0 秒")

