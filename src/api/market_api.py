"""
市场情绪API
提供市场状态、情绪评分、涨跌停数据、热点题材等
"""

from flask import Blueprint, jsonify, session as flask_session
from datetime import date
from src.database.db_manager import get_db
from src.database.models import MarketSentiment
from src.tools.zhitu_api import ZhituAPI

market_api = Blueprint('market_api', __name__)


@market_api.route('/api/market/sentiment', methods=['GET'])
def get_market_sentiment():
    """
    获取市场情绪数据
    
    Returns:
        {
            "success": true,
            "data": {
                "market_state": "hot",
                "sentiment_score": 85,
                "limit_up_count": 120,
                "limit_down_count": 5,
                "gain_count": 3200,
                "loss_count": 1800,
                "hot_topics": [
                    {"name": "AI", "count": 15},
                    {"name": "新能源", "count": 12}
                ]
            }
        }
    """
    db = get_db()
    
    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        with db.get_session() as session:
            # ✅ 查询今日市场情绪（添加session_id过滤）
            today = date.today()
            sentiment = session.query(MarketSentiment).filter(
                MarketSentiment.session_id == user_session_id,
                MarketSentiment.sentiment_date == today
            ).first()
            
            # 如果没有今日数据，尝试获取实时数据
            if not sentiment:
                zhitu = ZhituAPI()
                
                # 获取涨停股池
                limit_up_stocks = zhitu.get_limit_up_pool(today.strftime('%Y-%m-%d'))
                limit_up_count = len(limit_up_stocks) if limit_up_stocks else 0
                
                # 获取跌停股池
                limit_down_stocks = zhitu.get_limit_down_pool(today.strftime('%Y-%m-%d'))
                limit_down_count = len(limit_down_stocks) if limit_down_stocks else 0
                
                # 计算市场状态
                if limit_up_count > 100:
                    market_state = "hot"
                    sentiment_score = 90
                elif limit_up_count > 50:
                    market_state = "warm"
                    sentiment_score = 70
                elif limit_up_count > 20:
                    market_state = "neutral"
                    sentiment_score = 50
                elif limit_up_count > 0:
                    market_state = "cold"
                    sentiment_score = 30
                else:
                    market_state = "panic"
                    sentiment_score = 10
                
                # 提取热点题材（从涨停股中统计）
                hot_topics = []
                if limit_up_stocks:
                    # 简单统计：按行业分类
                    industry_count = {}
                    for stock in limit_up_stocks[:20]:  # 只取前20只
                        industry = stock.get('hy', '其他')
                        if industry and industry != '--':
                            industry_count[industry] = industry_count.get(industry, 0) + 1
                    
                    # 转换为列表格式
                    hot_topics = [
                        {"name": industry, "count": count}
                        for industry, count in sorted(industry_count.items(), key=lambda x: x[1], reverse=True)[:5]
                    ]
                
                return jsonify({
                    "success": True,
                    "data": {
                        "market_state": market_state,
                        "sentiment_score": sentiment_score,
                        "limit_up_count": limit_up_count,
                        "limit_down_count": limit_down_count,
                        "gain_count": 0,  # 需要额外接口获取
                        "loss_count": 0,  # 需要额外接口获取
                        "hot_topics": hot_topics
                    }
                })
            
            # 返回数据库中的数据
            hot_topics = sentiment.hot_topics if sentiment.hot_topics else []
            
            return jsonify({
                "success": True,
                "data": {
                    "market_state": sentiment.market_state,
                    "sentiment_score": float(sentiment.sentiment_score),
                    "limit_up_count": sentiment.limit_up_count,
                    "limit_down_count": sentiment.limit_down_count,
                    "gain_count": sentiment.gain_count or 0,
                    "loss_count": sentiment.loss_count or 0,
                    "hot_topics": hot_topics
                }
            })
            
    except Exception as e:
        print(f"获取市场情绪失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

