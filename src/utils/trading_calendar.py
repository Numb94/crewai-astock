#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交易日历工具模块 - CrewAI Stock V2.0

提供交易日判断、交易日计算等功能

作者: AI Architect
版本: v1.0.0
日期: 2025-11-17
"""

from datetime import date, timedelta
from typing import Optional
from loguru import logger


def is_trading_day(check_date: date) -> bool:
    """
    判断是否交易日
    
    Args:
        check_date: 检查日期
        
    Returns:
        True: 交易日
        False: 非交易日
        
    Note:
        简化版：周一到周五是交易日
        TODO: 接入交易日历API，准确判断节假日
    """
    # 简化版：周一到周五（0-4）是交易日
    return check_date.weekday() < 5


def get_last_trading_day(days_back: int = 1, from_date: Optional[date] = None) -> date:
    """
    获取最近的交易日（向前回溯）
    
    Args:
        days_back: 回溯天数（默认1天，即昨天）
        from_date: 起始日期（默认今天）
        
    Returns:
        最近的交易日
        
    Example:
        >>> get_last_trading_day()  # 获取昨天（如果是交易日）
        >>> get_last_trading_day(days_back=1, from_date=date(2025, 11, 17))  # 获取11月15日（周五）
    """
    start_date = from_date or date.today()
    current_date = start_date - timedelta(days=days_back)
    
    # 最多回溯7天
    max_attempts = 7
    attempts = 0
    
    while attempts < max_attempts:
        if is_trading_day(current_date):
            return current_date
        current_date -= timedelta(days=1)
        attempts += 1
    
    # 如果7天内都没有交易日，返回回溯后的日期（兜底）
    logger.warning(f"⚠️ 未找到交易日（回溯{max_attempts}天），返回兜底日期: {current_date}")
    return current_date


def get_next_trading_day(from_date: Optional[date] = None) -> date:
    """
    获取下一个交易日（向后查找）
    
    Args:
        from_date: 起始日期（默认今天）
        
    Returns:
        下一个交易日
        
    Example:
        >>> get_next_trading_day(date(2025, 11, 16))  # 周六 -> 返回11月18日（周一）
    """
    start_date = from_date or date.today()
    current_date = start_date + timedelta(days=1)
    
    # 最多向后查找7天
    max_attempts = 7
    attempts = 0
    
    while attempts < max_attempts:
        if is_trading_day(current_date):
            return current_date
        current_date += timedelta(days=1)
        attempts += 1
    
    # 如果7天内都没有交易日，返回查找后的日期（兜底）
    logger.warning(f"⚠️ 未找到交易日（向后查找{max_attempts}天），返回兜底日期: {current_date}")
    return current_date


def adjust_to_trading_day(check_date: date, direction: str = 'backward') -> date:
    """
    调整日期到最近的交易日
    
    Args:
        check_date: 检查日期
        direction: 调整方向
            - 'backward': 向前调整（默认，如周六调整到周五）
            - 'forward': 向后调整（如周六调整到周一）
            
    Returns:
        调整后的交易日
        
    Example:
        >>> adjust_to_trading_day(date(2025, 11, 16))  # 周六 -> 11月15日（周五）
        >>> adjust_to_trading_day(date(2025, 11, 16), 'forward')  # 周六 -> 11月18日（周一）
    """
    if is_trading_day(check_date):
        return check_date
    
    if direction == 'backward':
        return get_last_trading_day(days_back=1, from_date=check_date)
    elif direction == 'forward':
        return get_next_trading_day(from_date=check_date)
    else:
        logger.warning(f"⚠️ 未知的调整方向: {direction}，使用默认向前调整")
        return get_last_trading_day(days_back=1, from_date=check_date)


if __name__ == '__main__':
    # 测试代码
    from datetime import date
    
    print("=== 交易日判断测试 ===")
    test_dates = [
        date(2025, 11, 15),  # 周五
        date(2025, 11, 16),  # 周六
        date(2025, 11, 17),  # 周日
        date(2025, 11, 18),  # 周一
    ]
    
    for d in test_dates:
        weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][d.weekday()]
        is_trading = is_trading_day(d)
        print(f"{d} ({weekday}): {'✅ 交易日' if is_trading else '❌ 非交易日'}")
    
    print("\n=== 交易日调整测试 ===")
    test_date = date(2025, 11, 16)  # 周六
    print(f"原始日期: {test_date} (周六)")
    print(f"向前调整: {adjust_to_trading_day(test_date, 'backward')} (周五)")
    print(f"向后调整: {adjust_to_trading_day(test_date, 'forward')} (周一)")

