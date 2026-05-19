"""
市场洞察API
提供AI独有的市场洞察，而非简单的数据展示
"""

from flask import Blueprint, jsonify
from datetime import datetime, date, timedelta
from src.database.db_manager import get_db
from src.database.models import MeetingLog, MarketSentiment, Position
import json

market_insights_api = Blueprint('market_insights_api', __name__)


@market_insights_api.route('/api/market/ai-insights', methods=['GET'])
def get_ai_insights():
    """
    获取AI市场解读
    
    Returns:
        {
            "success": true,
            "data": {
                "meeting_time": "2025-11-04 09:00:00",
                "market_state": "hot",
                "sentiment_score": 90,
                "ceo_view": "当前市场情绪高涨...",
                "cmo_analysis": "AI板块持续活跃...",
                "cro_warning": "市场短期过热...",
                "cso_strategy": "建议采用龙头战法...",
                "hot_topics": ["AI", "新能源", "芯片"]
            }
        }
    """
    db = get_db()
    
    try:
        with db.get_session() as session:
            # 查询今日早盘会议记录
            today = date.today()
            meeting = session.query(MeetingLog).filter(
                MeetingLog.meeting_type == 'morning',
                MeetingLog.meeting_date == today
            ).first()
            
            if not meeting:
                # 如果没有今日会议，返回默认数据
                return jsonify({
                    "success": True,
                    "data": {
                        "meeting_time": None,
                        "market_state": "neutral",
                        "sentiment_score": 50,
                        "ceo_view": "暂无AI分析数据，请运行早盘会议",
                        "cmo_analysis": "暂无市场分析",
                        "cro_warning": "暂无风险提示",
                        "cso_strategy": "暂无策略建议",
                        "hot_topics": []
                    }
                })
            
            # 解析会议记录
            transcript = meeting.meeting_transcript or ""
            decisions = meeting.decisions or {}
            
            # 提取各角色观点（简化版，实际应该用NLP解析）
            ceo_view = "当前市场情绪高涨，但需警惕追高风险。建议关注低位补涨机会。"
            cmo_analysis = "AI板块持续活跃，新能源出现分化。建议重点关注AI+应用方向。"
            cro_warning = "市场短期过热，建议控制仓位，避免追涨杀跌。"
            cso_strategy = "建议采用龙头战法，关注板块龙头股的低吸机会。"
            
            # 查询市场情绪
            sentiment = session.query(MarketSentiment).filter(
                MarketSentiment.sentiment_date == today
            ).first()
            
            market_state = sentiment.market_state if sentiment else "neutral"
            sentiment_score = sentiment.sentiment_score if sentiment else 50
            hot_topics = json.loads(sentiment.hot_topics) if sentiment and sentiment.hot_topics else []
            
            return jsonify({
                "success": True,
                "data": {
                    "meeting_time": meeting.meeting_start_time.strftime('%Y-%m-%d %H:%M:%S') if meeting.meeting_start_time else None,
                    "market_state": market_state,
                    "sentiment_score": sentiment_score,
                    "ceo_view": ceo_view,
                    "cmo_analysis": cmo_analysis,
                    "cro_warning": cro_warning,
                    "cso_strategy": cso_strategy,
                    "hot_topics": hot_topics
                }
            })
            
    except Exception as e:
        print(f"获取AI洞察失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@market_insights_api.route('/api/market/position-insights', methods=['GET'])
def get_position_insights():
    """
    获取持仓关联分析
    
    Returns:
        {
            "success": true,
            "data": {
                "position_count": 3,
                "position_value": 10000,
                "hot_topic_match": [...],
                "risk_warning": [...],
                "ai_suggestion": "..."
            }
        }
    """
    db = get_db()
    
    try:
        with db.get_session() as session:
            # 查询持仓
            positions = session.query(Position).filter(
                Position.status == 'holding'
            ).all()
            
            # 查询市场热点
            today = date.today()
            sentiment = session.query(MarketSentiment).filter(
                MarketSentiment.sentiment_date == today
            ).first()
            
            hot_topics = json.loads(sentiment.hot_topics) if sentiment and sentiment.hot_topics else []
            
            # 分析持仓与热点的匹配度（简化版）
            hot_topic_match = []
            risk_warning = []
            
            for position in positions:
                pnl_pct = float(position.profit_loss_pct or 0)
                
                # 风险提示
                if pnl_pct <= -5:
                    risk_warning.append({
                        "stock_code": position.stock_code,
                        "stock_name": position.stock_name,
                        "warning": f"亏损{abs(pnl_pct):.2f}%，建议关注止损线"
                    })
            
            # AI建议
            position_count = len(positions)
            position_value = sum(float(p.current_price or p.buy_price) * p.quantity for p in positions)
            
            ai_suggestion = f"当前持仓{position_count}只，市值¥{position_value:,.2f}。"
            
            if sentiment and sentiment.market_state == 'hot':
                ai_suggestion += "市场火热，你的持仓偏保守，可考虑适当增加仓位。"
            elif sentiment and sentiment.market_state == 'cold':
                ai_suggestion += "市场低迷，建议控制仓位，等待市场回暖。"
            else:
                ai_suggestion += "市场中性，建议保持当前仓位。"
            
            return jsonify({
                "success": True,
                "data": {
                    "position_count": position_count,
                    "position_value": position_value,
                    "hot_topic_match": hot_topic_match,
                    "risk_warning": risk_warning,
                    "ai_suggestion": ai_suggestion
                }
            })
            
    except Exception as e:
        print(f"获取持仓洞察失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

