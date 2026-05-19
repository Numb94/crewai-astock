#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
推荐绩效分析工具

分析推荐股票的表现（不管是否买入），评估推荐质量
"""

from crewai.tools import tool
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


@tool("分析推荐股票表现")
def analyze_recommendation_performance(days: int = 1) -> str:
    """
    分析最近N天推荐的股票表现（不管是否买入）

    Args:
        days: 分析最近N天，默认1天（昨日）
              🔴 新增：如果days=0，分析今日推荐
              🔴 新增：如果days=-1，分析最近一个交易日（自动跳过周末）

    Returns:
        推荐股票表现分析（自然语言描述）
    """
    from src.database.db_manager import get_db
    from src.database.models import Candidate
    from src.tools.zhitu_api import ZhituAPI
    from sqlalchemy import func

    # 🔴 导入session_id获取函数
    from src.agents.tools.database_tools import get_current_session_id

    try:
        db = get_db()
        zhitu = ZhituAPI()
        # 🔴 获取当前用户的session_id
        session_id = get_current_session_id()

        # 🔴 新增：支持days=0，分析今日推荐
        if days == 0:
            # 今日推荐：start_date = today, end_date = tomorrow
            start_date = date.today()
            end_date = date.today() + timedelta(days=1)
            time_desc = "今日"
        elif days == -1:
            # ✅ 新增：分析最近一个交易日（自动跳过周末）
            end_date = date.today()
            # 向前查找最多7天，找到有推荐记录的最近一天
            with db.get_session() as session:
                for i in range(1, 8):
                    check_date = end_date - timedelta(days=i)
                    count = session.query(Candidate).filter(
                        Candidate.session_id == session_id,
                        func.date(Candidate.recommend_time) == check_date
                    ).count()
                    if count > 0:
                        start_date = check_date
                        end_date = check_date + timedelta(days=1)
                        time_desc = f"最近一个交易日({check_date.strftime('%Y-%m-%d')})"
                        break
                else:
                    return "最近7天没有推荐股票"
        else:
            # 历史推荐：end_date = today, start_date = today - days
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            time_desc = f"最近{days}天"

        with db.get_session() as session:
            # 🔴 查询当前用户最近N天的推荐股票（添加session_id过滤）
            candidates = session.query(Candidate).filter(
                Candidate.session_id == session_id,
                func.date(Candidate.recommend_time) >= start_date,
                func.date(Candidate.recommend_time) < end_date
            ).all()

            if not candidates:
                return f"{time_desc}没有推荐股票"
            
            # 分析每只股票的表现
            results = []
            win_count = 0
            total_return = 0
            
            for candidate in candidates:
                # 获取推荐日期
                recommend_date = candidate.recommend_time.date()
                recommend_price = float(candidate.recommend_price or 0)

                if recommend_price == 0:
                    continue

                # 🔴 新增：区分今日推荐和历史推荐
                if days == 0:
                    # 今日推荐：使用实时价格
                    try:
                        realtime_data = zhitu.get_real_time_broker(candidate.stock_code)
                        if not realtime_data or 'current_price' not in realtime_data:
                            continue

                        current_price = float(realtime_data['current_price'])

                        if current_price > 0:
                            # 计算涨跌幅
                            change_pct = ((current_price - recommend_price) / recommend_price) * 100

                            results.append({
                                'stock_code': candidate.stock_code,
                                'stock_name': candidate.stock_name,
                                'recommend_price': recommend_price,
                                'current_price': current_price,
                                'change_pct': change_pct,
                                'strategy': candidate.strategy_name
                            })

                            if change_pct > 0:
                                win_count += 1

                            total_return += change_pct

                    except Exception as e:
                        logger.warning(f"获取{candidate.stock_code}实时数据失败: {e}")
                        continue
                else:
                    # 历史推荐：使用T+1收盘价（下一个交易日）
                    next_day = recommend_date + timedelta(days=1)

                    # ✅ 修复：如果T+1是今天，使用实时价格
                    if next_day == date.today():
                        try:
                            realtime_data = zhitu.get_real_time_broker(candidate.stock_code)
                            if not realtime_data or 'current_price' not in realtime_data:
                                continue

                            current_price = float(realtime_data['current_price'])

                            if current_price > 0:
                                # 计算涨跌幅
                                change_pct = ((current_price - recommend_price) / recommend_price) * 100

                                results.append({
                                    'stock_code': candidate.stock_code,
                                    'stock_name': candidate.stock_name,
                                    'recommend_price': recommend_price,
                                    'current_price': current_price,
                                    'change_pct': change_pct,
                                    'strategy': candidate.strategy_name,
                                    'is_today': True  # 标记为今日数据
                                })

                                if change_pct > 0:
                                    win_count += 1

                                total_return += change_pct

                        except Exception as e:
                            logger.warning(f"获取{candidate.stock_code}实时数据失败: {e}")
                            continue
                    # 跳过未来日期
                    elif next_day > date.today():
                        continue
                    else:
                        # 获取历史数据
                        try:
                            # ✅ 修复：获取推荐日期之后的所有数据（最多7天），然后取第一个交易日
                            # 这样可以自动跳过周末和节假日
                            history_data = zhitu.get_history_timeframe(
                                stock_symbol=f"{candidate.stock_code}.{'SH' if candidate.stock_code.startswith('6') else 'SZ'}",
                                timeframe='d',
                                adjust_type='n',
                                start_time=next_day.strftime('%Y%m%d'),
                                end_time=(next_day + timedelta(days=7)).strftime('%Y%m%d')
                            )

                            if history_data and len(history_data) > 0:
                                # 取第一个交易日的收盘价（自动跳过周末/节假日）
                                next_day_close = float(history_data[0].get('c', 0))

                                if next_day_close > 0:
                                    # 计算涨跌幅
                                    change_pct = ((next_day_close - recommend_price) / recommend_price) * 100

                                    results.append({
                                        'stock_code': candidate.stock_code,
                                        'stock_name': candidate.stock_name,
                                        'recommend_price': recommend_price,
                                        'next_day_close': next_day_close,
                                        'change_pct': change_pct,
                                        'strategy': candidate.strategy_name
                                    })

                                    if change_pct > 0:
                                        win_count += 1

                                    total_return += change_pct

                        except Exception as e:
                            logger.warning(f"获取{candidate.stock_code}历史数据失败: {e}")
                            continue
            
            if not results:
                return f"{time_desc}推荐的股票暂无可分析数据"
            
            # 计算统计数据
            total_count = len(results)
            recommendation_win_rate = (win_count / total_count) * 100 if total_count > 0 else 0
            avg_return = total_return / total_count if total_count > 0 else 0
            
            # 按策略分组统计
            strategy_stats = {}
            for r in results:
                strategy = r['strategy'] or '未知策略'
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        'count': 0,
                        'win_count': 0,
                        'total_return': 0
                    }
                
                strategy_stats[strategy]['count'] += 1
                if r['change_pct'] > 0:
                    strategy_stats[strategy]['win_count'] += 1
                strategy_stats[strategy]['total_return'] += r['change_pct']
            
            # 格式化输出
            output = [
                f"=== {time_desc}推荐股票表现分析 ===",
                "",
                f"推荐总数: {total_count}只",
                f"推荐胜率: {recommendation_win_rate:.2f}% ({win_count}胜/{total_count-win_count}负)",
                f"平均收益: {avg_return:+.2f}%",
                "",
                "【策略表现】"
            ]
            
            for strategy, stats in strategy_stats.items():
                win_rate = (stats['win_count'] / stats['count']) * 100 if stats['count'] > 0 else 0
                avg_ret = stats['total_return'] / stats['count'] if stats['count'] > 0 else 0
                output.append(f"- {strategy}: 胜率{win_rate:.0f}% ({stats['win_count']}/{stats['count']}), 平均收益{avg_ret:+.2f}%")
            
            output.append("")
            output.append("【推荐明细】")

            # 按收益排序
            results_sorted = sorted(results, key=lambda x: x['change_pct'], reverse=True)

            for r in results_sorted[:10]:  # 只显示前10只
                status = "✅" if r['change_pct'] > 0 else "❌"

                # 🔴 修复：区分今日推荐和历史推荐的输出格式
                if 'current_price' in r:
                    # 今日推荐或T+1是今天：使用当前价格
                    time_label = "当前价" if r.get('is_today') else "当前价"
                    output.append(
                        f"{status} {r['stock_name']}({r['stock_code']}): "
                        f"推荐价{r['recommend_price']:.2f}元 → {time_label}{r['current_price']:.2f}元 "
                        f"({r['change_pct']:+.2f}%) [{r['strategy']}]"
                    )
                else:
                    # 历史推荐：使用次日收盘价
                    output.append(
                        f"{status} {r['stock_name']}({r['stock_code']}): "
                        f"推荐价{r['recommend_price']:.2f}元 → 次日收盘{r['next_day_close']:.2f}元 "
                        f"({r['change_pct']:+.2f}%) [{r['strategy']}]"
                    )

            if len(results) > 10:
                output.append(f"... 还有{len(results)-10}只股票")

            return "\n".join(output)
    
    except Exception as e:
        logger.error(f"分析推荐股票表现失败: {e}")
        return f"分析推荐股票表现失败: {str(e)}"

