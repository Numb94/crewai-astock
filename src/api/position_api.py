"""
持仓监控API
提供持仓查询、买入、卖出、智能卖点计算等功能
"""

from flask import Blueprint, jsonify, request, session as flask_session
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
from loguru import logger
from src.database.db_manager import get_db
from src.database.models import Position, Transaction, Candidate
from src.tools.zhitu_api import ZhituAPI

position_api = Blueprint('position_api', __name__)


@position_api.route('/api/positions/all', methods=['GET'])
def get_all_positions():
    """
    获取所有持仓记录（包括已卖出的）

    Query Parameters:
        status: 可选，过滤状态 (holding/sold/all，默认all)
        limit: 可选，返回数量限制（默认100）
        offset: 可选，偏移量（默认0）

    Returns:
        {
            "success": true,
            "data": {
                "positions": [...],
                "total": 50,
                "holding_count": 10,
                "sold_count": 40
            }
        }
    """
    db = get_db()

    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')


        # 获取查询参数
        status_filter = request.args.get('status', 'all')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        with db.get_session() as session:
            # 构建查询
            query = session.query(Position).filter(
                Position.session_id == user_session_id
            )

            # 状态过滤
            if status_filter != 'all':
                query = query.filter(Position.status == status_filter)

            # 统计总数
            total = query.count()
            holding_count = session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'holding'
            ).count()
            sold_count = session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'sold'
            ).count()

            # 分页查询
            positions = query.order_by(Position.buy_date.desc()).limit(limit).offset(offset).all()

            result_positions = []
            for position in positions:
                pos_data = {
                    "id": position.id,
                    "stock_code": position.stock_code,
                    "stock_name": position.stock_name,
                    "buy_price": float(position.buy_price),
                    "buy_date": position.buy_date.strftime('%Y-%m-%d'),
                    "buy_time": position.buy_time.strftime('%H:%M:%S') if position.buy_time else None,
                    "quantity": position.quantity,
                    "strategy_used": position.strategy_used,
                    "status": position.status,
                    "holding_days": (date.today() - position.buy_date).days
                }

                # 如果已卖出，添加卖出信息
                if position.status == 'sold':
                    pos_data.update({
                        "sell_price": float(position.sell_price) if position.sell_price else None,
                        "sell_date": position.sell_date.strftime('%Y-%m-%d') if position.sell_date else None,
                        "profit_loss": float(position.profit_loss) if position.profit_loss else 0,
                        "profit_loss_pct": float(position.profit_loss_pct) if position.profit_loss_pct else 0
                    })
                else:
                    # 如果持仓中，添加当前价格信息
                    pos_data.update({
                        "current_price": float(position.current_price) if position.current_price else float(position.buy_price),
                        "profit_loss": float(position.profit_loss) if position.profit_loss else 0,
                        "profit_loss_pct": float(position.profit_loss_pct) if position.profit_loss_pct else 0
                    })

                result_positions.append(pos_data)

            return jsonify({
                "success": True,
                "data": {
                    "positions": result_positions,
                    "total": total,
                    "holding_count": holding_count,
                    "sold_count": sold_count,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "has_more": (offset + limit) < total
                    }
                }
            })

    except Exception as e:
        print(f"获取持仓列表失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"获取持仓列表失败: {str(e)}"
        }), 500


@position_api.route('/api/positions/monitor', methods=['GET'])
def monitor_positions():
    """
    持仓监控 - 获取所有持仓及智能卖点建议

    Returns:
        {
            "success": true,
            "data": {
                "positions": [...],
                "total_profit_loss": 2500.00,
                "total_return_rate": 5.25
            }
        }
    """
    db = get_db()
    zhitu = ZhituAPI()

    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')


        with db.get_session() as session:
            # ✅ 查询所有持仓（添加session_id过滤）
            positions = session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'holding'
            ).all()

            if not positions:
                return jsonify({
                    "success": True,
                    "data": {
                        "positions": [],
                        "total_profit_loss": 0,
                        "total_return_rate": 0
                    }
                })

            # 获取实时价格
            stock_codes = [p.stock_code for p in positions]

            try:
                prices_data = zhitu.get_real_time_multi_broker(stock_codes)
            except Exception as e:
                # 只在出错时打印日志
                print(f"❌ 获取实时价格失败: {e}")
                prices_data = {}

            # 计算智能卖点
            result_positions = []
            total_profit_loss = Decimal('0')
            total_cost = Decimal('0')

            for position in positions:
                # 获取实时价格
                price_info = prices_data.get(position.stock_code, {})

                # ✅ 修复：字段名已经被映射为 'current_price'，不是 'p'
                # 同时保留 'p' 作为备选（兼容未映射的情况）
                current_price = price_info.get('current_price') or price_info.get('p', position.buy_price)
                current_price = Decimal(str(current_price))

                # 计算总盈亏
                profit_loss = (current_price - position.buy_price) * position.quantity
                profit_loss_pct = ((current_price - position.buy_price) / position.buy_price) * 100

                # 获取今日涨跌幅和今日盈亏
                # 注意：字段已被映射为 'change_pct'，同时保留 'pc' 作为备选
                today_change_pct = price_info.get('change_pct') or price_info.get('pc', 0)  # 今日涨跌幅
                today_profit_loss = (current_price * Decimal(str(today_change_pct)) / 100) * position.quantity  # 今日盈亏金额

                # 更新持仓
                position.current_price = current_price
                position.profit_loss = profit_loss
                position.profit_loss_pct = profit_loss_pct

                # 获取卖点建议（优先使用AI分析结果）
                if position.ai_sell_suggestion and position.ai_analysis_time:
                    # 使用缓存的AI分析结果
                    sell_suggestion = position.ai_sell_suggestion
                    sell_reason = position.ai_sell_reason
                    urgency = position.ai_urgency
                else:
                    # 使用简单规则
                    sell_suggestion, sell_reason, urgency = calculate_sell_point(
                        position, current_price, prices_data.get(position.stock_code, {})
                    )

                # 获取买入时间：优先使用持仓记录的buy_time，否则查推荐记录
                buy_time_str = None
                buy_date_str = position.buy_date.strftime('%Y-%m-%d')

                if position.buy_time:
                    buy_time_str = position.buy_time.strftime('%H:%M:%S')
                else:
                    # 没有buy_time，查询推荐记录获取更准确的时间
                    recommend_record = session.query(Candidate).filter(
                        Candidate.session_id == user_session_id,
                        Candidate.stock_code == position.stock_code
                    ).order_by(Candidate.recommend_time.desc()).first()

                    if recommend_record:
                        # 使用推荐记录的时间
                        buy_date_str = recommend_record.recommend_time.strftime('%Y-%m-%d')
                        buy_time_str = recommend_record.recommend_time.strftime('%H:%M:%S')

                result_positions.append({
                    "id": position.id,
                    "stock_code": position.stock_code,
                    "stock_name": position.stock_name,
                    "buy_price": round(float(position.buy_price), 3),  # 保留3位小数
                    "current_price": round(float(current_price), 3),  # 保留3位小数
                    "highest_price": round(float(position.today_highest_price), 3) if position.today_highest_price else round(float(current_price), 3),  # 最高价
                    "quantity": position.quantity,
                    "profit_loss": float(profit_loss),
                    "profit_loss_pct": float(profit_loss_pct),
                    "today_change_pct": float(today_change_pct),  # 新增：今日涨跌幅
                    "today_profit_loss": float(today_profit_loss),  # 新增：今日盈亏金额
                    "sell_suggestion": sell_suggestion,
                    "sell_reason": sell_reason,
                    "urgency": urgency,
                    "buy_date": buy_date_str,
                    "buy_time": buy_time_str,
                    "holding_days": (date.today() - position.buy_date).days,
                    "ai_analysis_time": position.ai_analysis_time.strftime('%Y-%m-%d %H:%M:%S') if position.ai_analysis_time else None,
                    "is_ai_analysis": bool(position.ai_sell_suggestion and position.ai_analysis_time)
                })

                total_profit_loss += profit_loss
                total_cost += position.buy_price * position.quantity

            session.commit()

            # 计算总收益率
            total_return_rate = (total_profit_loss / total_cost * 100) if total_cost > 0 else 0

            return jsonify({
                "success": True,
                "data": {
                    "positions": result_positions,
                    "total_profit_loss": float(total_profit_loss),
                    "total_return_rate": float(total_return_rate)
                }
            })

    except Exception as e:
        print(f"持仓监控失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"持仓监控失败: {str(e)}"
        }), 500


def calculate_sell_point(position, current_price, realtime_data):
    """
    计算智能卖点

    Args:
        position: 持仓对象
        current_price: 当前价格
        realtime_data: 实时数据（涨跌幅、成交额等）

    Returns:
        (sell_suggestion, sell_reason, urgency)
    """
    profit_loss_pct = float(position.profit_loss_pct)
    holding_days = (date.today() - position.buy_date).days
    # 注意：字段已被映射为 'change_pct'，同时保留 'pc' 作为备选
    today_change_pct = realtime_data.get('change_pct') or realtime_data.get('pc', 0)  # 今日涨跌幅

    # 强烈建议卖出（high urgency）
    if profit_loss_pct >= 8 and today_change_pct < 0:
        return "强烈建议卖出", f"盈利{profit_loss_pct:.2f}%，今日冲高回落，建议止盈", "high"

    if profit_loss_pct >= 10:
        return "强烈建议卖出", f"盈利{profit_loss_pct:.2f}%，达到止盈目标", "high"

    if profit_loss_pct <= -8:
        return "强烈建议卖出", f"亏损{abs(profit_loss_pct):.2f}%，达到止损线", "high"

    # 建议卖出（medium urgency）
    if profit_loss_pct >= 5 and holding_days >= 3:
        return "建议卖出", f"盈利{profit_loss_pct:.2f}%，持仓{holding_days}天，可考虑止盈", "medium"

    if profit_loss_pct <= -5:
        return "建议卖出", f"亏损{abs(profit_loss_pct):.2f}%，建议止损", "medium"

    # 建议持有（low urgency）
    if profit_loss_pct > 0:
        return "建议持有", f"盈利{profit_loss_pct:.2f}%，趋势良好", "low"
    else:
        return "建议观望", f"亏损{abs(profit_loss_pct):.2f}%，等待反弹", "low"


@position_api.route('/api/positions/buy', methods=['POST'])
def buy_position():
    """
    买入股票

    Request Body:
        {
            "stock_code": "600000",
            "stock_name": "浦发银行",
            "buy_price": 10.50,
            "quantity": 1000,
            "strategy": "龙头战法"
        }

    Returns:
        {
            "success": true,
            "message": "买入成功",
            "data": {...}
        }
    """
    db = get_db()

    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        data = request.get_json()

        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name')
        buy_price = Decimal(str(data.get('buy_price')))
        quantity = int(data.get('quantity'))
        strategy = data.get('strategy', '未知策略')

        if not all([stock_code, stock_name, buy_price, quantity]):
            return jsonify({
                "success": False,
                "message": "缺少必要参数"
            }), 400

        with db.get_session() as session:
            # ✅ 创建持仓记录（添加session_id + buy_time）
            current_time = datetime.now().time()

            position = Position(
                session_id=user_session_id,
                stock_code=stock_code,
                stock_name=stock_name,
                buy_date=date.today(),
                buy_time=current_time,  # ✅ 新增：保存买入时间
                buy_price=buy_price,
                quantity=quantity,
                can_sell_date=date.today() + timedelta(days=1),  # T+1
                strategy_used=strategy,
                current_price=buy_price,
                profit_loss=Decimal('0'),
                profit_loss_pct=Decimal('0'),
                status='holding'
            )

            session.add(position)
            session.flush()

            # 创建交易记录
            transaction = Transaction(
                stock_code=stock_code,
                stock_name=stock_name,
                trade_type='BUY',
                trade_date=date.today(),
                price=buy_price,
                quantity=quantity,
                amount=buy_price * quantity,
                strategy_used=strategy,
                position_id=position.id
            )

            session.add(transaction)
            session.commit()

            return jsonify({
                "success": True,
                "message": "买入成功",
                "data": {
                    "position_id": position.id,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "buy_price": float(buy_price),
                    "quantity": quantity
                }
            })

    except Exception as e:
        print(f"买入失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"买入失败: {str(e)}"
        }), 500


@position_api.route('/api/positions/add', methods=['POST'])
def add_position_manually():
    """
    手动添加持仓

    Request Body:
        {
            "stock_code": "600000",
            "stock_name": "浦发银行",
            "buy_price": 10.50,
            "quantity": 1000,
            "buy_date": "2025-01-01",  # 可选，默认今天
            "strategy": "手动添加"  # 可选
        }

    Returns:
        {
            "success": true,
            "message": "添加成功",
            "data": {...}
        }
    """
    db = get_db()

    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        data = request.get_json()

        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name')
        buy_price = Decimal(str(data.get('buy_price')))
        quantity = int(data.get('quantity'))
        buy_date_str = data.get('buy_date')
        strategy = data.get('strategy', '手动添加')

        if not all([stock_code, stock_name, buy_price, quantity]):
            return jsonify({
                "success": False,
                "message": "缺少必要参数"
            }), 400

        # 解析买入日期
        if buy_date_str:
            try:
                buy_date_obj = datetime.strptime(buy_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    "success": False,
                    "message": "日期格式错误，应为YYYY-MM-DD"
                }), 400
        else:
            buy_date_obj = date.today()

        with db.get_session() as session:
            # ✅ 创建持仓记录（添加session_id + buy_time）
            current_time = datetime.now().time()

            position = Position(
                session_id=user_session_id,
                stock_code=stock_code,
                stock_name=stock_name,
                buy_date=buy_date_obj,
                buy_time=current_time,  # ✅ 新增：保存买入时间
                buy_price=buy_price,
                quantity=quantity,
                can_sell_date=buy_date_obj + timedelta(days=1),  # T+1
                strategy_used=strategy,
                current_price=buy_price,
                profit_loss=Decimal('0'),
                profit_loss_pct=Decimal('0'),
                status='holding'
            )

            session.add(position)
            session.flush()

            # 创建交易记录
            transaction = Transaction(
                stock_code=stock_code,
                stock_name=stock_name,
                trade_type='BUY',
                trade_date=buy_date_obj,
                price=buy_price,
                quantity=quantity,
                amount=buy_price * quantity,
                strategy_used=strategy,
                position_id=position.id
            )

            session.add(transaction)
            session.commit()

            return jsonify({
                "success": True,
                "message": "添加成功",
                "data": {
                    "position_id": position.id,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "buy_price": float(buy_price),
                    "quantity": quantity,
                    "buy_date": buy_date_obj.strftime('%Y-%m-%d')
                }
            })

    except Exception as e:
        print(f"添加持仓失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"添加持仓失败: {str(e)}"
        }), 500


@position_api.route('/api/positions/sell', methods=['POST'])
def sell_position():
    """
    卖出股票

    Request Body:
        {
            "position_id": 1,
            "sell_price": 11.50
        }

    Returns:
        {
            "success": true,
            "message": "卖出成功",
            "data": {...}
        }
    """
    db = get_db()

    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        data = request.get_json()

        position_id = data.get('position_id')
        sell_price = Decimal(str(data.get('sell_price')))

        if not all([position_id, sell_price]):
            return jsonify({
                "success": False,
                "message": "缺少必要参数"
            }), 400

        with db.get_session() as session:
            # ✅ 查询持仓（添加session_id过滤）
            position = session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.id == position_id,
                Position.status == 'holding'
            ).first()

            if not position:
                return jsonify({
                    "success": False,
                    "message": "持仓不存在或已卖出"
                }), 404

            # 检查T+1限制
            if date.today() < position.can_sell_date:
                return jsonify({
                    "success": False,
                    "message": f"T+1限制，最早可卖日期：{position.can_sell_date}"
                }), 400

            # 计算盈亏
            profit_loss = (sell_price - position.buy_price) * position.quantity
            profit_loss_pct = ((sell_price - position.buy_price) / position.buy_price) * 100

            # 🔴 修复：先更新持仓状态（避免被同步覆盖）
            position.status = 'sold'
            position.sell_date = date.today()
            position.sell_price = sell_price
            position.profit_loss = profit_loss
            position.profit_loss_pct = profit_loss_pct
            position.sell_reason = 'Web手动卖出'

            # 创建交易记录
            transaction = Transaction(
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                trade_type='SELL',
                trade_date=date.today(),
                price=sell_price,
                quantity=position.quantity,
                amount=sell_price * position.quantity,
                strategy_used=position.strategy_used,
                position_id=position.id,
                profit_loss=profit_loss,
                profit_loss_pct=profit_loss_pct
            )

            session.add(transaction)
            session.commit()

            return jsonify({
                "success": True,
                "message": "卖出成功",
                "data": {
                    "position_id": position.id,
                    "stock_code": position.stock_code,
                    "stock_name": position.stock_name,
                    "sell_price": float(sell_price),
                    "profit_loss": float(profit_loss),
                    "profit_loss_pct": float(profit_loss_pct)
                }
            })

    except Exception as e:
        print(f"卖出失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"卖出失败: {str(e)}"
        }), 500

