#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新闻监控调度器 - CrewAI A-Stock V2.0

描述: 根据交易时间动态调整监控频率
- 休盘期间：每1小时
- 开盘前：每5分钟
- 盘中：每5分钟
- 盘后：每30分钟

特性:
- 动态监控频率
- 交易日判断
- 紧急程度判断
- 开盘前摘要生成

作者: AI Architect
版本: v2.0.0
日期: 2025-11-07
"""

import logging
from datetime import datetime, time, date
from typing import Optional, List, Dict, Any

# 配置日志
logger = logging.getLogger(__name__)


class NewsMonitorScheduler:
    """
    新闻监控调度器
    
    根据交易时间动态调整监控频率
    """
    
    def __init__(self, session_id: str):
        """
        初始化
        
        Args:
            session_id: 用户会话ID
        """
        self.session_id = session_id
        self.last_monitor_time: Optional[datetime] = None
        self.last_summary_date: Optional[date] = None
    
    def should_monitor(self) -> bool:
        """
        判断是否需要监控
        
        Returns:
            True: 需要监控
            False: 不需要监控
        """
        now = datetime.now()
        current_time = now.time()
        
        # 判断是否交易日
        is_trading_day = self._is_trading_day(now.date())
        
        if not is_trading_day:
            # 非交易日：每1小时监控一次
            return self._should_monitor_by_interval(3600)
        
        # 交易日：根据时间段判断
        if time(9, 0) <= current_time < time(9, 30):
            # 开盘前：每5分钟
            return self._should_monitor_by_interval(300)
        elif time(9, 30) <= current_time < time(15, 0):
            # 盘中：每5分钟
            return self._should_monitor_by_interval(300)
        elif time(15, 0) <= current_time < time(23, 59):
            # 盘后：每30分钟
            return self._should_monitor_by_interval(1800)
        else:
            # 夜间：每1小时
            return self._should_monitor_by_interval(3600)
    
    def should_generate_summary(self) -> bool:
        """
        判断是否需要生成开盘前摘要
        
        Returns:
            True: 需要生成摘要
            False: 不需要生成摘要
        """
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # 判断是否交易日
        if not self._is_trading_day(current_date):
            return False
        
        # 判断是否在9:00-9:05之间（开盘前5分钟）
        if time(9, 0) <= current_time < time(9, 5):
            # 判断今天是否已经生成过摘要
            if self.last_summary_date != current_date:
                return True
        
        return False
    
    def _should_monitor_by_interval(self, interval: int) -> bool:
        """
        根据时间间隔判断是否需要监控
        
        Args:
            interval: 时间间隔（秒）
            
        Returns:
            True: 需要监控
            False: 不需要监控
        """
        if self.last_monitor_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_monitor_time).total_seconds()
        return elapsed >= interval
    
    def _is_trading_day(self, check_date: date) -> bool:
        """
        判断是否交易日
        
        Args:
            check_date: 检查日期
            
        Returns:
            True: 交易日
            False: 非交易日
        
        TODO: 接入交易日历API，准确判断节假日
        """
        # 简化版：周一到周五
        return check_date.weekday() < 5
    
    def update_monitor_time(self):
        """更新最后监控时间"""
        self.last_monitor_time = datetime.now()
        # logger.debug(f"更新监控时间: {self.last_monitor_time}")  # 🔴 注释掉DEBUG日志

    def update_summary_date(self):
        """更新最后摘要日期"""
        self.last_summary_date = datetime.now().date()
        # logger.debug(f"更新摘要日期: {self.last_summary_date}")  # 🔴 注释掉DEBUG日志
    
    def get_monitor_interval(self) -> int:
        """
        获取当前监控间隔（秒）
        
        Returns:
            监控间隔（秒）
        """
        now = datetime.now()
        current_time = now.time()
        
        # 判断是否交易日
        is_trading_day = self._is_trading_day(now.date())
        
        if not is_trading_day:
            return 3600  # 非交易日：1小时
        
        # 交易日：根据时间段判断
        if time(9, 0) <= current_time < time(9, 30):
            return 300  # 开盘前：5分钟
        elif time(9, 30) <= current_time < time(15, 0):
            return 300  # 盘中：5分钟
        elif time(15, 0) <= current_time < time(23, 59):
            return 1800  # 盘后：30分钟
        else:
            return 3600  # 夜间：1小时


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # 创建调度器
    scheduler = NewsMonitorScheduler(session_id="test_session")
    
    # 测试监控判断
    print(f"是否需要监控: {scheduler.should_monitor()}")
    print(f"是否需要生成摘要: {scheduler.should_generate_summary()}")
    print(f"当前监控间隔: {scheduler.get_monitor_interval()}秒")
    
    # 更新监控时间
    scheduler.update_monitor_time()
    
    # 再次测试
    print(f"更新后是否需要监控: {scheduler.should_monitor()}")

