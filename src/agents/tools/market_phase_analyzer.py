#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
市场阶段分析工具

识别市场阶段（牛市/熊市/震荡市），为策略选择提供依据
"""

from crewai.tools import tool
from typing import Dict, Any
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@tool("识别市场阶段")
def identify_market_phase() -> str:
    """
    识别当前市场阶段（牛市/熊市/震荡市）
    
    基于上证指数的MA均线判断市场趋势
    
    Returns:
        市场阶段分析结果（自然语言描述）
    """
    from src.tools.zhitu_api import ZhituAPI
    
    try:
        zhitu = ZhituAPI()
        
        # 获取上证指数最近60天的日线数据
        # 🔴 修复：增加获取天数（90天 → 120天），确保有足够的交易日数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')

        # 获取上证指数历史数据
        index_data = zhitu.get_history_timeframe(
            stock_symbol='000001.SH',
            timeframe='d',
            adjust_type='n',
            start_time=start_date,
            end_time=end_date
        )

        # 🔴 调试日志
        logger.info(f"📊 获取上证指数数据: {len(index_data) if index_data else 0}条（请求{start_date}至{end_date}）")
        if index_data:
            logger.debug(f"  - 第一条: {index_data[0]}")
            logger.debug(f"  - 最后一条: {index_data[-1]}")

        # 🔴 修复：降低最小数据要求（60条 → 50条），提高容错性
        if not index_data or len(index_data) < 50:
            logger.warning(f"⚠️ 数据不足，只有{len(index_data) if index_data else 0}条，需要至少50条")
            return f"数据不足，无法判断市场阶段（获取到{len(index_data) if index_data else 0}条数据，需要至少50条）"

        # 如果数据在50-60条之间，给出警告但继续执行
        if len(index_data) < 60:
            logger.warning(f"⚠️ 数据略少（{len(index_data)}条），建议至少60条，但仍可继续分析")
        
        # 计算MA5, MA10, MA20, MA60
        ma5 = _calculate_ma(index_data, 5)
        ma10 = _calculate_ma(index_data, 10)
        ma20 = _calculate_ma(index_data, 20)
        ma60 = _calculate_ma(index_data, 60)
        
        # 获取最新价格
        current_price = float(index_data[-1].get('c', 0))
        
        # 判断市场阶段
        phase_result = _judge_market_phase(current_price, ma5, ma10, ma20, ma60)
        
        # 计算趋势持续天数
        duration = _calculate_trend_duration(index_data, phase_result['phase'])
        
        # 计算涨跌幅
        price_change_5d = ((current_price - float(index_data[-5].get('c', current_price))) / float(index_data[-5].get('c', current_price))) * 100
        price_change_20d = ((current_price - float(index_data[-20].get('c', current_price))) / float(index_data[-20].get('c', current_price))) * 100
        
        # 格式化输出
        return f"""
=== 市场阶段分析 ===

市场阶段: {phase_result['phase_cn']}
趋势方向: {phase_result['trend_cn']}
趋势强度: {phase_result['strength']:.0%}
持续天数: {duration}天

上证指数: {current_price:.2f}
MA5: {ma5:.2f}
MA10: {ma10:.2f}
MA20: {ma20:.2f}
MA60: {ma60:.2f}

近期表现:
- 5日涨跌: {price_change_5d:+.2f}%
- 20日涨跌: {price_change_20d:+.2f}%

策略建议: {phase_result['strategy_suggestion']}
"""
    
    except Exception as e:
        logger.error(f"识别市场阶段失败: {e}")
        return f"识别市场阶段失败: {str(e)}"


def _calculate_ma(data: list, period: int) -> float:
    """计算移动平均线"""
    if len(data) < period:
        return 0
    
    prices = [float(d.get('c', 0)) for d in data[-period:]]
    return sum(prices) / period


def _judge_market_phase(current_price: float, ma5: float, ma10: float, ma20: float, ma60: float) -> Dict[str, Any]:
    """
    判断市场阶段
    
    Returns:
        {
            "phase": "bull_market",  # bull_market/bear_market/sideways
            "phase_cn": "牛市",
            "trend": "upward",  # upward/downward/neutral
            "trend_cn": "上涨",
            "strength": 0.8,  # 0-1
            "strategy_suggestion": "..."
        }
    """
    # 多头排列：价格 > MA5 > MA10 > MA20 > MA60
    if current_price > ma5 > ma10 > ma20 > ma60:
        return {
            "phase": "bull_market",
            "phase_cn": "牛市（多头排列）",
            "trend": "upward",
            "trend_cn": "强势上涨",
            "strength": 0.9,
            "strategy_suggestion": "激进策略，龙头战法、题材轮动、异动跟踪"
        }
    
    # 空头排列：价格 < MA5 < MA10 < MA20 < MA60
    elif current_price < ma5 < ma10 < ma20 < ma60:
        return {
            "phase": "bear_market",
            "phase_cn": "熊市（空头排列）",
            "trend": "downward",
            "trend_cn": "弱势下跌",
            "strength": 0.9,
            "strategy_suggestion": "保守策略，观望等待或防守反击（超跌反弹）"
        }
    
    # 价格在MA20之上，但均线未完全多头排列
    elif current_price > ma20:
        return {
            "phase": "bull_market",
            "phase_cn": "牛市（震荡上行）",
            "trend": "upward",
            "trend_cn": "震荡上涨",
            "strength": 0.6,
            "strategy_suggestion": "稳健策略，低吸埋伏、高低切换"
        }
    
    # 价格在MA20之下，但均线未完全空头排列
    elif current_price < ma20:
        return {
            "phase": "bear_market",
            "phase_cn": "熊市（震荡下行）",
            "trend": "downward",
            "trend_cn": "震荡下跌",
            "strength": 0.6,
            "strategy_suggestion": "防守策略，观望等待，避免追高"
        }
    
    # 震荡市
    else:
        return {
            "phase": "sideways",
            "phase_cn": "震荡市",
            "trend": "neutral",
            "trend_cn": "横盘震荡",
            "strength": 0.5,
            "strategy_suggestion": "灵活策略，题材轮动、新闻驱动"
        }


def _calculate_trend_duration(data: list, phase: str) -> int:
    """计算趋势持续天数"""
    duration = 0
    
    for i in range(len(data) - 1, max(0, len(data) - 30), -1):
        current = float(data[i].get('c', 0))
        prev = float(data[i-1].get('c', 0)) if i > 0 else current
        
        if phase == "bull_market" and current >= prev:
            duration += 1
        elif phase == "bear_market" and current <= prev:
            duration += 1
        else:
            break
    
    return duration

