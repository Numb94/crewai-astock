"""
策略表现API
提供策略胜率、收益率等统计数据
"""

from flask import Blueprint, jsonify
from datetime import date, timedelta
from src.database.db_manager import get_db
from src.database.models import Transaction

strategy_api = Blueprint('strategy_api', __name__)


@strategy_api.route('/api/strategies/performance', methods=['GET'])
def get_strategy_performance():
    """
    获取策略表现
    
    Returns:
        {
            "success": true,
            "data": {
                "strategies": [
                    {
                        "name": "龙头战法",
                        "win_rate": 70.5,
                        "avg_return": 5.2,
                        "trade_count": 10
                    },
                    ...
                ]
            }
        }
    """
    db = get_db()
    
    try:
        with db.get_session() as session:
            # 查询最近7天的交易记录（使用trade_type和trade_date字段）
            seven_days_ago = date.today() - timedelta(days=7)

            transactions = session.query(Transaction).filter(
                Transaction.trade_type == 'SELL',
                Transaction.trade_date >= seven_days_ago
            ).all()
            
            # 按策略统计
            strategy_stats = {}
            
            for trans in transactions:
                # ✅ 直接使用策略名称（不转换）
                strategy = trans.strategy_used or '未知策略'

                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        'name': strategy,
                        'win_count': 0,
                        'total_count': 0,
                        'total_return': 0
                    }

                strategy_stats[strategy]['total_count'] += 1

                if trans.profit_loss_pct and trans.profit_loss_pct > 0:
                    strategy_stats[strategy]['win_count'] += 1

                if trans.profit_loss_pct:
                    strategy_stats[strategy]['total_return'] += float(trans.profit_loss_pct)
            
            # 计算胜率和平均收益率
            result = []

            # ✅ 动态统计所有策略（不限制策略种类）
            for strategy_name, stats in strategy_stats.items():
                win_rate = (stats['win_count'] / stats['total_count'] * 100) if stats['total_count'] > 0 else 0
                avg_return = (stats['total_return'] / stats['total_count']) if stats['total_count'] > 0 else 0

                result.append({
                    'name': strategy_name,
                    'win_rate': round(win_rate, 2),
                    'avg_return': round(avg_return, 2),
                    'trade_count': stats['total_count']
                })
            
            # 按胜率排序
            result.sort(key=lambda x: x['win_rate'], reverse=True)
            
            return jsonify({
                "success": True,
                "data": {
                    "strategies": result
                }
            })
            
    except Exception as e:
        print(f"获取策略表现失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"获取策略表现失败: {str(e)}"
        }), 500

