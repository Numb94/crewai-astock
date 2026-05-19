"""
绩效对比API
提供推荐胜率 vs 交易胜率的对比分析
"""

from flask import Blueprint, jsonify, request, session as flask_session
from datetime import date, datetime, timedelta
from decimal import Decimal
from src.database.db_manager import get_db
from src.database.models import Candidate, Position, Transaction
from src.tools.zhitu_api import ZhituAPI
from sqlalchemy import func
import json

performance_api = Blueprint('performance_api', __name__)


@performance_api.route('/api/performance/comparison', methods=['GET'])
def get_performance_comparison():
    """
    获取推荐胜率 vs 交易胜率对比分析

    Query Parameters:
        days: 统计最近N天，默认0（全部历史）
              - 0: 全部历史
              - N: 最近N天

    Returns:
        {
            "success": true,
            "data": {
                "recommendation": {
                    "total_count": 50,
                    "win_count": 35,
                    "win_rate": 70.0,
                    "avg_return": 2.35,
                    "by_strategy": [...]
                },
                "trading": {
                    "total_count": 30,
                    "win_count": 18,
                    "win_rate": 60.0,
                    "avg_return": 1.8
                },
                "diagnosis": "推荐胜率高但交易胜率低，建议优化买入时机"
            }
        }
    """
    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        days = int(request.args.get('days', 0))  # 默认0=全部历史

        # ✅ 计算推荐胜率（传递session_id）
        recommendation_stats = calculate_recommendation_win_rate(days, user_session_id)

        # ✅ 计算交易胜率（传递session_id）
        trading_stats = calculate_trading_win_rate(days, user_session_id)

        # 生成诊断
        diagnosis = generate_diagnosis(recommendation_stats, trading_stats)

        return jsonify({
            "success": True,
            "data": {
                "recommendation": recommendation_stats,
                "trading": trading_stats,
                "diagnosis": diagnosis,
                "period_days": days
            }
        })

    except Exception as e:
        print(f"获取绩效对比失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"获取绩效对比失败: {str(e)}"
        }), 500


@performance_api.route('/api/performance/multi-period', methods=['GET'])
def get_multi_period_performance():
    """
    获取多时间维度回测统计（周/月/年/全部）

    按自然周期划分：
    - 本周：本周一 ~ 今天
    - 本月：本月1日 ~ 今天
    - 本年：今年1月1日 ~ 今天
    - 全部：所有历史数据

    Returns:
        {
            "success": true,
            "data": {
                "week": { "recommendation": {...}, "trading": {...}, "diagnosis": "..." },
                "month": { "recommendation": {...}, "trading": {...}, "diagnosis": "..." },
                "year": { "recommendation": {...}, "trading": {...}, "diagnosis": "..." },
                "all": { "recommendation": {...}, "trading": {...}, "diagnosis": "..." }
            }
        }
    """
    try:
        user_session_id = flask_session.get('user_session_id', 'default')
        today = date.today()

        # 计算自然周期的起始日期
        # 本周一（weekday(): 周一=0, 周日=6）
        week_start = today - timedelta(days=today.weekday())
        # 本月1日
        month_start = today.replace(day=1)
        # 本年1月1日
        year_start = today.replace(month=1, day=1)

        # 定义时间维度及其起始日期
        periods = {
            "week": week_start,
            "month": month_start,
            "year": year_start,
            "all": None  # None表示全部历史
        }

        result = {}
        for period_name, start_date in periods.items():
            recommendation_stats = calculate_recommendation_win_rate_by_date(start_date, today, user_session_id)
            trading_stats = calculate_trading_win_rate_by_date(start_date, today, user_session_id)
            diagnosis = generate_diagnosis(recommendation_stats, trading_stats)

            result[period_name] = {
                "recommendation": recommendation_stats,
                "trading": trading_stats,
                "diagnosis": diagnosis,
                "period_start": start_date.strftime('%Y-%m-%d') if start_date else None,
                "period_end": today.strftime('%Y-%m-%d'),
                "period_label": _get_period_label(period_name)
            }

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        print(f"获取多维度绩效对比失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"获取多维度绩效对比失败: {str(e)}"
        }), 500


def _get_period_label(period_name: str) -> str:
    """获取时间维度的中文标签"""
    labels = {
        "week": "本周",
        "month": "本月",
        "year": "本年",
        "all": "全部"
    }
    return labels.get(period_name, period_name)


def calculate_recommendation_win_rate_by_date(start_date, end_date, session_id: str = 'default'):
    """
    按日期范围计算推荐胜率

    Args:
        start_date: 起始日期，None表示全部历史
        end_date: 结束日期
        session_id: 用户session_id
    """
    db = get_db()
    zhitu = ZhituAPI()

    with db.get_session() as session:
        from src.utils.trading_calendar import is_trading_day

        # 查询推荐记录
        if start_date is None:
            # 全部历史
            all_candidates = session.query(Candidate).filter(
                Candidate.session_id == session_id
            ).all()
        else:
            # 指定日期范围
            all_candidates = session.query(Candidate).filter(
                Candidate.session_id == session_id,
                func.date(Candidate.recommend_time) >= start_date,
                func.date(Candidate.recommend_time) <= end_date
            ).all()

        # 过滤非交易日的推荐
        candidates = []
        for cand in all_candidates:
            recommend_date = cand.recommend_time.date()
            if is_trading_day(recommend_date):
                candidates.append(cand)

        if not candidates:
            return {
                "total_count": 0,
                "win_count": 0,
                "win_rate": 0,
                "avg_return": 0,
                "by_strategy": [],
                "by_date": []
            }

        # 统计数据 - 按日期分组
        daily_returns = {}  # {date: [change_pct1, change_pct2, ...]}
        daily_stocks = {}   # {date: [{code, name, strategy, change_pct}, ...]}
        strategy_stats = {}

        for candidate in candidates:
            recommend_date = candidate.recommend_time.date()

            # 跳过今天的推荐（至少需要1天时间验证）
            if recommend_date >= date.today():
                continue

            recommend_price = candidate.recommend_price
            if not recommend_price or recommend_price == 0:
                continue

            try:
                # 简化逻辑：推荐价 → T+1收盘价
                stock_symbol = f"{candidate.stock_code}.{'SH' if candidate.stock_code.startswith('6') else 'SZ'}"
                t1_close = None

                # 查找T+1收盘价（跳过周末/节假日）
                for days_offset in range(1, 8):
                    check_date = recommend_date + timedelta(days=days_offset)
                    if check_date > date.today():
                        break

                    if check_date == date.today():
                        # T+1是今天，使用实时价格
                        try:
                            current_data = zhitu.get_real_time_broker(candidate.stock_code)
                            if current_data and 'current_price' in current_data:
                                t1_close = Decimal(str(current_data['current_price']))
                                break
                        except Exception:
                            continue
                    else:
                        # 历史日期，使用收盘价
                        try:
                            history_data = zhitu.get_history_timeframe(
                                stock_symbol=stock_symbol,
                                timeframe='d',
                                adjust_type='n',
                                start_time=check_date.strftime('%Y%m%d'),
                                end_time=check_date.strftime('%Y%m%d')
                            )
                            if history_data and len(history_data) > 0:
                                close_price = Decimal(str(history_data[0].get('c', 0)))
                                if close_price > 0:
                                    t1_close = close_price
                                    break
                        except Exception:
                            continue

                if t1_close is None:
                    continue

                change_pct = float((t1_close - recommend_price) / recommend_price * 100)

                # 按日期分组收集收益率
                if recommend_date not in daily_returns:
                    daily_returns[recommend_date] = []
                daily_returns[recommend_date].append(change_pct)

                # 按日期分组收集股票信息
                strategy = candidate.strategy_name or "未知策略"
                if recommend_date not in daily_stocks:
                    daily_stocks[recommend_date] = []
                daily_stocks[recommend_date].append({
                    "code": candidate.stock_code,
                    "name": candidate.stock_name,
                    "strategy": strategy,
                    "change_pct": round(change_pct, 2)
                })

                # 按策略分组统计
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        "count": 0,
                        "win_count": 0,
                        "total_return": 0,
                        "stocks": []
                    }

                strategy_stats[strategy]["count"] += 1
                strategy_stats[strategy]["total_return"] += change_pct
                if change_pct > 0:
                    strategy_stats[strategy]["win_count"] += 1

                strategy_stats[strategy]["stocks"].append({
                    "code": candidate.stock_code,
                    "name": candidate.stock_name,
                    "change_pct": round(change_pct, 2),
                    "recommend_date": recommend_date.strftime('%Y-%m-%d')
                })

            except Exception as e:
                print(f"处理推荐记录失败 {candidate.stock_code}: {e}")
                continue

        # 按日期计算累计收益和胜率
        total_days = len(daily_returns)
        win_days = 0
        cumulative_return = 0
        total_stock_count = 0
        total_win_count = 0

        for date_key, returns in daily_returns.items():
            daily_avg = sum(returns) / len(returns)
            cumulative_return += daily_avg
            total_stock_count += len(returns)
            total_win_count += sum(1 for r in returns if r > 0)
            if daily_avg > 0:
                win_days += 1

        # 胜率 = 盈利天数 / 总天数
        win_rate = (win_days / total_days * 100) if total_days > 0 else 0
        # 累计收益 = 每日平均收益之和
        avg_return = cumulative_return

        # 整理策略统计
        by_strategy = []
        for strategy, stats in strategy_stats.items():
            by_strategy.append({
                "strategy": strategy,
                "count": stats["count"],
                "win_count": stats["win_count"],
                "win_rate": round((stats["win_count"] / stats["count"] * 100) if stats["count"] > 0 else 0, 2),
                "avg_return": round((stats["total_return"] / stats["count"]) if stats["count"] > 0 else 0, 2),
                "stocks": stats["stocks"]
            })

        by_strategy.sort(key=lambda x: x["win_rate"], reverse=True)

        # 整理按日期分组的数据
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        by_date = []
        for date_key in sorted(daily_stocks.keys(), reverse=True):  # 按日期倒序（最新在前）
            stocks = daily_stocks[date_key]
            returns = daily_returns.get(date_key, [])
            win_count = sum(1 for r in returns if r > 0)
            total_return = sum(returns)
            avg_return_day = total_return / len(returns) if returns else 0

            by_date.append({
                "date": date_key.strftime('%Y-%m-%d'),
                "weekday": weekday_names[date_key.weekday()],
                "count": len(stocks),
                "win_count": win_count,
                "win_rate": round((win_count / len(stocks) * 100) if stocks else 0, 1),
                "avg_return": round(avg_return_day, 2),
                "stocks": stocks
            })

        return {
            "total_count": total_stock_count,  # 总股票数
            "win_count": total_win_count,      # 盈利股票数
            "total_days": total_days,          # 总交易天数
            "win_days": win_days,              # 盈利天数
            "win_rate": round(win_rate, 2),    # 按天胜率
            "avg_return": round(avg_return, 2),  # 累计收益
            "by_strategy": by_strategy,
            "by_date": by_date
        }


def calculate_trading_win_rate_by_date(start_date, end_date, session_id: str = 'default'):
    """
    按日期范围计算交易胜率

    Args:
        start_date: 起始日期，None表示全部历史
        end_date: 结束日期
        session_id: 用户session_id
    """
    db = get_db()
    zhitu = ZhituAPI()

    with db.get_session() as session:
        # 查询持仓记录
        if start_date is None:
            positions = session.query(Position).filter(
                Position.session_id == session_id
            ).all()
        else:
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.buy_date >= start_date,
                Position.buy_date <= end_date
            ).all()

        if not positions:
            return {
                "total_count": 0,
                "win_count": 0,
                "win_rate": 0,
                "avg_return": 0
            }

        # 统计数据 - 按买入日期分组
        daily_returns = {}  # {buy_date: [change_pct1, change_pct2, ...]}

        for position in positions:
            buy_price = position.buy_price
            buy_date = position.buy_date
            if not buy_price or buy_price == 0:
                continue

            try:
                change_pct = None

                if position.status == 'sold' and position.sell_price:
                    sell_price = position.sell_price
                    change_pct = float((sell_price - buy_price) / buy_price * 100)

                elif position.status == 'holding':
                    current_data = zhitu.get_real_time_broker(position.stock_code)
                    if not current_data or 'current_price' not in current_data:
                        continue
                    current_price = Decimal(str(current_data['current_price']))
                    change_pct = float((current_price - buy_price) / buy_price * 100)

                if change_pct is not None:
                    # 按买入日期分组收集收益��
                    if buy_date not in daily_returns:
                        daily_returns[buy_date] = []
                    daily_returns[buy_date].append(change_pct)

            except Exception as e:
                print(f"处理持仓记录失败 {position.stock_code}: {e}")
                continue

        # 按日期计算累计收益和胜率
        total_days = len(daily_returns)
        win_days = 0
        cumulative_return = 0
        total_stock_count = 0
        total_win_count = 0

        for date_key, returns in daily_returns.items():
            daily_avg = sum(returns) / len(returns)
            cumulative_return += daily_avg
            total_stock_count += len(returns)
            total_win_count += sum(1 for r in returns if r > 0)
            if daily_avg > 0:
                win_days += 1

        # 胜率 = 盈利天数 / 总天数
        win_rate = (win_days / total_days * 100) if total_days > 0 else 0
        # 累计收益 = 每日平均收益之和
        avg_return = cumulative_return

        return {
            "total_count": total_stock_count,  # 总股票数
            "win_count": total_win_count,      # 盈利股票数
            "total_days": total_days,          # 总交易天数
            "win_days": win_days,              # 盈利天数
            "win_rate": round(win_rate, 2),    # 按天胜率
            "avg_return": round(avg_return, 2)  # 累计收益
        }


def calculate_recommendation_win_rate(days: int = 0, session_id: str = 'default'):
    """
    计算推荐胜率（所有推荐的股票，不管是否买入）

    Args:
        days: 统计最近N天，0=全部历史
        session_id: 用户session_id

    Returns:
        {
            "total_count": 50,
            "win_count": 35,
            "win_rate": 70.0,
            "avg_return": 2.35,
            "by_strategy": [...]
        }
    """
    db = get_db()
    zhitu = ZhituAPI()

    with db.get_session() as session:
        from src.utils.trading_calendar import is_trading_day

        # 计算日期范围
        end_date = date.today()

        # ✅ 查询推荐记录（添加session_id过滤）
        if days == 0:
            # 全部历史
            all_candidates = session.query(Candidate).filter(
                Candidate.session_id == session_id
            ).all()
        else:
            # 最近N天
            start_date = end_date - timedelta(days=days)
            all_candidates = session.query(Candidate).filter(
                Candidate.session_id == session_id,
                func.date(Candidate.recommend_time) >= start_date,
                func.date(Candidate.recommend_time) < end_date
            ).all()

        # ✅ 过滤非交易日的推荐
        candidates = []
        for cand in all_candidates:
            recommend_date = cand.recommend_time.date()
            if is_trading_day(recommend_date):
                candidates.append(cand)

        if not candidates:
            return {
                "total_count": 0,
                "win_count": 0,
                "win_rate": 0,
                "avg_return": 0,
                "by_strategy": []
            }
        
        # 统计数据 - 按日期分组
        daily_returns = {}  # {date: [change_pct1, change_pct2, ...]}
        strategy_stats = {}

        for candidate in candidates:
            # ✅ 修复：使用T+1日收盘价或实际卖出价，而不是当前价格
            recommend_date = candidate.recommend_time.date()

            # 跳过今天的推荐（至少需要1天时间验证）
            if recommend_date >= date.today():
                continue

            recommend_price = candidate.recommend_price
            if not recommend_price or recommend_price == 0:
                continue

            try:
                # 🔴 修复：优先检查Position表，判断是否实际买入了推荐的股票
                # 1. 检查是否买入了这只股票（包括已卖出和持仓中的）
                position = session.query(Position).filter(
                    Position.session_id == session_id,
                    Position.stock_code == candidate.stock_code,
                    Position.buy_date >= recommend_date  # 推荐日期之后买入的
                ).order_by(Position.buy_date.asc()).first()

                if position:
                    # 1.1 如果买入了且已卖出，使用实际卖出价
                    if position.status == 'sold' and position.sell_price:
                        sell_price = position.sell_price
                        change_pct = float((sell_price - recommend_price) / recommend_price * 100)

                    # 1.2 如果买入了且还持有，使用当前价格
                    elif position.status == 'holding':
                        try:
                            current_data = zhitu.get_real_time_broker(candidate.stock_code)
                            if current_data and 'current_price' in current_data:
                                current_price = Decimal(str(current_data['current_price']))
                                change_pct = float((current_price - recommend_price) / recommend_price * 100)
                            else:
                                # 获取实时价格失败，跳过
                                continue
                        except Exception as e:
                            # 获取实时价格失败，跳过
                            continue

                    # 🔴 修复：如果是已卖出但sell_price为None，尝试使用卖出日收盘价
                    elif position.status == 'sold' and not position.sell_price:
                        try:
                            # 尝试获取卖出日的收盘价
                            if position.sell_date:
                                # 🔴 新增：如果卖出日期是今天，使用实时价格
                                if position.sell_date == date.today():
                                    current_data = zhitu.get_real_time_broker(candidate.stock_code)
                                    if current_data and 'current_price' in current_data:
                                        current_price = Decimal(str(current_data['current_price']))
                                        change_pct = float((current_price - recommend_price) / recommend_price * 100)
                                        print(f"[INFO] {candidate.stock_code} ({candidate.stock_name}) sold today without sell_price, using real-time price {current_price}, recommend_price {recommend_price}, change_pct {change_pct:.2f}%")
                                    else:
                                        # 获取实时价格失败，跳过
                                        print(f"[WARN] {candidate.stock_code} ({candidate.stock_name}) failed to get real-time price")
                                        continue
                                else:
                                    # 历史日期，使用收盘价
                                    stock_symbol = f"{candidate.stock_code}.{'SH' if candidate.stock_code.startswith('6') else 'SZ'}"

                                    history_data = zhitu.get_history_timeframe(
                                        stock_symbol=stock_symbol,
                                        timeframe='d',
                                        adjust_type='n',
                                        start_time=position.sell_date.strftime('%Y%m%d'),
                                        end_time=position.sell_date.strftime('%Y%m%d')
                                    )

                                    if history_data and len(history_data) > 0:
                                        close_price = Decimal(str(history_data[0].get('c', 0)))
                                        if close_price > 0:
                                            change_pct = float((close_price - recommend_price) / recommend_price * 100)
                                            print(f"[INFO] {candidate.stock_code} sold without sell_price, using close price {close_price} on {position.sell_date}")
                                        else:
                                            # 收盘价获取失败，跳过
                                            continue
                                    else:
                                        # 没有数据，跳过
                                        continue
                            else:
                                # 没有卖出日期，跳过
                                continue
                        except Exception as e:
                            # 获取收盘价失败，跳过
                            print(f"[WARN] {candidate.stock_code} failed to get sell date close price: {e}")
                            continue

                    else:
                        # 其他状态，跳过
                        continue
                else:
                    # 2. 没有买入记录，使用T+1收盘价
                    # 从T+1开始，最多尝试7天，自动跳过周末和节假日
                    stock_symbol = f"{candidate.stock_code}.{'SH' if candidate.stock_code.startswith('6') else 'SZ'}"
                    next_day_close = None

                    for days_offset in range(1, 8):  # T+1 到 T+7
                        check_date = recommend_date + timedelta(days=days_offset)

                        # 如果检查日期超过今天，停止查找
                        if check_date > date.today():
                            break

                        try:
                            history_data = zhitu.get_history_timeframe(
                                stock_symbol=stock_symbol,
                                timeframe='d',
                                adjust_type='n',
                                start_time=check_date.strftime('%Y%m%d'),
                                end_time=check_date.strftime('%Y%m%d')
                            )

                            if history_data and len(history_data) > 0:
                                close_price = Decimal(str(history_data[0].get('c', 0)))
                                if close_price > 0:
                                    next_day_close = close_price
                                    break  # 找到第一个交易日，停止查找
                        except Exception as e:
                            # 继续尝试下一天
                            continue

                    if next_day_close is None:
                        # 7天内都没有找到交易日数据，跳过
                        continue

                    # 计算收益率（推荐价 → 下一个交易日收盘价）
                    change_pct = float((next_day_close - recommend_price) / recommend_price * 100)

                # 按日期分组收集��益率
                if recommend_date not in daily_returns:
                    daily_returns[recommend_date] = []
                daily_returns[recommend_date].append(change_pct)

                # 按策略分组统计
                strategy = candidate.strategy_name or "未知策略"
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        "count": 0,
                        "win_count": 0,
                        "total_return": 0,
                        "stocks": []  # ✅ 新增：股票列表
                    }

                strategy_stats[strategy]["count"] += 1
                strategy_stats[strategy]["total_return"] += change_pct
                if change_pct > 0:
                    strategy_stats[strategy]["win_count"] += 1

                # ✅ 新增：记录股票信息
                strategy_stats[strategy]["stocks"].append({
                    "code": candidate.stock_code,
                    "name": candidate.stock_name,
                    "change_pct": round(change_pct, 2),
                    "recommend_date": recommend_date.strftime('%Y-%m-%d')
                })

            except Exception as e:
                print(f"处理推荐记录失败 {candidate.stock_code}: {e}")
                import traceback
                traceback.print_exc()
                continue

        # 按日期计算累计收益和胜率
        total_days = len(daily_returns)
        win_days = 0
        cumulative_return = 0
        total_stock_count = 0
        total_win_count = 0

        for date, returns in daily_returns.items():
            daily_avg = sum(returns) / len(returns)
            cumulative_return += daily_avg
            total_stock_count += len(returns)
            total_win_count += sum(1 for r in returns if r > 0)
            if daily_avg > 0:
                win_days += 1

        # 胜率 = 盈利天数 / 总天数
        win_rate = (win_days / total_days * 100) if total_days > 0 else 0
        # 累计收益 = 每日平均收益之和
        avg_return = cumulative_return
        
        # 整理策略统计
        by_strategy = []
        for strategy, stats in strategy_stats.items():
            by_strategy.append({
                "strategy": strategy,
                "count": stats["count"],
                "win_count": stats["win_count"],
                "win_rate": round((stats["win_count"] / stats["count"] * 100) if stats["count"] > 0 else 0, 2),
                "avg_return": round((stats["total_return"] / stats["count"]) if stats["count"] > 0 else 0, 2),
                "stocks": stats["stocks"]  # ✅ 新增：股票列表
            })

        # 按胜率排序
        by_strategy.sort(key=lambda x: x["win_rate"], reverse=True)

        return {
            "total_count": total_stock_count,  # 总股票数
            "win_count": total_win_count,      # 盈利股票数
            "total_days": total_days,          # 总交易天数
            "win_days": win_days,              # 盈利天数
            "win_rate": round(win_rate, 2),    # 按天胜率
            "avg_return": round(avg_return, 2),  # 累计收益
            "by_strategy": by_strategy
        }


def calculate_trading_win_rate(days: int = 0, session_id: str = 'default'):
    """
    计算交易胜率（实际买入的股票）

    🔴 修改：从Position表统计，而不是Transaction表
    - 已卖出的持仓：使用sell_price计算收益率
    - 持仓中的股票：使用当前价格计算收益率

    Args:
        days: 统计最近N天，0=全部历史
        session_id: 用户session_id

    Returns:
        {
            "total_count": 30,
            "win_count": 18,
            "win_rate": 60.0,
            "avg_return": 1.8
        }
    """
    db = get_db()
    zhitu = ZhituAPI()

    with db.get_session() as session:
        # 计算日期范围
        end_date = date.today()

        # ✅ 查询持仓记录（添加session_id过滤）
        if days == 0:
            # 全部历史
            positions = session.query(Position).filter(
                Position.session_id == session_id
            ).all()
        else:
            # 最近N天
            start_date = end_date - timedelta(days=days)
            positions = session.query(Position).filter(
                Position.session_id == session_id,
                Position.buy_date >= start_date,
                Position.buy_date < end_date
            ).all()

        if not positions:
            return {
                "total_count": 0,
                "win_count": 0,
                "win_rate": 0,
                "avg_return": 0
            }

        # 统计数据 - 按买入日期分组
        daily_returns = {}  # {buy_date: [change_pct1, change_pct2, ...]}

        for position in positions:
            buy_price = position.buy_price
            buy_date = position.buy_date
            if not buy_price or buy_price == 0:
                continue

            try:
                change_pct = None

                # 1. 已卖出的持仓：使用sell_price
                if position.status == 'sold' and position.sell_price:
                    sell_price = position.sell_price
                    change_pct = float((sell_price - buy_price) / buy_price * 100)

                # 2. 持仓中的股票：使用当前价格
                elif position.status == 'holding':
                    current_data = zhitu.get_real_time_broker(position.stock_code)
                    if not current_data or 'current_price' not in current_data:
                        continue

                    current_price = Decimal(str(current_data['current_price']))
                    change_pct = float((current_price - buy_price) / buy_price * 100)

                if change_pct is not None:
                    # 按买入日期分组收集收益率
                    if buy_date not in daily_returns:
                        daily_returns[buy_date] = []
                    daily_returns[buy_date].append(change_pct)

            except Exception as e:
                print(f"处理持仓记录失败 {position.stock_code}: {e}")
                continue

        # 按日期计算累计收益和胜率
        total_days = len(daily_returns)
        win_days = 0
        cumulative_return = 0
        total_stock_count = 0
        total_win_count = 0

        for date_key, returns in daily_returns.items():
            daily_avg = sum(returns) / len(returns)
            cumulative_return += daily_avg
            total_stock_count += len(returns)
            total_win_count += sum(1 for r in returns if r > 0)
            if daily_avg > 0:
                win_days += 1

        # 胜率 = 盈利天数 / 总天数
        win_rate = (win_days / total_days * 100) if total_days > 0 else 0
        # 累计收益 = 每日平均收益之和
        avg_return = cumulative_return

        return {
            "total_count": total_stock_count,  # 总股票数
            "win_count": total_win_count,      # 盈利股票数
            "total_days": total_days,          # 总交易天数
            "win_days": win_days,              # 盈利天数
            "win_rate": round(win_rate, 2),    # 按天胜率
            "avg_return": round(avg_return, 2)  # 累计收益
        }


def generate_diagnosis(recommendation_stats, trading_stats):
    """
    生成诊断建议

    Args:
        recommendation_stats: 推荐胜率统计
        trading_stats: 交易胜率统计

    Returns:
        诊断文本
    """
    rec_win_rate = recommendation_stats.get("win_rate", 0)
    trade_win_rate = trading_stats.get("win_rate", 0)

    # 场景1：推荐胜率高，交易胜率低
    if rec_win_rate >= 60 and trade_win_rate < 50:
        return "推荐质量优秀，但交易执行较差。建议优化买入时机，避免追高。"

    # 场景2：推荐胜率低，交易胜率低
    elif rec_win_rate < 50 and trade_win_rate < 50:
        return "推荐质量需要改进。建议优化选股逻辑和市场环境适应性。"

    # 场景3：推荐胜率高，交易胜率高
    elif rec_win_rate >= 60 and trade_win_rate >= 60:
        return "推荐质量和交易执行都很优秀，继续保持！"

    # 场景4：推荐胜率低，交易胜率高
    elif rec_win_rate < 50 and trade_win_rate >= 60:
        return "交易执行优秀，但推荐样本可能不足。建议增加推荐数量。"

    # 场景5：推荐胜率中等，交易胜率中等
    elif 50 <= rec_win_rate < 60 and 50 <= trade_win_rate < 60:
        return "推荐质量和交易执行都处于中等水平，有提升空间。"

    # 场景6：推荐胜率中等，交易胜率低
    elif 50 <= rec_win_rate < 60 and trade_win_rate < 50:
        return "推荐质量尚可，但交易执行需要改进。建议优化买入时机。"

    # 场景7：推荐胜率高，交易胜率中等
    elif rec_win_rate >= 60 and 50 <= trade_win_rate < 60:
        return "推荐质量优秀，交易执行良好，可进一步优化买入时机。"

    # 默认
    else:
        return "数据样本不足，建议继续观察。"

