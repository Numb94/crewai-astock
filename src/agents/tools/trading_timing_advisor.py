#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交易时机建议工具

根据当前时间和股票实时价格，给出最佳买入时机建议
"""

from crewai.tools import tool
from typing import Dict, Any
import logging
from datetime import datetime, time

logger = logging.getLogger(__name__)


@tool("推荐买入时机")
def recommend_buy_timing(stock_code: str, recommend_price: float) -> str:
    """
    推荐最佳买入时机
    
    Args:
        stock_code: 股票代码（如600000）
        recommend_price: 推荐价格
    
    Returns:
        买入时机建议（自然语言描述）
    """
    from src.tools.zhitu_api import ZhituAPI
    
    try:
        zhitu = ZhituAPI()
        current_time = datetime.now()
        
        # 获取实时价格
        realtime_data = zhitu.get_real_time_broker(stock_code)
        if not realtime_data:
            return "无法获取实时价格，建议谨慎买入"
        
        current_price = float(realtime_data.get('p', recommend_price))
        change_pct = float(realtime_data.get('pc', 0))
        
        # 判断买入时机
        timing_result = _judge_buy_timing(
            current_time=current_time,
            current_price=current_price,
            recommend_price=recommend_price,
            change_pct=change_pct
        )
        
        # 格式化输出
        return f"""
=== 买入时机建议 ===

股票代码: {stock_code}
推荐价格: {recommend_price:.2f}元
当前价格: {current_price:.2f}元
今日涨跌: {change_pct:+.2f}%

买入时机: {timing_result['timing_cn']}
紧急程度: {timing_result['urgency_cn']}
建议价格区间: {timing_result['price_range'][0]:.2f}-{timing_result['price_range'][1]:.2f}元

建议理由: {timing_result['reason']}
"""
    
    except Exception as e:
        logger.error(f"推荐买入时机失败: {e}")
        return f"推荐买入时机失败: {str(e)}"


def _judge_buy_timing(
    current_time: datetime,
    current_price: float,
    recommend_price: float,
    change_pct: float
) -> Dict[str, Any]:
    """
    判断买入时机
    
    Returns:
        {
            "timing": "tomorrow_open",  # tomorrow_open/today_now/wait_dip
            "timing_cn": "明日开盘买入",
            "urgency": "low",  # high/medium/low
            "urgency_cn": "低",
            "price_range": [10.20, 10.50],
            "reason": "..."
        }
    """
    hour = current_time.hour
    minute = current_time.minute
    
    # 计算价格偏差
    price_deviation = ((current_price - recommend_price) / recommend_price) * 100
    
    # 盘后推荐（15:00-次日9:30）
    if hour >= 15 or hour < 9:
        return {
            "timing": "tomorrow_open",
            "timing_cn": "明日开盘买入",
            "urgency": "low",
            "urgency_cn": "低",
            "price_range": [recommend_price * 0.98, recommend_price * 1.02],
            "reason": "盘后推荐，建议明日集合竞价（9:15-9:25）或开盘后观察，如有回调可低吸"
        }
    
    # 早盘推荐（9:30-11:30）
    elif 9 <= hour < 12:
        # 已经大涨（>5%）
        if change_pct >= 5:
            return {
                "timing": "wait_dip",
                "timing_cn": "等待回调买入",
                "urgency": "low",
                "urgency_cn": "低",
                "price_range": [current_price * 0.97, current_price * 0.99],
                "reason": f"早盘已涨{change_pct:.2f}%，不建议追高，等待回调至{current_price * 0.98:.2f}元附近再买入"
            }
        
        # 价格合理（-2% ~ +3%）
        elif -2 <= price_deviation <= 3:
            return {
                "timing": "today_now",
                "timing_cn": "立即买入",
                "urgency": "high",
                "urgency_cn": "高",
                "price_range": [current_price * 0.99, current_price * 1.01],
                "reason": f"早盘涨幅适中（{change_pct:+.2f}%），价格合理，建议立即买入"
            }
        
        # 价格偏高（>3%）
        else:
            return {
                "timing": "wait_dip",
                "timing_cn": "等待回调买入",
                "urgency": "low",
                "urgency_cn": "低",
                "price_range": [recommend_price * 0.98, recommend_price * 1.00],
                "reason": f"当前价格偏高（比推荐价高{price_deviation:.2f}%），建议等待回调"
            }
    
    # 午盘推荐（13:00-14:30）
    elif 13 <= hour < 15:
        # 已经大涨（>5%）
        if change_pct >= 5:
            return {
                "timing": "wait_dip",
                "timing_cn": "等待回调或明日买入",
                "urgency": "low",
                "urgency_cn": "低",
                "price_range": [current_price * 0.97, current_price * 0.99],
                "reason": f"午盘已涨{change_pct:.2f}%，不建议追高，可等待尾盘回调或明日买入"
            }
        
        # 价格合理
        elif -2 <= price_deviation <= 3:
            return {
                "timing": "today_now",
                "timing_cn": "立即买入或等待尾盘",
                "urgency": "medium",
                "urgency_cn": "中",
                "price_range": [current_price * 0.99, current_price * 1.01],
                "reason": f"午盘价格合理（{change_pct:+.2f}%），可立即买入或等待尾盘观察"
            }
        
        # 价格偏高
        else:
            return {
                "timing": "tomorrow_open",
                "timing_cn": "明日开盘买入",
                "urgency": "low",
                "urgency_cn": "低",
                "price_range": [recommend_price * 0.98, recommend_price * 1.02],
                "reason": f"当前价格偏高（比推荐价高{price_deviation:.2f}%），建议明日开盘买入"
            }
    
    # 其他时间（盘前）
    else:
        return {
            "timing": "today_open",
            "timing_cn": "今日开盘买入",
            "urgency": "medium",
            "urgency_cn": "中",
            "price_range": [recommend_price * 0.98, recommend_price * 1.02],
            "reason": "盘前推荐，建议开盘后观察，如价格合理可买入"
        }

