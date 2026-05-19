#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
逐笔数据分析工具 - 用于多维分析

集成东方财富实时数据和智兔API历史数据
优先获取当天数据，无数据则回退到历史数据

作者: AI Architect
版本: v1.0.0
日期: 2025-11-14
"""

from crewai.tools import tool
from loguru import logger
from typing import Optional


@tool("智能获取逐笔数据分析")
def get_smart_tick_analysis(stock_code: str) -> str:
    """
    智能获取股票逐笔数据分析（优先当天实时数据，无数据则历史数据）
    
    用于多维分析时的资金流向分析，帮助判断主力行为和买卖力量对比
    
    Args:
        stock_code: 股票代码（如600000）
        
    Returns:
        逐笔数据分析结果，包括：
        - 数据来源（当天实时/历史数据）
        - 交易日期
        - 买卖力量对比（买入量、卖出量、买卖比）
        - 资金流向（净流入/净流出）
        - 主力行为判断
        - 大单交易分析
    """
    from src.tools.tick_data_fetcher import TickDataFetcher
    from src.tools.zhitu_api import ZhituAPI
    
    try:
        # 1. 尝试获取当天实时数据（东方财富）
        logger.info(f"尝试获取股票 {stock_code} 的当天逐笔数据...")
        # 启用代理（如果配置了GIANT_IP_API_URL）
        fetcher = TickDataFetcher(enable_proxy=True)
        today_result = fetcher.get_today_tick_data(stock_code)
        
        if today_result and today_result.get('data_count', 0) > 0:
            # 分析当天逐笔数据
            analysis = fetcher.analyze_tick_data(today_result['tick_data'])
            
            # 判断主力行为
            buy_sell_ratio = analysis['buy_sell_ratio']
            net_inflow = analysis['net_inflow']
            
            if buy_sell_ratio > 1.5:
                main_behavior = "主力买入"
                behavior_desc = "买入力量明显强于卖出，主力资金流入"
            elif buy_sell_ratio < 0.67:
                main_behavior = "主力卖出"
                behavior_desc = "卖出力量明显强于买入，主力资金流出"
            else:
                main_behavior = "多空平衡"
                behavior_desc = "买卖力量相对均衡，主力观望"
            
            # 大单分析（假设>100手为大单）
            big_trades = [t for t in today_result['tick_data'] if t['volume'] > 100]
            big_buy = sum(t['volume'] for t in big_trades if t.get('buy_sell_type') == 1)
            big_sell = sum(t['volume'] for t in big_trades if t.get('buy_sell_type') == 2)
            
            return f"""
=== {stock_code} 逐笔数据分析（当天实时数据）===

【数据来源】东方财富实时数据
【交易日期】{today_result['trade_date']}
【数据条数】{today_result['data_count']} 笔

【买卖力量对比】
- 买入量: {analysis['buy_volume']} 手
- 卖出量: {analysis['sell_volume']} 手
- 中性盘: {analysis['neutral_volume']} 手
- 买卖比: {buy_sell_ratio:.2f}

【资金流向】
- 买入金额: {analysis['buy_amount']:,.2f} 元
- 卖出金额: {analysis['sell_amount']:,.2f} 元
- 净流入: {net_inflow:,.2f} 元
- 平均价格: {analysis['avg_price']:.2f} 元

【大单交易】（>100手）
- 大单买入: {big_buy} 手
- 大单卖出: {big_sell} 手
- 大单数量: {len(big_trades)} 笔

【主力行为判断】
- 行为类型: {main_behavior}
- 行为描述: {behavior_desc}

【分析建议】
{_generate_tick_advice(buy_sell_ratio, net_inflow, analysis['total_volume'])}
"""
        
        # 2. 当天无数据，获取历史数据（智兔API）
        logger.info(f"当天无数据，尝试获取股票 {stock_code} 的历史逐笔数据...")
        zhitu = ZhituAPI()
        symbol = f"{stock_code}.SH" if stock_code.startswith(('6', '688')) else f"{stock_code}.SZ"
        historical_tick = zhitu.get_tick_by_tick(symbol)
        
        if not historical_tick or len(historical_tick) == 0:
            return f"❌ 未找到股票 {stock_code} 的逐笔数据（当天和历史数据均无）"
        
        # 分析历史逐笔数据
        buy_count = sum(1 for t in historical_tick if t.get('ts') == 1)
        sell_count = sum(1 for t in historical_tick if t.get('ts') == 2)
        buy_volume = sum(t.get('v', 0) for t in historical_tick if t.get('ts') == 1)
        sell_volume = sum(t.get('v', 0) for t in historical_tick if t.get('ts') == 2)
        
        buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else 0
        
        # 判断主力行为
        if buy_sell_ratio > 1.5:
            main_behavior = "主力买入"
        elif buy_sell_ratio < 0.67:
            main_behavior = "主力卖出"
        else:
            main_behavior = "多空平衡"
        
        return f"""
=== {stock_code} 逐笔数据分析（历史数据）===

【数据来源】智兔API历史数据
【数据条数】{len(historical_tick)} 笔
【注意】当前非交易时间或股票停牌，使用历史数据

【买卖力量对比】
- 买入笔数: {buy_count} 笔
- 卖出笔数: {sell_count} 笔
- 买入量: {buy_volume} 手
- 卖出量: {sell_volume} 手
- 买卖比: {buy_sell_ratio:.2f}

【主力行为判断】{main_behavior}
"""
        
    except Exception as e:
        logger.error(f"获取逐笔数据分析失败: {e}")
        return f"❌ 获取{stock_code}逐笔数据分析失败: {str(e)}"


@tool("获取当天逐笔数据分析")
def get_today_tick_analysis(stock_code: str) -> str:
    """
    获取股票当天逐笔数据分析（仅当天实时数据，无历史回退）

    专为持仓监控设计，只返回当天实时逐笔数据，用于判断卖点

    Args:
        stock_code: 股票代码（如600000）

    Returns:
        当天逐笔数据分析结果，包括：
        - 交易日期
        - 买卖力量对比（买入量、卖出量、买卖比）
        - 资金流向（净流入/净流出）
        - 主力行为判断
        - 大单交易分析
        - 卖点建议

    注意：
        - 只在交易时间内有数据
        - 非交易时间或停牌时返回无数据提示
    """
    from src.tools.tick_data_fetcher import TickDataFetcher

    try:
        # 获取当天实时数据（东方财富）
        logger.info(f"获取股票 {stock_code} 的当天逐笔数据...")
        # 启用代理（如果配置了GIANT_IP_API_URL）
        fetcher = TickDataFetcher(enable_proxy=True)
        today_result = fetcher.get_today_tick_data(stock_code)

        if not today_result or today_result.get('data_count', 0) == 0:
            return f"""
=== {stock_code} 逐笔数据分析 ===

❌ 当前无法获取逐笔数据

【可能原因】
- 非交易时间（交易时间：9:30-11:30, 13:00-15:00）
- 股票停牌
- 数据源暂时不可用

【建议】
- 主要依靠五档盘口数据和技术指标判断卖点
- 等待交易时间后再次获取逐笔数据
"""

        # 分析当天逐笔数据
        analysis = fetcher.analyze_tick_data(today_result['tick_data'])

        # 判断主力行为
        buy_sell_ratio = analysis['buy_sell_ratio']
        net_inflow = analysis['net_inflow']

        if buy_sell_ratio > 1.5:
            main_behavior = "主力买入"
            behavior_desc = "买入力量明显强于卖出，主力资金流入"
        elif buy_sell_ratio < 0.67:
            main_behavior = "主力卖出"
            behavior_desc = "卖出力量明显强于买入，主力资金流出"
        else:
            main_behavior = "多空平衡"
            behavior_desc = "买卖力量相对均衡，主力观望"

        # 大单分析（>100手为大单）
        big_trades = [t for t in today_result['tick_data'] if t['volume'] > 100]
        big_buy = sum(t['volume'] for t in big_trades if t.get('buy_sell_type') == 1)
        big_sell = sum(t['volume'] for t in big_trades if t.get('buy_sell_type') == 2)

        # 生成卖点建议
        sell_advice = _generate_sell_advice(buy_sell_ratio, net_inflow, big_buy, big_sell)

        return f"""
=== {stock_code} 逐笔数据分析（当天实时）===

【数据来源】东方财富实时数据
【交易日期】{today_result['trade_date']}
【数据条数】{today_result['data_count']} 笔

【买卖力量对比】
- 买入量: {analysis['buy_volume']} 手
- 卖出量: {analysis['sell_volume']} 手
- 中性盘: {analysis['neutral_volume']} 手
- 买卖比: {buy_sell_ratio:.2f}

【资金流向】
- 买入金额: {analysis['buy_amount']:,.2f} 元
- 卖出金额: {analysis['sell_amount']:,.2f} 元
- 净流入: {net_inflow:,.2f} 元
- 平均价格: {analysis['avg_price']:.2f} 元

【大单交易】（>100手）
- 大单买入: {big_buy} 手
- 大单卖出: {big_sell} 手
- 大单数量: {len(big_trades)} 笔

【主力行为判断】
- 行为类型: {main_behavior}
- 行为描述: {behavior_desc}

【卖点建议】
{sell_advice}
"""

    except Exception as e:
        logger.error(f"获取当天逐笔数据分析失败: {e}")
        return f"❌ 获取{stock_code}当天逐笔数据分析失败: {str(e)}"


def _generate_tick_advice(buy_sell_ratio: float, net_inflow: float, total_volume: int) -> str:
    """生成逐笔数据分析建议（用于选股）"""
    if buy_sell_ratio > 2.0 and net_inflow > 0:
        return "✅ 强烈买入信号：买入力量远超卖出，主力资金大幅流入，建议关注"
    elif buy_sell_ratio > 1.5 and net_inflow > 0:
        return "✅ 买入信号：买入力量明显强于卖出，主力资金流入，可以考虑"
    elif buy_sell_ratio < 0.5 and net_inflow < 0:
        return "⚠️ 强烈卖出信号：卖出力量远超买入，主力资金大幅流出，建议回避"
    elif buy_sell_ratio < 0.67 and net_inflow < 0:
        return "⚠️ 卖出信号：卖出力量明显强于买入，主力资金流出，谨慎对待"
    else:
        return "➡️ 中性信号：买卖力量相对均衡，主力观望，等待明确信号"


def _generate_sell_advice(buy_sell_ratio: float, net_inflow: float, big_buy: int, big_sell: int) -> str:
    """生成卖点建议（用于持仓监控）"""
    # 强烈卖出信号
    if buy_sell_ratio < 0.5 and net_inflow < -10000000:  # 净流出>1000万
        return "🔴 强烈建议卖出：卖出力量远超买入，资金大幅流出，主力出逃，建议立即卖出"
    elif buy_sell_ratio < 0.67 and big_sell > big_buy * 2:
        return "🔴 强烈建议卖出：大单持续流出，主力出货，建议立即卖出"

    # 建议卖出信号
    elif buy_sell_ratio < 0.8 and net_inflow < 0:
        return "🟡 建议卖出：卖出力量强于买入，资金流出，建议择机卖出"
    elif big_sell > big_buy * 1.5:
        return "🟡 建议卖出：大单卖出明显多于买入，主力减仓，建议择机卖出"

    # 建议持有信号
    elif buy_sell_ratio > 1.2 and net_inflow > 0:
        return "🟢 建议持有：买入力量强于卖出，资金流入，趋势良好，建议继续持有"
    elif big_buy > big_sell * 1.5:
        return "🟢 建议持有：大单买入明显多于卖出，主力吸筹，建议继续持有"

    # 观望信号
    else:
        return "⚪ 建议观望：买卖力量相对均衡，主力观望，继续观察盘口变化"

