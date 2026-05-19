"""
推荐API
提供最新AI推荐股票查询功能
"""

from flask import Blueprint, jsonify, session as flask_session
from datetime import date
from decimal import Decimal
from src.database.db_manager import get_db
from src.database.models import Candidate
from src.tools.zhitu_api import ZhituAPI

recommendation_api = Blueprint('recommendation_api', __name__)

# 初始化智兔API
zhitu = ZhituAPI()


@recommendation_api.route('/api/recommendations/latest', methods=['GET'])
def get_latest_recommendations():
    """
    获取最近N天的AI推荐（包括已过期的推荐）

    推荐状态判断规则：
    1. track1_tail（尾盘赛道）：推荐当天收盘前有效，次日显示"已过期"
    2. track2_next（次日赛道）：推荐后次日开盘前有效，开盘后显示"已过期"
    3. 无赛道标识：默认当天有效，次日显示"已过期"

    显示最近3天的推荐，让用户可以：
    - 回顾历史推荐
    - 验证推荐效果
    - 学习AI逻辑

    Returns:
        {
            "success": true,
            "data": {
                "recommendations": [...]
            }
        }
    """
    db = get_db()

    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        with db.get_session() as session:
            from datetime import datetime, timedelta
            from src.utils.trading_calendar import is_trading_day

            now = datetime.now()
            today = date.today()

            # 查询最近7天的候选股票（修改：3天 → 7天）
            seven_days_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())

            # ✅ 添加session_id过滤，并按股票代码去重，只保留最新的一条
            from sqlalchemy import func

            # 子查询：获取每只股票的最新推荐时间
            subquery = session.query(
                Candidate.stock_code,
                func.max(Candidate.recommend_time).label('max_time')
            ).filter(
                Candidate.session_id == user_session_id,
                Candidate.recommend_time >= seven_days_ago
            ).group_by(Candidate.stock_code).subquery()

            # 主查询：根据股票代码和最新推荐时间，获取完整记录
            all_candidates = session.query(Candidate).join(
                subquery,
                (Candidate.stock_code == subquery.c.stock_code) &
                (Candidate.recommend_time == subquery.c.max_time)
            ).filter(
                Candidate.session_id == user_session_id
            ).order_by(
                Candidate.recommend_time.desc(),
                Candidate.final_score.desc()
            ).all()

            # ✅ 过滤非交易日的推荐
            candidates = []
            for cand in all_candidates:
                recommend_date = cand.recommend_time.date()
                if is_trading_day(recommend_date):
                    candidates.append(cand)
                    if len(candidates) >= 30:  # 最多返回30条
                        break

            # 批量获取实时价格
            stock_codes = [cand.stock_code for cand in candidates]
            prices_dict = {}

            if stock_codes:
                try:
                    print(f"🔍 准备批量获取实时价格，股票代码: {stock_codes}")
                    # 使用券商数据源批量获取实时价格
                    prices_data = zhitu.get_real_time_multi_broker(stock_codes)
                    print(f"📊 API返回数据: {prices_data}")
                    if prices_data:
                        for stock_code, price_info in prices_data.items():
                            print(f"🔍 处理股票 {stock_code}, 数据: {price_info}")
                            if price_info and 'current_price' in price_info:
                                prices_dict[stock_code] = {
                                    'current_price': float(price_info['current_price']),
                                    'change_pct': float(price_info.get('change_pct', 0))  # 涨跌幅
                                }
                                print(f"✅ 股票 {stock_code} 价格数据已添加: {prices_dict[stock_code]}")
                            else:
                                print(f"❌ 股票 {stock_code} 数据中没有current_price字段")
                    print(f"📊 最终价格字典: {prices_dict}")
                except Exception as e:
                    print(f"批量获取实时价格失败: {e}")
                    import traceback
                    traceback.print_exc()

            result = []
            for cand in candidates:
                # 获取当前价和涨幅
                price_info = prices_dict.get(cand.stock_code, {})
                current_price = price_info.get('current_price')
                change_pct = price_info.get('change_pct')

                result.append({
                    "id": cand.id,
                    "stock_code": cand.stock_code,
                    "stock_name": cand.stock_name,
                    "recommend_price": round(float(cand.recommend_price), 3) if cand.recommend_price else 0,  # ✅ 保留3位小数
                    "current_price": round(current_price, 3) if current_price else None,  # ✅ 保留3位小数
                    "change_pct": change_pct,  # 涨跌幅
                    "strategy": cand.strategy_name or "未知策略",  # ✅ 直接显示策略名称
                    "final_score": float(cand.final_score) if cand.final_score else 0,
                    "reason": cand.ceo_reason or "AI综合分析推荐",
                    "target_price": round(float(cand.target_price), 3) if cand.target_price else None,  # ✅ 保留3位小数
                    "stop_loss": None,
                    "recommend_date": cand.recommend_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "recommend_track": cand.recommend_track or "未知赛道"
                })

            return jsonify({
                "success": True,
                "data": {
                    "recommendations": result
                }
            })

    except Exception as e:
        print(f"获取推荐失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"获取推荐失败: {str(e)}"
        }), 500

