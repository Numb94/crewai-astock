#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
涨停形态匹配回测工具

功能：
1. 回测涨停形态匹配的胜率和收益
2. 统计相似股票在后续N天的表现
3. 生成回测报告

作者: AI Architect
日期: 2025-11-11
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from crewai.tools import tool

logger = logging.getLogger(__name__)


@tool("回测涨停形态匹配策略")
def backtest_limit_up_pattern_matching(
    backtest_days: int = 20,
    holding_days: int = 1,
    similarity_threshold: float = 50.0,
    limit_up_stocks_count: int = 5,
    stocks_per_limit_up: int = 1
) -> str:
    """
    回测涨停形态匹配策略的胜率和收益（T+1模式）

    回测逻辑：
    1. 遍历最近N个交易日
    2. 每天选择TOP N只封板强度最高的涨停股票作为参考
    3. 对每只涨停股票，找出最相似的M只股票
    4. 汇总所有相似股票，去重后买入
    5. T+1卖出（买入后第二天就卖）
    6. 统计胜率、累计收益、月度收益

    Args:
        backtest_days: 回测天数（默认20天，约1个月）
        holding_days: 持仓天数（默认1天，T+1模式）
        similarity_threshold: 相似度阈值（默认50%，提高质量）
        limit_up_stocks_count: 每天分析的涨停股票数量（默认5只）
        stocks_per_limit_up: 每只涨停股找出的相似股票数量（默认1只）

    Returns:
        回测报告（包含胜率、收益率、交易明细）
    """
    from src.tools.zhitu_api import ZhituAPI
    from src.utils.db_cache import get_db_cache
    from src.agents.tools.limit_up_pattern_matcher import (
        _extract_limit_up_features,
        _calculate_similarity
    )

    zhitu = ZhituAPI()
    db_cache = get_db_cache()
    
    logger.info(f"🔍 开始回测涨停形态匹配策略")
    logger.info(f"   回测天数: {backtest_days}天")
    logger.info(f"   持仓天数: {holding_days}天")
    logger.info(f"   相似度阈值: {similarity_threshold}%")
    logger.info(f"   分析模式: 每天分析{limit_up_stocks_count}只涨停股，每只找{stocks_per_limit_up}只相似股")
    
    # 1. 获取回测日期范围（生成最近N个自然日，后续会过滤出有涨停数据的交易日）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=backtest_days * 3)  # 多取一些天数，确保有足够的交易日

    # 2. 生成日期列表（格式：YYYY-MM-DD）
    trade_dates = []
    current_date = start_date
    while current_date <= end_date:
        # 排除周末
        if current_date.weekday() < 5:  # 0-4是周一到周五
            trade_dates.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)

    logger.info(f"✅ 生成{len(trade_dates)}个潜在交易日")
    
    # 3. 回测统计
    total_trades = 0  # 总交易次数
    win_trades = 0  # 盈利交易次数
    total_return = 0.0  # 总收益率
    max_return = -999.0  # 最大收益率
    max_loss = 0.0  # 最大亏损率
    trade_details = []  # 交易明细
    
    # 4. 遍历每个交易日（只处理前backtest_days个有效交易日）
    valid_trade_count = 0
    for i, trade_date in enumerate(trade_dates, 1):
        # 检查是否已经处理了足够的交易日
        if valid_trade_count >= backtest_days:
            break

        # 确保有足够的后续日期用于持仓
        remaining_dates = len(trade_dates) - i
        if remaining_dates < holding_days:
            break

        logger.info(f"📅 [{valid_trade_count+1}/{backtest_days}] 回测日期: {trade_date}")
        
        try:
            # 4.1 获取当日涨停股票
            try:
                limit_up_stocks = zhitu.get_limit_up_pool(trade_date)
            except Exception as e:
                logger.debug(f"   ⚠️ 获取涨停数据失败: {e}")
                continue

            if not limit_up_stocks or len(limit_up_stocks) == 0:
                logger.debug(f"   ⚠️ 当日无涨停股票，跳过")
                continue

            logger.info(f"   ✅ 获取到{len(limit_up_stocks)}只涨停股票")
            
            # 4.2 选择TOP N只封板强度最高的涨停股票作为参考
            # 按封板资金排序，选择封板最强的股票
            sorted_stocks = sorted(
                limit_up_stocks,
                key=lambda x: x.get('limit_up_funds', x.get('zj', 0)) or 0,
                reverse=True
            )

            # 选择TOP N只强封板股票
            ref_stocks = sorted_stocks[:limit_up_stocks_count]

            # 过滤ST股票
            ref_stocks = [
                s for s in ref_stocks
                if not (s.get('stock_name', s.get('mc', '')) and
                       ('ST' in s.get('stock_name', s.get('mc', '')) or
                        'st' in s.get('stock_name', s.get('mc', ''))))
            ]

            if len(ref_stocks) == 0:
                logger.info(f"   ⚠️ 无有效参考股票（可能都是ST股），跳过")
                continue

            logger.info(f"   📌 参考股票: {len(ref_stocks)}只强封板股票")

            # 4.3 对每只涨停股票，找出相似股票
            all_similar_stocks = []  # 汇总所有相似股票

            for ref_stock in ref_stocks:
                ref_code = ref_stock.get('stock_code', ref_stock.get('dm', ''))
                ref_name = ref_stock.get('stock_name', ref_stock.get('mc', ''))

                if not ref_code:
                    continue

                logger.debug(f"      分析涨停股: {ref_name}({ref_code})")

                # 提取涨停股票特征
                limit_up_features = _extract_limit_up_features(ref_code, zhitu, db_cache)
                if not limit_up_features:
                    logger.debug(f"      ⚠️ 无法提取特征，跳过")
                    continue
            
                # 4.4 获取候选股票池（同题材）
                limit_up_concepts = set(limit_up_features.get('concepts', []))
                candidate_stocks = []

                if limit_up_concepts:
                    all_stock_concepts = db_cache.get_all_stock_concepts()
                    for stock_code, concepts in all_stock_concepts.items():
                        stock_concepts = set(concepts)
                        if limit_up_concepts & stock_concepts:
                            candidate_stocks.append(stock_code)

                # 排除参考股票本身
                candidate_stocks = [s for s in candidate_stocks if s != ref_code]

                if len(candidate_stocks) == 0:
                    logger.debug(f"      ⚠️ 无候选股票，跳过")
                    continue

                logger.debug(f"      📊 候选股票池: {len(candidate_stocks)}只")

                # 4.5 计算相似度（只分析前100只）
                similar_stocks = []
                for candidate_code in candidate_stocks[:100]:
                    similarity = _calculate_similarity(limit_up_features, candidate_code, zhitu, db_cache)
                    if similarity >= similarity_threshold:
                        similar_stocks.append({
                            'code': candidate_code,
                            'similarity': similarity,
                            'ref_stock': f"{ref_name}({ref_code})"
                        })

                # 按相似度排序，取TOP N
                similar_stocks.sort(key=lambda x: x['similarity'], reverse=True)
                similar_stocks = similar_stocks[:stocks_per_limit_up]

                if len(similar_stocks) > 0:
                    logger.debug(f"      🎯 找到{len(similar_stocks)}只相似股票（最高相似度{similar_stocks[0]['similarity']:.1f}%）")
                    all_similar_stocks.extend(similar_stocks)

            # 4.6 汇总所有相似股票，去重（保留相似度最高的）
            if len(all_similar_stocks) == 0:
                logger.info(f"   ⚠️ 无相似股票（相似度≥{similarity_threshold}%），跳过")
                continue

            # 按股票代码去重，保留相似度最高的
            unique_stocks = {}
            for stock in all_similar_stocks:
                code = stock['code']
                if code not in unique_stocks or stock['similarity'] > unique_stocks[code]['similarity']:
                    unique_stocks[code] = stock

            # 按相似度排序，只选择相似度最高的1只（单调模式）
            all_stocks_sorted = sorted(unique_stocks.values(), key=lambda x: x['similarity'], reverse=True)
            similar_stocks = all_stocks_sorted[:stocks_per_limit_up]  # 只取TOP N只

            logger.info(f"   🎯 汇总找到{len(unique_stocks)}只相似股票，选择相似度最高的{len(similar_stocks)}只（最高相似度{similar_stocks[0]['similarity']:.1f}%）")

            # 4.7 追踪相似股票在后续N天的表现
            # 获取买入日期（下一个交易日）和卖出日期（N天后）
            current_idx = i - 1  # 当前日期在列表中的索引
            buy_date_idx = current_idx + 1
            sell_date_idx = buy_date_idx + holding_days

            buy_date = trade_dates[buy_date_idx]
            sell_date = trade_dates[sell_date_idx]

            # 计算每只相似股票的收益率
            for stock in similar_stocks:
                stock_code = stock['code']
                similarity = stock['similarity']
                ref_stock_info = stock['ref_stock']

                try:
                    # 添加市场后缀
                    if stock_code.startswith('6'):
                        stock_symbol = f"{stock_code}.SH"
                    else:
                        stock_symbol = f"{stock_code}.SZ"

                    # 获取K线数据（买入日到卖出日）
                    # 日期格式需要转换为YYYYMMDD
                    start_time = buy_date.replace('-', '')
                    end_time = sell_date.replace('-', '')

                    kline_data = zhitu.get_history_timeframe(
                        stock_symbol=stock_symbol,
                        timeframe='d',
                        start_time=start_time,
                        end_time=end_time
                    )

                    if not kline_data or len(kline_data) < 2:
                        logger.debug(f"      ⚠️ {stock_code} K线数据不足: {len(kline_data) if kline_data else 0}条")
                        continue

                    # 买入价：下一个交易日开盘价
                    buy_price = kline_data[0]['o']

                    # 卖出价：N天后收盘价
                    sell_price = kline_data[-1]['c']

                    # 计算收益率
                    return_rate = (sell_price - buy_price) / buy_price * 100

                    # 统计
                    total_trades += 1
                    total_return += return_rate

                    if return_rate > 0:
                        win_trades += 1

                    if return_rate > max_return:
                        max_return = return_rate

                    if return_rate < max_loss:
                        max_loss = return_rate

                    # 记录交易明细
                    trade_details.append({
                        'date': trade_date,
                        'ref_stock': ref_stock_info,
                        'stock_code': stock_code,
                        'similarity': similarity,
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'return_rate': return_rate,
                        'holding_days': holding_days
                    })

                    logger.info(f"      ✅ {stock_code} 相似度{similarity:.1f}% 收益率{return_rate:+.2f}%")

                except Exception as e:
                    logger.warning(f"      ⚠️ {stock_code} 数据获取失败: {e}")
                    continue

            # 成功处理一个交易日
            valid_trade_count += 1

        except Exception as e:
            logger.error(f"   ❌ 回测失败: {e}")
            continue

    # 5. 生成回测报告
    if total_trades == 0:
        return "回测失败: 没有有效的交易数据"

    win_rate = win_trades / total_trades * 100
    avg_return = total_return / total_trades

    # 计算月度累计收益（假设每次投入相同资金）
    # 简化计算：累计收益 = 总收益率
    cumulative_return = total_return

    # 计算月化收益率（假设20个交易日为1个月）
    monthly_return = (cumulative_return / backtest_days) * 20

    result_lines = [f"=== 涨停形态匹配回测报告（T+1单股模式）===\n"]
    result_lines.append(f"📅 回测周期: {trade_dates[0]} ~ {trade_dates[-1]}")
    result_lines.append(f"📊 回测天数: {valid_trade_count}个有效交易日")
    result_lines.append(f"⏱️ 持仓周期: T+{holding_days}（买入后第{holding_days+1}天卖出）")
    result_lines.append(f"🎯 相似度阈值: {similarity_threshold}%")
    result_lines.append(f"💼 交易模式: 每天买入1只最相似股票，次日卖出\n")

    result_lines.append(f"📈 回测结果:")
    result_lines.append(f"  总交易次数: {total_trades}次")
    result_lines.append(f"  盈利次数: {win_trades}次")
    result_lines.append(f"  亏损次数: {total_trades - win_trades}次")
    result_lines.append(f"  胜率: {win_rate:.2f}%")
    result_lines.append(f"  平均收益率: {avg_return:+.2f}%")
    result_lines.append(f"  累计收益率: {cumulative_return:+.2f}%")
    result_lines.append(f"  月化收益率: {monthly_return:+.2f}%")
    result_lines.append(f"  最大单笔收益: {max_return:+.2f}%")
    result_lines.append(f"  最大单笔亏损: {max_loss:+.2f}%\n")

    # 展示部分交易明细（最多10条）
    result_lines.append(f"💼 交易明细（最近10笔）:")
    for i, trade in enumerate(trade_details[-10:], 1):
        result_lines.append(
            f"  {i}. {trade['date']} | 参考:{trade['ref_stock']} | "
            f"买入:{trade['stock_code']} | 相似度{trade['similarity']:.1f}% | "
            f"收益率{trade['return_rate']:+.2f}%"
        )

    result_lines.append(f"\n💡 策略评估:")
    if win_rate >= 60 and monthly_return >= 10:
        result_lines.append("  ✅ 策略表现优秀！胜率和月化收益率都很高")
        result_lines.append(f"  💰 如果投入10万元，预计月收益: {10 * monthly_return / 100:.0f}元")
    elif win_rate >= 50 and monthly_return >= 5:
        result_lines.append("  ✅ 策略表现良好，具有实战价值")
        result_lines.append(f"  💰 如果投入10万元，预计月收益: {10 * monthly_return / 100:.0f}元")
    elif win_rate >= 40:
        result_lines.append("  ⚠️ 策略表现一般，建议优化相似度算法或持仓周期")
    else:
        result_lines.append("  ❌ 策略表现较差，需要重新设计")

    # 风险提示
    result_lines.append(f"\n⚠️ 风险提示:")
    result_lines.append(f"  - 最大单笔亏损: {max_loss:+.2f}%，需要做好止损准备")
    result_lines.append(f"  - 历史回测不代表未来收益，实盘需谨慎")
    result_lines.append(f"  - 建议控制单笔仓位，分散风险")

    logger.info(f"✅ 回测完成")

    return "\n".join(result_lines)

