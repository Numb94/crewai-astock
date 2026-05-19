#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - 数据库查询工具

为CrewAI Agent提供数据库查询能力

✅ 多用户支持：所有工具函数通过context参数接收session_id
"""

from crewai.tools import tool
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any
import json
from decimal import Decimal
from loguru import logger
import threading

# ✅ 移到顶部导入，避免CrewAI工具验证失败
from src.database.db_manager import get_db
from src.database.models import SystemConfig, Candidate, Transaction, StrategyExecution, StrategyWeight


# ✅ 使用UserContainerManager管理session_id（支持多用户并发）
from src.core.user_container import get_container_manager


def set_current_session_id(session_id: str):
    """
    设置当前的session_id（使用contextvars）

    Args:
        session_id: 用户session_id
    """
    manager = get_container_manager()
    manager.set_current_session(session_id)
    logger.debug(f"🔄 设置当前session_id: {session_id[:8]}...")


def get_current_session_id() -> str:
    """
    获取当前的session_id（从contextvars）

    Returns:
        session_id，默认为'default'
    """
    manager = get_container_manager()
    return manager.get_current_session()


# ✅ 辅助函数：从context中获取session_id（保留兼容性）
def get_session_id_from_context(context: Optional[Dict[str, Any]] = None) -> str:
    """
    从CrewAI context中获取session_id

    优先级：
    1. 全局变量（线程安全）
    2. context参数
    3. 默认值'default'

    Args:
        context: CrewAI传递的上下文字典

    Returns:
        session_id，默认为'default'
    """
    thread_id = threading.current_thread().ident

    # 🔴 优先从全局变量获取
    global_session_id = get_current_session_id()

    # 从context获取（用于日志对比）
    context_session_id = 'default'
    if context and isinstance(context, dict):
        context_session_id = context.get('session_id', 'default')

    # 🔴 详细日志
    logger.debug(f"🔍 [线程{thread_id}] get_session_id_from_context:")
    logger.debug(f"  - 全局变量session_id: {global_session_id}")
    logger.debug(f"  - context参数session_id: {context_session_id}")
    logger.debug(f"  - 最终使用session_id: {global_session_id if global_session_id != 'default' else context_session_id}")

    # 优先使用全局变量
    if global_session_id != 'default':
        return global_session_id

    # 兼容旧方式：从context获取
    return context_session_id


@tool("查询当前总资产")
def query_total_assets() -> str:
    """
    从system_config表查询当前总资产

    优先级：
    1. 同花顺实时数据（account_总资产）
    2. 账户配置数据（account_capital）
    3. 默认值（100000元）

    Returns:
        总资产金额（元）
    """
    # ✅ 获取session_id（从全局变量）
    session_id = get_current_session_id()
    logger.debug(f"� [查询总资产] 使用 session_id: {session_id}")
    db = get_db()

    try:
        with db.get_session() as session:
            # 🔴 优先查询同花顺实时数据（account_总资产）
            ths_config = session.query(SystemConfig).filter(
                SystemConfig.session_id == session_id,
                SystemConfig.config_key == 'account_总资产'
            ).first()

            if ths_config:
                try:
                    total_assets = float(ths_config.config_value)
                    logger.info(f"✅ [同花顺数据] 查询总资产成功：{total_assets:.2f}元")
                    return f"当前总资产：{total_assets:.2f}元（同花顺实时数据）"
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ 同花顺数据解析失败: {e}，降级到account_capital")

            # 🔴 降级：查询account_capital配置项
            config = session.query(SystemConfig).filter(
                SystemConfig.session_id == session_id,
                SystemConfig.config_key == 'account_capital'
            ).first()

            if not config:
                logger.warning(f"[{session_id[:8]}] 未配置总资产，使用默认值：100000元")
                return "未配置总资产，默认总资产：100000元"

            # ✅ 解析JSON配置
            capital_config = json.loads(config.config_value)

            # ✅ 计算总资产 = 初始资金 + 追加资金 - 提取资金
            total_assets = (
                capital_config.get('initial_capital', 100000) +
                capital_config.get('additional_capital', 0) -
                capital_config.get('withdrawn_capital', 0)
            )

            logger.info(f"✅ [配置数据] 查询总资产成功：{total_assets:.2f}元")
            return f"当前总资产：{total_assets:.2f}元（配置数据）"

    except Exception as e:
        logger.error(f"❌ 查询总资产失败: {str(e)}")
        return f"查询总资产失败: {str(e)}"


@tool("根据总资产计算推荐数量")
def calculate_recommended_count() -> str:
    """
    🔴 根据总资产计算应该推荐的股票数量

    核心逻辑：
    推荐数量只跟总资产有关，与持仓无关
    - 总资产 < 10万 → 推荐1只（集中火力）
    - 总资产 10-30万 → 推荐2只（适度分散）
    - 总资产 > 30万 → 推荐3只（充分分散）

    注意：
    - 即使满仓，也要推荐股票
    - 投资决策官会对比持仓和推荐，给出"卖A买B"或"保留A"的建议

    Returns:
        推荐数量和详细理由
    """
    from src.database.models import Position

    # ✅ 获取session_id（从全局变量）
    session_id = get_current_session_id()
    db = get_db()

    try:
        # 🔴 日志：确认使用的 session_id
        logger.info(f"💰 [calculate_recommended_count] 使用 session_id: {session_id}")

        with db.get_session() as session:
            # ✅ 1. 获取总资产（优先使用同花顺实时数据）
            # 🔴 优先查询同花顺实时数据（account_总资产）
            ths_config = session.query(SystemConfig).filter(
                SystemConfig.session_id == session_id,
                SystemConfig.config_key == 'account_总资产'
            ).first()

            total_assets = None
            if ths_config:
                try:
                    total_assets = float(ths_config.config_value)
                    logger.info(f"✅ [同花顺数据] 总资产：{total_assets:.2f}元")
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ 同花顺数据解析失败: {e}，降级到account_capital")

            # 🔴 降级：查询account_capital配置项
            if total_assets is None:
                config = session.query(SystemConfig).filter(
                    SystemConfig.session_id == session_id,
                    SystemConfig.config_key == 'account_capital'
                ).first()

                if not config:
                    return "未配置总资产，默认推荐1只股票"

                capital_config = json.loads(config.config_value)
                total_assets = (
                    capital_config.get('initial_capital', 100000) +
                    capital_config.get('additional_capital', 0) -
                    capital_config.get('withdrawn_capital', 0)
                )
                logger.info(f"✅ [配置数据] 总资产：{total_assets:.2f}元")

            # ✅ 2. 查询当前持仓（仅用于展示，不影响推荐数量）
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.status == 'holding'
            ).all()

            # 🔴 修复：使用 current_price * quantity 计算持仓市值
            total_position_value = sum(
                float(p.current_price or 0) * float(p.quantity or 0)
                for p in positions
            )
            available_cash = total_assets - total_position_value

            # ✅ 3. 根据总资产决定推荐数量（固定规则）
            if total_assets < 100000:
                count = 1
                reason = "总资产不足10万，建议集中火力投资1只优质股票"
            elif total_assets < 300000:
                count = 2
                reason = "总资产10-30万，建议适度分散投资2只优质股票"
            else:
                count = 3
                reason = "总资产超过30万，建议充分分散投资3只优质股票"

            # ✅ 4. 构建详细报告
            result = f"""
=== 资产分析 ===
当前总资产：{total_assets:.2f}元
持仓数量：{len(positions)}只
持仓市值：{total_position_value:.2f}元
可用资金：{available_cash:.2f}元

=== 推荐数量 ===
推荐数量：{count}只股票
推荐理由：{reason}

⚠️ 重要说明：
- 推荐数量只跟总资产有关，与当前持仓无关
- 即使满仓，也会推荐股票
- 投资决策官会对比持仓和推荐，给出具体操作建议（卖A买B 或 保留A）
"""
            logger.info(f"✅ 计算推荐数量：{count}只（总资产{total_assets:.2f}元）")
            return result

    except Exception as e:
        logger.error(f"❌ 计算推荐数量失败: {str(e)}")
        return f"计算推荐数量失败: {str(e)}"


# ✅ 已删除query_yesterday_performance工具
# 原因：功能与analyze_recommendation_performance(days=-1)重复
# 问题：周一执行时会查询周日（无数据），导致"没有推荐记录"
# 替代方案：统一使用analyze_recommendation_performance(days=-1)，自动跳过周末


@tool("查询策略历史表现")
def query_strategy_performance() -> str:
    """
    实时计算所有策略最近7天的胜率、收益率、交易次数

    ✅ 策略数量是动态的，不限于8种
    ✅ 实时计算，不依赖strategy_weights表的缓存数据
    ✅ 支持多用户隔离

    注意：此工具会自动查询最近7天的数据，不需要传入任何参数

    Returns:
        策略表现报告（包含胜率、收益率、交易次数、状态）
    """
    from src.tools.zhitu_api import ZhituAPI
    from sqlalchemy import func
    from decimal import Decimal

    # ✅ 获取session_id（从全局变量）
    session_id = get_current_session_id()
    db = get_db()
    zhitu = ZhituAPI()
    days = 7  # 固定查询最近7天

    try:
        with db.get_session() as session:
            # 计算日期范围
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # ✅ 查询推荐记录（添加session_id过滤）
            candidates = session.query(Candidate).filter(
                Candidate.session_id == session_id,
                func.date(Candidate.recommend_time) >= start_date,
                func.date(Candidate.recommend_time) < end_date
            ).all()

            if not candidates:
                return f"最近{days}天没有推荐记录"

            # 统计数据
            strategy_stats = {}

            for candidate in candidates:
                # 跳过今天的推荐（至少需要1天时间验证）
                recommend_date = candidate.recommend_time.date()
                if recommend_date >= date.today():
                    continue

                recommend_price = candidate.recommend_price
                if not recommend_price or recommend_price == 0:
                    continue

                try:
                    # 1. 检查是否有卖出记录
                    sell_transaction = session.query(Transaction).filter(
                        Transaction.session_id == session_id,
                        Transaction.stock_code == candidate.stock_code,
                        Transaction.trade_type == 'SELL',
                        Transaction.trade_date >= recommend_date
                    ).order_by(Transaction.trade_date.asc()).first()

                    if sell_transaction:
                        # 使用实际卖出价格
                        sell_price = sell_transaction.price
                        change_pct = float((sell_price - recommend_price) / recommend_price * 100)
                    else:
                        # 2. 没有卖出记录，使用T+1日收盘价
                        next_day = recommend_date + timedelta(days=1)

                        # 获取T+1日历史数据（自动跳过周末/节假日）
                        stock_symbol = f"{candidate.stock_code}.{'SH' if candidate.stock_code.startswith('6') else 'SZ'}"
                        history_data = zhitu.get_history_timeframe(
                            stock_symbol=stock_symbol,
                            timeframe='d',
                            adjust_type='n',
                            start_time=next_day.strftime('%Y%m%d'),
                            end_time=(next_day + timedelta(days=7)).strftime('%Y%m%d')
                        )

                        if not history_data or len(history_data) == 0:
                            # T+1日没有数据（可能是周末/节假日），跳过
                            continue

                        # 取第一个交易日的收盘价
                        next_day_close = Decimal(str(history_data[0].get('c', 0)))
                        if next_day_close == 0:
                            continue

                        # 计算收益率（推荐价 → T+1收盘价）
                        change_pct = float((next_day_close - recommend_price) / recommend_price * 100)

                    # 按策略分组统计
                    strategy = candidate.strategy_name or "未知策略"
                    if strategy not in strategy_stats:
                        strategy_stats[strategy] = {
                            "count": 0,
                            "win_count": 0,
                            "total_return": 0
                        }

                    strategy_stats[strategy]["count"] += 1
                    strategy_stats[strategy]["total_return"] += change_pct
                    if change_pct > 0:
                        strategy_stats[strategy]["win_count"] += 1

                except Exception as e:
                    logger.warning(f"处理推荐记录失败 {candidate.stock_code}: {e}")
                    continue

            if not strategy_stats:
                return f"最近{days}天的推荐记录暂无可分析数据"

            # 格式化输出
            report_lines = [f"=== 最近{days}天策略表现（实时计算） ===\n"]
            report_lines.append(f"共{len(strategy_stats)}个策略\n")

            # 按胜率排序
            sorted_strategies = sorted(
                strategy_stats.items(),
                key=lambda x: (x[1]["win_count"] / x[1]["count"]) if x[1]["count"] > 0 else 0,
                reverse=True
            )

            for strategy, stats in sorted_strategies:
                win_rate = (stats["win_count"] / stats["count"] * 100) if stats["count"] > 0 else 0
                avg_return = (stats["total_return"] / stats["count"]) if stats["count"] > 0 else 0

                # 判断表现趋势
                if win_rate > 60:
                    trend = "强势"
                elif win_rate > 50:
                    trend = "正常"
                else:
                    trend = "弱势"

                report_lines.append(f"""
【{strategy}】
  胜率: {win_rate:.1f}% ({stats["win_count"]}/{stats["count"]})
  平均收益率: {avg_return:+.2f}%
  交易次数: {stats["count"]}次
  状态: {trend}
""")

            # 推荐建议
            report_lines.append("\n--- 策略建议 ---")

            if sorted_strategies:
                # 找出表现最好的策略
                best_strategy, best_stats = sorted_strategies[0]
                best_win_rate = (best_stats["win_count"] / best_stats["count"] * 100) if best_stats["count"] > 0 else 0
                if best_win_rate > 60:
                    report_lines.append(f"推荐使用: {best_strategy} (胜率{best_win_rate:.1f}%)")

                # 找出表现最差的策略
                worst_strategy, worst_stats = sorted_strategies[-1]
                worst_win_rate = (worst_stats["win_count"] / worst_stats["count"] * 100) if worst_stats["count"] > 0 else 0
                if worst_win_rate < 50:
                    report_lines.append(f"不建议使用: {worst_strategy} (胜率{worst_win_rate:.1f}%)")

            return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"查询策略表现失败: {e}")
        return f"查询策略表现失败: {str(e)}"


@tool("保存推荐结果到数据库")
def save_recommendations_to_db(recommendations_json: str) -> str:
    """
    将CEO的最终推荐结果保存到candidates和strategy_executions表

    Args:
        recommendations_json: JSON格式的推荐结果

    Returns:
        保存结果说明
    """
    # ✅ 获取session_id（从全局变量）
    session_id = get_current_session_id()
    db = get_db()

    try:
        recs = json.loads(recommendations_json)

        # ✅ 直接使用Agent输出的策略名称（不转换）
        strategy_name = recs.get('strategy', '未知策略')
        stock_codes = [s['code'] for s in recs.get('stocks', [])]
        logger.warning(f"🔴🔴🔴 save_recommendations_to_db 被调用！session_id={session_id[:8]}, 策略={strategy_name}, 股票={stock_codes}")
        logger.info(f"📊 [{session_id[:8]}] 保存推荐策略: {strategy_name}")

        # ✅ 过滤非交易日：如果当前是周末，调整到下一个交易日
        from src.utils.trading_calendar import is_trading_day, get_next_trading_day

        current_date = date.today()
        current_time = datetime.now()
        recommend_date = current_date

        if not is_trading_day(current_date):
            recommend_date = get_next_trading_day(from_date=current_date)
            logger.info(f"📅 当前是非交易日，推荐日期已调整: {current_date} -> {recommend_date}")
            # 非交易日：设置推荐时间为下一个交易日的开盘时间（9:30）
            recommend_time = datetime.combine(recommend_date, datetime.min.time().replace(hour=9, minute=30))
        else:
            # ✅ 交易日：使用当前实际时间
            recommend_time = current_time
            logger.info(f"📅 当前是交易日，推荐时间: {recommend_time.strftime('%Y-%m-%d %H:%M:%S')}")

        expected_buy_time = recommend_time
        can_sell_date = recommend_date + timedelta(days=1)  # T+1

        with db.get_session() as session:
            # 🔴 不再检查是否已保存过推荐，允许用户多次点击"AI推荐"
            # 🔴 但是会在下面的循环中检查相同股票，进行去重合并
            today_start = datetime.combine(date.today(), datetime.min.time())

            # ✅ 动态创建策略权重记录（如果不存在）
            existing_strategy = session.query(StrategyWeight).filter(
                StrategyWeight.session_id == session_id,
                StrategyWeight.strategy_name == strategy_name
            ).first()

            if not existing_strategy:
                # 创建新策略记录
                new_strategy = StrategyWeight(
                    session_id=session_id,
                    strategy_name=strategy_name,
                    current_weight=1.0,
                    previous_weight=1.0,
                    weight_change=0.0,
                    rolling_30d_win_rate=0.0,
                    rolling_30d_return_pct=0.0,
                    rolling_30d_trades=0,
                    is_enabled=True,
                    adjustment_reason=f'AI自主创建策略：{strategy_name}',
                    last_review_date=date.today()
                )
                session.add(new_strategy)
                logger.success(f"🆕 [{session_id[:8]}] 创建新策略: {strategy_name}")

            # ✅ 保存到candidates表（添加session_id + 去重合并）
            saved_count = 0
            merged_count = 0

            for stock in recs.get('stocks', []):
                stock_code = stock['code']

                # 🔴 检查今天是否已经推荐过这只股票
                existing = session.query(Candidate).filter(
                    Candidate.session_id == session_id,
                    Candidate.stock_code == stock_code,
                    Candidate.recommend_time >= today_start
                ).first()

                # 🔴 调试日志
                logger.warning(f"🔍 检查股票 {stock_code}: session_id={session_id[:8]}, today_start={today_start}, existing={'存在' if existing else '不存在'}")
                if existing:
                    logger.warning(f"   已存在记录: id={existing.id}, recommend_time={existing.recommend_time}, strategy={existing.strategy_name}")

                if existing:
                    # 🔴 已存在，合并推荐理由
                    merged_count += 1

                    # 合并推荐理由
                    new_reason = f"\n\n【{strategy_name}】{stock.get('reason', '')}"
                    if existing.ceo_reason:
                        existing.ceo_reason += new_reason
                    else:
                        existing.ceo_reason = new_reason

                    # 🔴 修改：总是更新推荐价格和推荐时间为最新的（使用调整后的交易日时间）
                    existing.recommend_time = recommend_time
                    existing.recommend_price = stock.get('recommend_price', 0)
                    existing.target_price = stock.get('target_price', 0)

                    # 更新评分（取最高分）
                    new_final_score = stock.get('final_score', 0)
                    if new_final_score > (existing.final_score or 0):
                        existing.final_score = new_final_score
                        # 🔴 LLM 输出可能用 'technical_score' 或 'tech_score' 两种命名，兼容
                        existing.cto_score = stock.get('technical_score', stock.get('tech_score', 0))
                        existing.cfo_score = stock.get('fund_score', 0)
                        existing.cmo_score = stock.get('fundamental_score', 0)
                        # CSO = 新闻面与社区情绪的平均（若都缺则保持 None）
                        _news = stock.get('news_score')
                        _comm = stock.get('community_sentiment_score')
                        if _news is not None and _comm is not None:
                            existing.cso_score = (float(_news) + float(_comm)) / 2
                        elif _news is not None:
                            existing.cso_score = float(_news)
                        elif _comm is not None:
                            existing.cso_score = float(_comm)
                        existing.ceo_decision = stock.get('decision', 'BUY')

                    # 合并策略名称
                    if strategy_name not in existing.strategy_name:
                        existing.strategy_name += f" + {strategy_name}"

                    logger.info(f"  🔄 合并推荐: {stock_code} {stock['name']} (策略: {strategy_name}, 更新推荐价:{existing.recommend_price})")
                else:
                    # 🔴 不存在，新增推荐（使用调整后的交易日时间）
                    # CSO = 新闻面与社区情绪的平均
                    _news = stock.get('news_score')
                    _comm = stock.get('community_sentiment_score')
                    if _news is not None and _comm is not None:
                        _cso = (float(_news) + float(_comm)) / 2
                    elif _news is not None:
                        _cso = float(_news)
                    elif _comm is not None:
                        _cso = float(_comm)
                    else:
                        _cso = None

                    candidate = Candidate(
                        session_id=session_id,  # ✅ 添加session_id
                        stock_code=stock_code,
                        stock_name=stock['name'],
                        recommend_time=recommend_time,  # ✅ 使用调整后的交易日时间
                        recommend_track='manual',  # 手动触发
                        expected_buy_time=expected_buy_time,  # ✅ 使用调整后的交易日时间
                        can_sell_date=can_sell_date,  # ✅ 使用调整后的T+1日期
                        strategy_name=strategy_name,  # ✅ 直接保存策略名称
                        final_score=stock.get('final_score', 0),
                        # 🔴 LLM 输出可能用 'technical_score' 或 'tech_score'，兼容两种
                        cto_score=stock.get('technical_score', stock.get('tech_score', 0)),
                        cfo_score=stock.get('fund_score', 0),
                        cmo_score=stock.get('fundamental_score', 0),
                        cso_score=_cso,
                        ceo_decision=stock.get('decision', 'BUY'),
                        ceo_reason=f"【{strategy_name}】{stock.get('reason', '')}",  # ✅ 添加策略标签
                        cro_approved=stock.get('cro_approved', True),
                        cro_risk_level=stock.get('risk_level', 'medium'),
                        recommend_price=stock.get('recommend_price', 0),
                        target_price=stock.get('target_price', 0)
                    )
                    session.add(candidate)
                    saved_count += 1
                    logger.info(f"  ✅ 新增推荐: {stock_code} {stock['name']} (策略: {strategy_name})")

            # ✅ 保存到strategy_executions表（添加session_id，使用调整后的交易日）
            execution = StrategyExecution(
                session_id=session_id,  # ✅ 添加session_id
                execution_date=recommend_date,  # ✅ 使用调整后的交易日
                market_state=recs.get('market_state', 'neutral'),
                primary_strategy=strategy_name,  # ✅ 直接保存策略名称
                ceo_decision=recs.get('ceo_summary', ''),
                recommended_stocks=[{
                    'code': s['code'],
                    'name': s['name'],
                    'score': s.get('final_score', 0)
                } for s in recs.get('stocks', [])]
            )
            session.add(execution)

            session.commit()

            # 🔴 返回详细统计
            result_msg = f"✅ 成功保存推荐到数据库（策略：{strategy_name}）\n"
            result_msg += f"   新增推荐: {saved_count}只\n"
            if merged_count > 0:
                result_msg += f"   合并推荐: {merged_count}只（多个策略推荐同一股票）"

            return result_msg

    except json.JSONDecodeError as e:
        return f"JSON解析失败: {str(e)}"
    except Exception as e:
        return f"保存到数据库失败: {str(e)}"
