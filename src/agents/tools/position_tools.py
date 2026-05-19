#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - 持仓管理工具

为CrewAI Agent提供持仓查询、风险计算能力
"""

from crewai.tools import tool
from typing import Dict, List
from datetime import date, datetime, timedelta
import json
from loguru import logger


@tool("查询当前持仓")
def query_current_positions() -> str:
    """
    查询当前所有持仓，包括盈亏情况、行业分布

    ⚡ 重要：此工具会自动更新数据库中的实时价格和盈亏数据

    Returns:
        持仓详情(自然语言描述)
    """
    from src.database.db_manager import get_db
    from src.database.models import Position
    from src.tools.zhitu_api import ZhituAPI
    from decimal import Decimal
    # 🔴 导入session_id获取函数
    from src.agents.tools.database_tools import get_current_session_id

    db = get_db()
    # 🔴 获取当前用户的session_id
    session_id = get_current_session_id()

    try:
        with db.get_session() as session:
            # 🔴 查询当前用户的持仓（添加session_id过滤）
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.status == 'holding'
            ).all()

            if not positions:
                return "当前无持仓"

            # ✅ 获取实时价格并更新数据库
            stock_codes = [p.stock_code for p in positions]
            zhitu = ZhituAPI()

            try:
                prices_data = zhitu.get_real_time_multi_broker(stock_codes)
                logger.info(f"✅ 获取实时价格成功: {len(prices_data)}只股票")

                # 更新每个持仓的实时价格和盈亏
                for position in positions:
                    price_info = prices_data.get(position.stock_code, {})
                    if price_info:
                        # ✅ 修复：字段名已经被映射为 'current_price'，不是 'p'
                        price_value = price_info.get('current_price') or price_info.get('p', position.buy_price)
                        current_price = Decimal(str(price_value))

                        # 更新持仓数据
                        position.current_price = current_price
                        position.profit_loss = (current_price - position.buy_price) * position.quantity
                        position.profit_loss_pct = ((current_price - position.buy_price) / position.buy_price) * 100

                        logger.debug(f"更新 {position.stock_code} 价格: {current_price}")

                # 提交更新到数据库
                session.commit()
                logger.info("✅ 数据库价格更新成功")

            except Exception as e:
                logger.error(f"❌ 获取实时价格失败: {e}")
                # 即使获取价格失败，也继续使用数据库中的旧价格

            # 统计数据（使用更新后的数据）
            total_positions = len(positions)
            total_amount = sum(float(p.buy_amount or 0) for p in positions)
            total_pnl = sum(float(p.profit_loss or 0) for p in positions)

            # 格式化输出
            result_lines = [f"=== 当前持仓 (共{total_positions}只) ===\n"]
            result_lines.append(f"总持仓金额: {total_amount:.2f}元")
            result_lines.append(f"总浮动盈亏: {total_pnl:+.2f}元\n")

            for i, pos in enumerate(positions, 1):
                pnl_pct = float(pos.profit_loss_pct or 0)
                pnl = float(pos.profit_loss or 0)
                current_price = float(pos.current_price or 0)

                result_lines.append(
                    f"{i}. {pos.stock_name}({pos.stock_code}) "
                    f"买入价:{float(pos.buy_price):.2f} "
                    f"当前价:{current_price:.2f} "
                    f"数量:{pos.quantity}股 "
                    f"盈亏:{pnl:+.2f}元({pnl_pct:+.2f}%) "
                    f"策略:{pos.strategy_used or 'N/A'}"
                )

            return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"查询持仓失败: {e}")
        return f"查询持仓失败: {str(e)}"


@tool("查询最近卖出的股票")
def query_recently_sold_positions(days: int = 7) -> str:
    """
    查询最近N天内卖出的股票，根据卖出原因设置冷却期

    冷却期规则：
    - 止损卖出：7天冷却期（股票走势不好，不应短期内再推荐）
    - 止盈卖出：3天冷却期（可能还有机会，但需要观察）
    - 手动卖出：5天冷却期（用户主动卖出，可能有特殊原因）
    - 其他原因：5天冷却期（默认）

    Args:
        days: 查询最近N天内的卖出记录，默认7天

    Returns:
        最近卖出的股票列表（JSON格式），包含冷却期信息
    """
    from src.database.db_manager import get_db
    from src.database.models import Position
    from src.agents.tools.database_tools import get_current_session_id

    db = get_db()
    session_id = get_current_session_id()

    try:
        with db.get_session() as session:
            # 计算查询起始日期
            start_date = datetime.now().date() - timedelta(days=days)

            # 查询最近N天内卖出的股票
            sold_positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.status == 'sold',
                Position.sell_date >= start_date
            ).order_by(Position.sell_date.desc()).all()

            if not sold_positions:
                return json.dumps({
                    "total": 0,
                    "stocks": [],
                    "message": f"最近{days}天内无卖出记录"
                }, ensure_ascii=False)

            # 冷却期规则
            cooldown_rules = {
                '止损': 7,  # 止损卖出：7天冷却期
                '止盈': 3,  # 止盈卖出：3天冷却期
                '手动': 5,  # 手动卖出：5天冷却期
                '其他': 5   # 其他原因：5天冷却期
            }

            # 构建结果
            stocks = []
            in_cooldown_codes = []  # 冷却期内的股票代码

            for pos in sold_positions:
                sell_reason = pos.sell_reason or '其他'
                cooldown_days = cooldown_rules.get(sell_reason, 5)

                # 计算剩余冷却天数
                days_since_sell = (datetime.now().date() - pos.sell_date).days
                remaining_cooldown = max(0, cooldown_days - days_since_sell)

                stock_info = {
                    'stock_code': pos.stock_code,
                    'stock_name': pos.stock_name,
                    'sell_date': pos.sell_date.strftime('%Y-%m-%d'),
                    'sell_price': float(pos.sell_price) if pos.sell_price else 0,
                    'sell_reason': sell_reason,
                    'buy_price': float(pos.buy_price),
                    'profit_loss_pct': float(pos.profit_loss_pct) if pos.profit_loss_pct else 0,
                    'cooldown_days': cooldown_days,
                    'days_since_sell': days_since_sell,
                    'remaining_cooldown': remaining_cooldown,
                    'in_cooldown': remaining_cooldown > 0
                }

                stocks.append(stock_info)

                # 如果还在冷却期内，记录股票代码
                if remaining_cooldown > 0:
                    in_cooldown_codes.append(pos.stock_code)

            # 统计信息
            total_sold = len(stocks)
            in_cooldown_count = len(in_cooldown_codes)

            result = {
                'total': total_sold,
                'in_cooldown_count': in_cooldown_count,
                'in_cooldown_codes': in_cooldown_codes,
                'stocks': stocks,
                'message': f"最近{days}天内卖出{total_sold}只股票，其中{in_cooldown_count}只仍在冷却期内"
            }

            logger.info(f"📊 查询最近卖出股票: {total_sold}只，冷却期内{in_cooldown_count}只")
            logger.info(f"   冷却期内股票: {in_cooldown_codes}")

            return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"查询最近卖出股票失败: {e}")
        return json.dumps({
            "error": str(e),
            "message": "查询失败"
        }, ensure_ascii=False)


@tool("计算组合风险")
def calculate_portfolio_risk(new_stock_code: str, new_position_pct: float) -> str:
    """
    计算加入新股票后的组合风险，检查总仓位、行业集中度

    Args:
        new_stock_code: 新股票代码
        new_position_pct: 新股票仓位百分比(0-1之间)

    Returns:
        风险评估结果(自然语言描述)
    """
    from src.database.db_manager import get_db
    from src.database.models import Position
    # 🔴 导入session_id获取函数
    from src.agents.tools.database_tools import get_current_session_id

    db = get_db()
    # 🔴 获取当前用户的session_id
    session_id = get_current_session_id()

    try:
        # 获取股票名称
        stock_name = 'N/A'
        try:
            from src.agents.tools.market_tools import _get_all_broker_data_with_names
            broker_stocks = _get_all_broker_data_with_names()
            for stock in broker_stocks:
                if stock.get('dm') == new_stock_code:
                    stock_name = stock.get('name', 'N/A')
                    break
        except Exception as e:
            logger.warning(f"获取股票名称失败: {e}")

        with db.get_session() as session:
            # 🔴 查询当前用户的持仓（添加session_id过滤）
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.status == 'holding'
            ).all()

            # 计算当前总仓位
            current_total_position = sum(float(p.position_pct or 0) for p in positions)

            # 加入新股票后的总仓位
            new_total_position = current_total_position + new_position_pct

            # 风险评估（激进策略：满仓单调）
            risk_factors = []
            risk_level = "low"
            approved = True

            # 1. 总仓位检查（放宽限制，支持满仓）
            if new_total_position > 1.0:
                risk_factors.append(f"总仓位超过100%({new_total_position*100:.1f}%)")
                risk_level = "high"
                approved = False
            elif new_total_position > 0.95:
                risk_factors.append(f"接近满仓({new_total_position*100:.1f}%)")
                risk_level = "medium"
                # 满仓是允许的，不拒绝

            # 2. 单票仓位检查（放宽限制，支持单调）
            if new_position_pct > 1.0:
                risk_factors.append(f"单票仓位超过100%({new_position_pct*100:.1f}%)")
                risk_level = "high"
                approved = False
            elif new_position_pct > 0.80:
                risk_factors.append(f"单票仓位很高({new_position_pct*100:.1f}%)，高风险高收益")
                if risk_level == "low":
                    risk_level = "medium"
                # 单调是允许的，不拒绝

            # 3. 持仓数量检查（放宽限制）
            if len(positions) >= 3:
                risk_factors.append(f"持仓数量较多({len(positions)}只)，建议集中持仓")
                if risk_level == "low":
                    risk_level = "medium"

            # 格式化输出
            result = f"""
=== 组合风险评估 ===

新股票: {stock_name}({new_stock_code})
新增仓位: {new_position_pct*100:.1f}%

当前持仓数: {len(positions)}只
当前总仓位: {current_total_position*100:.1f}%
新增后总仓位: {new_total_position*100:.1f}%

风险等级: {risk_level.upper()}
是否批准: {'✓ 批准' if approved else '✗ 拒绝'}

风险因素: {', '.join(risk_factors) if risk_factors else '无明显风险'}

建议: {'可以买入' if approved else '建议降低仓位或观望'}

💡 策略提示: 月收益目标50%+，建议满仓单调，集中火力
"""
            return result
            
    except Exception as e:
        return f"计算组合风险失败: {str(e)}"


@tool("更新移动止盈数据")
def update_trailing_stop_data() -> str:
    """
    更新可卖出持仓的移动止盈数据（T+1约束）

    功能：
    1. 只处理可卖出的持仓（can_sell_date <= 今天）
    2. 记录当日开盘价（如果未记录）
    3. 更新当日最高价
    4. 判断是否触发移动止盈（从最高价回落≥1%）

    Returns:
        更新结果（自然语言描述）
    """
    from src.database.db_manager import get_db
    from src.database.models import Position
    from src.tools.zhitu_api import ZhituAPI
    from decimal import Decimal
    from datetime import datetime, date as dt_date
    from src.agents.tools.database_tools import get_current_session_id

    db = get_db()
    session_id = get_current_session_id()
    today = dt_date.today()

    try:
        with db.get_session() as session:
            # 查询可卖出的持仓
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.status == 'holding',
                Position.can_sell_date <= today
            ).all()

            if not positions:
                return "当前无可卖出的持仓"

            # 获取实时价格
            stock_codes = [p.stock_code for p in positions]
            zhitu = ZhituAPI()
            prices_data = zhitu.get_real_time_multi_broker(stock_codes)

            updated_count = 0
            triggered_count = 0
            results = []

            for position in positions:
                price_info = prices_data.get(position.stock_code, {})
                if not price_info:
                    continue

                current_price = Decimal(str(price_info.get('current_price') or price_info.get('p', 0)))
                if current_price == 0:
                    continue

                # 1. 记录开盘价（如果未记录）
                if position.today_open_price is None:
                    position.today_open_price = current_price
                    logger.info(f"{position.stock_code} 记录开盘价: {current_price}")

                # 2. 更新最高价
                if position.today_highest_price is None or current_price > position.today_highest_price:
                    position.today_highest_price = current_price
                    position.today_highest_time = datetime.now()
                    logger.info(f"{position.stock_code} 更新最高价: {current_price}")

                # 3. 判断是否触发移动止盈（动态阈值）
                if position.today_highest_price and not position.trailing_stop_triggered:
                    # 计算回落幅度
                    pullback_pct = ((position.today_highest_price - current_price) / position.today_highest_price) * 100

                    # 计算当前盈利幅度
                    profit_pct = ((current_price - position.buy_price) / position.buy_price) * 100

                    # 🆕 动态回落阈值：根据盈利幅度调整
                    if profit_pct >= 10:
                        threshold = 2.5  # 高盈利，给予更大回落空间
                    elif profit_pct >= 5:
                        threshold = 2.0  # 中等盈利，适度保护
                    elif profit_pct >= 3:
                        threshold = 1.5  # 小盈利，较严格保护
                    elif profit_pct >= 0:
                        threshold = 1.0  # 微盈利，严格保护（原规则）
                    else:
                        threshold = None  # 亏损状态，不触发移动止盈

                    if threshold and pullback_pct >= threshold:
                        position.trailing_stop_triggered = True
                        triggered_count += 1

                        results.append(
                            f"🔴 {position.stock_name}({position.stock_code}): "
                            f"最高价¥{position.today_highest_price:.2f} → 当前价¥{current_price:.2f} "
                            f"(回落{pullback_pct:.2f}% >= {threshold}%), 当前盈利{profit_pct:+.2f}%"
                        )

                        logger.warning(f"🔴 触发移动止盈: {position.stock_code} 回落{pullback_pct:.2f}% (阈值{threshold}%)")

                updated_count += 1

            session.commit()

            result_text = f"✅ 已更新 {updated_count} 只可卖出持仓的移动止盈数据\n"

            if triggered_count > 0:
                result_text += f"\n🔴 触发移动止盈: {triggered_count} 只\n"
                result_text += "\n".join(results)
            else:
                result_text += "\n✅ 暂无触发移动止盈的持仓"

            return result_text

    except Exception as e:
        logger.error(f"❌ 更新移动止盈数据失败: {e}")
        return f"更新移动止盈数据失败: {str(e)}"


@tool("检查开盘信号")
def check_opening_signal() -> str:
    """
    检查持仓股票的开盘信号（适用于隔夜短线策略）

    分析内容：
    1. 集合竞价/开盘价与昨收价对比
    2. 开盘价与买入价对比
    3. 给出开盘方向判断和操作建议

    信号级别：
    - 🟢 高开≥3%：冲高止盈信号，开盘就卖
    - 🟡 高开1-3%：正常，等冲高再卖
    - ⚪ 平开±1%：观察开盘走势
    - 🟠 低开1-3%：警惕，设好止损
    - 🔴 低开≥3%：紧急止损信号

    Returns:
        开盘信号分析结果
    """
    from src.database.db_manager import get_db
    from src.database.models import Position
    from src.tools.zhitu_api import ZhituAPI
    from decimal import Decimal
    from src.agents.tools.database_tools import get_current_session_id

    db = get_db()
    session_id = get_current_session_id()
    today = date.today()

    try:
        with db.get_session() as session:
            # 查询可卖出的持仓
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.status == 'holding',
                Position.can_sell_date <= today
            ).all()

            if not positions:
                return "当前无可卖出的持仓"

            # 获取实时行情数据
            stock_codes = [p.stock_code for p in positions]
            zhitu = ZhituAPI()
            prices_data = zhitu.get_real_time_multi_broker(stock_codes)

            results = []
            results.append("=== 开盘信号检查（隔夜短线策略）===\n")

            high_open_count = 0  # 高开数量
            low_open_count = 0   # 低开数量

            for position in positions:
                price_info = prices_data.get(position.stock_code, {})
                if not price_info:
                    results.append(f"❌ {position.stock_name}({position.stock_code}): 无法获取行情数据")
                    continue

                # 获取关键价格
                current_price = float(price_info.get('current_price') or price_info.get('p', 0))
                open_price = float(price_info.get('open_price') or price_info.get('o', current_price))
                prev_close = float(price_info.get('prev_close') or price_info.get('pc', 0))
                buy_price = float(position.buy_price)

                if prev_close == 0 or current_price == 0:
                    continue

                # 计算涨跌幅
                open_vs_prev_close_pct = ((open_price - prev_close) / prev_close) * 100  # 开盘vs昨收
                current_vs_prev_close_pct = ((current_price - prev_close) / prev_close) * 100  # 现价vs昨收
                current_vs_buy_pct = ((current_price - buy_price) / buy_price) * 100  # 现价vs买入价
                open_vs_buy_pct = ((open_price - buy_price) / buy_price) * 100  # 开盘vs买入价

                # 判断开盘信号
                if open_vs_prev_close_pct >= 3:
                    signal = "🟢 高开≥3%"
                    suggestion = "冲高止盈信号，建议开盘就卖"
                    high_open_count += 1
                elif open_vs_prev_close_pct >= 1:
                    signal = "🟡 高开1-3%"
                    suggestion = "正常高开，等冲高再卖"
                    high_open_count += 1
                elif open_vs_prev_close_pct >= -1:
                    signal = "⚪ 平开"
                    suggestion = "观察开盘走势"
                elif open_vs_prev_close_pct >= -3:
                    signal = "🟠 低开1-3%"
                    suggestion = "警惕，设好止损"
                    low_open_count += 1
                else:
                    signal = "🔴 低开≥3%"
                    suggestion = "紧急止损信号，考虑割肉"
                    low_open_count += 1

                # 格式化输出
                results.append(f"【{position.stock_name}({position.stock_code})】")
                results.append(f"  昨收价: ¥{prev_close:.2f}")
                results.append(f"  开盘价: ¥{open_price:.2f} ({open_vs_prev_close_pct:+.2f}%)")
                results.append(f"  现  价: ¥{current_price:.2f} ({current_vs_prev_close_pct:+.2f}%)")
                results.append(f"  买入价: ¥{buy_price:.2f}")
                results.append(f"  持仓盈亏: {current_vs_buy_pct:+.2f}%")
                results.append(f"  开盘信号: {signal}")
                results.append(f"  操作建议: {suggestion}")
                results.append("")

            # 汇总
            results.append("--- 汇总 ---")
            results.append(f"高开股票: {high_open_count}只")
            results.append(f"低开股票: {low_open_count}只")

            if low_open_count > 0:
                results.append("\n⚠️ 注意：有低开股票，请优先处理止损！")

            return "\n".join(results)

    except Exception as e:
        logger.error(f"❌ 检查开盘信号失败: {e}")
        return f"检查开盘信号失败: {str(e)}"


@tool("计算5分钟ATR")
def calculate_5min_atr(stock_code: str) -> str:
    """
    计算股票的5分钟级别ATR（平均真实波幅）

    用于隔夜短线策略，判断当前波动是否正常：
    - 回落 > 1.5×ATR_5min → 明显冲高回落，止盈信号
    - 回落 > 1.0×ATR_5min → 有回落迹象，关注
    - 回落 < 1.0×ATR_5min → 正常波动，持有

    Args:
        stock_code: 股票代码（如600000）

    Returns:
        5分钟ATR数据和波动分析
    """
    from src.tools.zhitu_api import ZhituAPI

    try:
        zhitu = ZhituAPI()

        # 转换股票代码格式
        if stock_code.startswith('6'):
            symbol = f"{stock_code}.SH"
        else:
            symbol = f"{stock_code}.SZ"

        # 获取5分钟K线数据（最近12根，约1小时）
        kline_data = zhitu.get_latest_timeframe(symbol, timeframe='5', limit=12)

        if not kline_data or len(kline_data) < 6:
            return f"❌ 无法获取{stock_code}的5分钟K线数据（数据不足）"

        # 计算TR（True Range）和ATR
        tr_list = []
        for i in range(1, len(kline_data)):
            high = float(kline_data[i].get('h', 0))
            low = float(kline_data[i].get('l', 0))
            prev_close = float(kline_data[i-1].get('c', 0))

            if high == 0 or low == 0 or prev_close == 0:
                continue

            # TR = max(H-L, |H-PC|, |L-PC|)
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)

        if not tr_list:
            return f"❌ 无法计算{stock_code}的5分钟ATR"

        # 计算ATR（简单移动平均）
        atr_5min = sum(tr_list) / len(tr_list)

        # 获取当前价格和今日最高价
        latest = kline_data[-1]
        current_price = float(latest.get('c', 0))
        today_high = max(float(k.get('h', 0)) for k in kline_data)

        # 计算从最高点的回落
        pullback = today_high - current_price
        pullback_atr_ratio = pullback / atr_5min if atr_5min > 0 else 0

        # 判断波动信号
        if pullback_atr_ratio >= 1.5:
            signal = "🔴 明显冲高回落"
            suggestion = "止盈信号，建议卖出"
        elif pullback_atr_ratio >= 1.0:
            signal = "🟠 有回落迹象"
            suggestion = "关注走势，准备止盈"
        elif pullback_atr_ratio >= 0.5:
            signal = "🟡 小幅回落"
            suggestion = "正常波动，可持有"
        else:
            signal = "🟢 走势正常"
            suggestion = "继续持有"

        # 格式化输出
        result = f"""=== {stock_code} 5分钟ATR分析 ===

📊 技术数据:
  5分钟ATR: ¥{atr_5min:.3f}
  当前价格: ¥{current_price:.2f}
  近1小时最高: ¥{today_high:.2f}
  回落幅度: ¥{pullback:.3f} ({pullback_atr_ratio:.2f}×ATR)

📈 波动信号: {signal}
💡 操作建议: {suggestion}

🔍 ATR解读:
  - 回落 > 1.5×ATR: 明显冲高回落，止盈
  - 回落 > 1.0×ATR: 有回落迹象，关注
  - 回落 < 1.0×ATR: 正常波动，持有
"""
        return result

    except Exception as e:
        logger.error(f"❌ 计算5分钟ATR失败: {e}")
        return f"计算5分钟ATR失败: {str(e)}"


@tool("检查早盘时间窗口")
def check_morning_time_window() -> str:
    """
    检查早盘时间窗口（适用于隔夜短线策略）

    时间窗口规则：
    - 9:30-9:45: 黄金15分钟，冲高回落要快速反应
    - 9:45-10:00: 趋势确认期，涨幅不及预期考虑减仓
    - 10:00-10:30: 最后窗口，不涨反跌应清仓
    - 10:30后: 错过最佳卖点，资金可能流出

    Returns:
        时间窗口分析和操作建议
    """
    from src.database.db_manager import get_db
    from src.database.models import Position
    from src.tools.zhitu_api import ZhituAPI
    from src.agents.tools.database_tools import get_current_session_id

    db = get_db()
    session_id = get_current_session_id()
    now = datetime.now()
    today = now.date()
    current_time = now.time()

    # 判断当前时间窗口
    from datetime import time as dt_time
    t_0930 = dt_time(9, 30)
    t_0945 = dt_time(9, 45)
    t_1000 = dt_time(10, 0)
    t_1030 = dt_time(10, 30)
    t_1130 = dt_time(11, 30)
    t_1300 = dt_time(13, 0)
    t_1500 = dt_time(15, 0)

    # 确定时间窗口
    if current_time < t_0930:
        window = "盘前"
        window_desc = "⏰ 尚未开盘，等待集合竞价"
        urgency = "low"
    elif current_time < t_0945:
        window = "黄金15分钟"
        window_desc = "🔥 黄金15分钟！冲高回落要快速反应"
        urgency = "high"
    elif current_time < t_1000:
        window = "趋势确认期"
        window_desc = "📊 趋势确认期，涨幅不及预期考虑减仓"
        urgency = "high"
    elif current_time < t_1030:
        window = "最后窗口"
        window_desc = "⚠️ 最后窗口！不涨反跌应清仓"
        urgency = "critical"
    elif current_time < t_1130:
        window = "上午尾盘"
        window_desc = "📉 已过最佳卖点，资金可能流出"
        urgency = "medium"
    elif current_time < t_1300:
        window = "午休"
        window_desc = "💤 午间休市"
        urgency = "low"
    elif current_time < t_1500:
        window = "下午盘"
        window_desc = "📊 下午盘，关注尾盘走势"
        urgency = "low"
    else:
        window = "已收盘"
        window_desc = "🔒 已收盘"
        urgency = "low"

    try:
        with db.get_session() as session:
            # 查询可卖出的持仓
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.status == 'holding',
                Position.can_sell_date <= today
            ).all()

            if not positions:
                return f"=== 早盘时间窗口检查 ===\n\n当前时间: {now.strftime('%H:%M:%S')}\n时间窗口: {window}\n{window_desc}\n\n当前无可卖出的持仓"

            # 获取实时行情
            stock_codes = [p.stock_code for p in positions]
            zhitu = ZhituAPI()
            prices_data = zhitu.get_real_time_multi_broker(stock_codes)

            results = []
            results.append("=== 早盘时间窗口检查（隔夜短线策略）===\n")
            results.append(f"当前时间: {now.strftime('%H:%M:%S')}")
            results.append(f"时间窗口: 【{window}】")
            results.append(f"{window_desc}\n")

            # 统计
            need_action_count = 0

            for position in positions:
                price_info = prices_data.get(position.stock_code, {})
                if not price_info:
                    continue

                current_price = float(price_info.get('current_price') or price_info.get('p', 0))
                open_price = float(price_info.get('open_price') or price_info.get('o', current_price))
                prev_close = float(price_info.get('prev_close') or price_info.get('pc', 0))
                high_price = float(price_info.get('high_price') or price_info.get('h', current_price))
                buy_price = float(position.buy_price)

                if current_price == 0 or buy_price == 0:
                    continue

                # 计算关键指标
                profit_pct = ((current_price - buy_price) / buy_price) * 100
                today_change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                pullback_from_high_pct = ((high_price - current_price) / high_price) * 100 if high_price > 0 else 0

                # 根据时间窗口给出建议
                if window == "黄金15分钟":
                    if pullback_from_high_pct > 1.5 and profit_pct > 0:
                        action = "🔴 冲高回落，建议立即止盈"
                        need_action_count += 1
                    elif profit_pct >= 3:
                        action = "🟢 盈利良好，关注冲高回落"
                    else:
                        action = "🟡 观察走势"

                elif window == "趋势确认期":
                    if profit_pct < 1 and today_change_pct < 1:
                        action = "🟠 涨幅不及预期，考虑减仓50%"
                        need_action_count += 1
                    elif pullback_from_high_pct > 2:
                        action = "🔴 明显回落，建议止盈"
                        need_action_count += 1
                    else:
                        action = "🟢 走势正常"

                elif window == "最后窗口":
                    if profit_pct < 0:
                        action = "🔴 亏损状态，建议止损清仓"
                        need_action_count += 1
                    elif profit_pct < 2:
                        action = "🟠 盈利微薄，建议清仓"
                        need_action_count += 1
                    else:
                        action = "🟡 还有盈利，可持有观察"

                elif window == "上午尾盘":
                    action = "⚠️ 已过最佳卖点，谨慎持有"
                    if profit_pct < 0:
                        need_action_count += 1

                else:
                    action = "⏰ 等待开盘"

                results.append(f"【{position.stock_name}({position.stock_code})】")
                results.append(f"  当前价: ¥{current_price:.2f} | 今日涨跌: {today_change_pct:+.2f}%")
                results.append(f"  持仓盈亏: {profit_pct:+.2f}% | 从最高回落: {pullback_from_high_pct:.2f}%")
                results.append(f"  ➡️ {action}")
                results.append("")

            # 汇总建议
            results.append("--- 汇总 ---")
            results.append(f"持仓数量: {len(positions)}只")
            results.append(f"需要操作: {need_action_count}只")

            if urgency == "critical" and need_action_count > 0:
                results.append("\n🚨 紧急提醒：已到最后窗口，请立即处理需要操作的股票！")
            elif urgency == "high" and need_action_count > 0:
                results.append("\n⚠️ 提醒：黄金时间窗口，请关注需要操作的股票！")

            return "\n".join(results)

    except Exception as e:
        logger.error(f"❌ 检查早盘时间窗口失败: {e}")
        return f"检查早盘时间窗口失败: {str(e)}"
