"""
账户资金管理API
提供总资产配置、资金操作、账户信息查询等功能
"""

from flask import Blueprint, jsonify, request, session as flask_session
from datetime import datetime, date
from decimal import Decimal
import json
import os
from src.database.db_manager import get_db
from src.database.models import SystemConfig, Position

account_api = Blueprint('account_api', __name__)


def _sync_account_for_realtime_user(user_session_id):
    """
    读取数据库中缓存的账户资金信息（SystemConfig 表）

    Args:
        user_session_id: 用户session_id

    Returns:
        dict: 账户信息 或 None（若未配置）
    """
    try:
        # 从数据库读取资金信息（SystemConfig 表）
        # 资金信息在以下时机同步到数据库：
        # 1. 首次启动时
        # 2. 买入完成后
        # 3. 卖出完成后
        from src.database.db_manager import get_db
        from src.database.models import Position, SystemConfig

        db = get_db()

        with db.get_session() as session:
            # 查询持仓
            positions = session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'holding'
            ).all()

            # 计算持仓市值和盈亏
            total_value = sum(float(p.current_price * p.quantity) for p in positions)
            total_profit_loss = sum(float(p.profit_loss) for p in positions)

            # 🔴 从SystemConfig表读取资金信息（同花顺同步的完整数据）
            # ⚠️ 注意：同花顺的"可用金额"字段实际返回的是"总资产"，真正的可用金额是"资金余额"
            account_fields = {
                'available_capital': 'account_资金余额',  # ✅ 修正：使用资金余额作为可用金额
                'total_capital': 'account_总资产',
                'balance': 'account_资金余额',  # 资金余额（与available_capital相同）
                'withdrawable_capital': 'account_可取金额',
                'stock_market_value': 'account_股票市值',
            }

            account_data = {}
            for field_name, config_key in account_fields.items():
                config = session.query(SystemConfig).filter(
                    SystemConfig.session_id == user_session_id,
                    SystemConfig.config_key == config_key
                ).first()
                if config:
                    try:
                        account_data[field_name] = float(config.config_value)
                    except (ValueError, TypeError):
                        account_data[field_name] = 0
                else:
                    account_data[field_name] = 0

            # ✅ 计算冻结金额（同花顺balance接口不返回此字段）
            # 冻结金额 = 总资产 - 可用金额 - 股票市值
            frozen_capital = (
                account_data.get('total_capital', 0) -
                account_data.get('available_capital', 0) -
                account_data.get('stock_market_value', 0)
            )

            # ✅ 从持仓数据计算持仓盈亏和当日盈亏（同花顺balance接口不返回这些字段）
            # 注意：这些数据需要从持仓明细中累加
            position_profit_loss = total_profit_loss  # 使用数据库计算的总盈亏

            # ✅ 计算今日盈亏：区分今天买入和之前买入的股票
            today_profit_loss = 0
            today_profit_loss_pct = 0
            today = date.today()

            try:
                from src.tools.zhitu_api import ZhituAPI
                zhitu = ZhituAPI()

                # 获取所有持仓股票代码
                stock_codes = [p.stock_code for p in positions]

                if stock_codes:
                    # 获取实时行情（包含昨收价字段）
                    prices_data = zhitu.get_real_time_multi_broker(stock_codes)

                    # 计算今日盈亏
                    for position in positions:
                        price_info = prices_data.get(position.stock_code, {})
                        current_price = price_info.get('current_price', 0)  # 当前价

                        if not current_price:
                            continue

                        # 区分今天买入和之前买入
                        if position.buy_date == today:
                            # 今天买入：今日盈亏 = (当前价 - 买入价) × 数量
                            buy_price = float(position.buy_price)
                            position_today_pl = (current_price - buy_price) * position.quantity
                        else:
                            # 之前买入：今日盈亏 = (当前价 - 昨收价) × 数量
                            yesterday_close = price_info.get('pre_close_price', 0)
                            if not yesterday_close:
                                continue
                            position_today_pl = (current_price - yesterday_close) * position.quantity

                        today_profit_loss += position_today_pl

                    # 计算今日盈亏比
                    if account_data.get('total_capital', 0) > 0:
                        today_profit_loss_pct = (today_profit_loss / account_data.get('total_capital', 1)) * 100

            except Exception as e:
                print(f"❌ 计算今日盈亏失败: {e}")
                today_profit_loss = 0
                today_profit_loss_pct = 0

            # 返回账户信息（合并同花顺数据和数据库计算数据）
            return {
                'total_capital': account_data.get('total_capital', 0),
                'available_capital': account_data.get('available_capital', 0),
                'position_value': total_value,  # 使用数据库计算的持仓市值
                'frozen_capital': frozen_capital,  # ✅ 计算得出
                'total_profit_loss': total_profit_loss,  # 使用数据库计算的总盈亏
                # ✅ 新增：同花顺原始数据
                'balance': account_data.get('balance', 0),  # 资金余额
                'withdrawable_capital': account_data.get('withdrawable_capital', 0),  # 可取金额
                'stock_market_value': account_data.get('stock_market_value', 0),  # 股票市值（同花顺）
                'position_profit_loss': position_profit_loss,  # 持仓盈亏（从数据库计算）
                'today_profit_loss': today_profit_loss,  # 当日盈亏（TODO）
                'today_profit_loss_pct': today_profit_loss_pct,  # 当日盈亏比（TODO）
            }

    except Exception as e:
        print(f"同步账户失败: {e}")
        return None


@account_api.route('/api/account/info', methods=['GET'])
def get_account_info():
    """
    获取账户信息
    
    Returns:
        {
            "success": true,
            "data": {
                "initial_capital": 100000,
                "additional_capital": 0,
                "withdrawn_capital": 0,
                "total_capital": 100000,
                "available_capital": 95000,
                "position_value": 5000,
                "total_profit_loss": 0,
                "total_return_rate": 0,
                "last_updated": "2025-11-04 15:30:00"
            }
        }
    """
    db = get_db()
    
    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        # 🔴 实盘用户：尝试从同花顺同步账户资产
        realtime_account = _sync_account_for_realtime_user(user_session_id)

        if realtime_account:
            # 实盘用户：直接返回同花顺的账户信息（包含完整的11个字段）
            total_profit_loss = realtime_account.get('total_profit_loss', 0)
            total_capital = realtime_account.get('total_capital', 0)

            return jsonify({
                "success": True,
                "data": {
                    # 核心资产数据
                    "total_capital": total_capital,
                    "available_capital": realtime_account.get('available_capital', 0),
                    "position_value": realtime_account.get('position_value', 0),
                    "frozen_capital": realtime_account.get('frozen_capital', 0),
                    "total_profit_loss": total_profit_loss,
                    "total_return_rate": (total_profit_loss / total_capital * 100) if total_capital > 0 else 0,
                    # ✅ 新增：同花顺完整数据
                    "balance": realtime_account.get('balance', 0),  # 资金余额
                    "withdrawable_capital": realtime_account.get('withdrawable_capital', 0),  # 可取金额
                    "stock_market_value": realtime_account.get('stock_market_value', 0),  # 股票市值（同花顺）
                    "position_profit_loss": realtime_account.get('position_profit_loss', 0),  # 持仓盈亏（同花顺）
                    "today_profit_loss": realtime_account.get('today_profit_loss', 0),  # 当日盈亏
                    "today_profit_loss_pct": realtime_account.get('today_profit_loss_pct', 0),  # 当日盈亏比
                    # 元数据
                    "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "source": "realtime"  # 标识数据来源
                }
            })

        # 远程用户：从数据库读取
        with db.get_session() as session:
            # ✅ 获取资金配置（添加session_id过滤）
            config = session.query(SystemConfig).filter(
                SystemConfig.session_id == user_session_id,
                SystemConfig.config_key == 'account_capital'
            ).first()

            if not config:
                # 初始化默认配置
                default_config = {
                    "initial_capital": 100000,
                    "additional_capital": 0,
                    "withdrawn_capital": 0,
                    "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                config = SystemConfig(
                    session_id=user_session_id,  # ✅ 添加session_id
                    config_key="account_capital",
                    config_type="json",
                    config_value=json.dumps(default_config),
                    description="账户资金配置"
                )
                session.add(config)
                session.commit()

            # 解析配置
            capital_config = json.loads(config.config_value)

            # 计算总资产
            total_capital = (
                capital_config.get('initial_capital', 100000) +
                capital_config.get('additional_capital', 0) -
                capital_config.get('withdrawn_capital', 0)
            )

            # ✅ 计算持仓市值（添加session_id过滤）
            positions = session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'holding'
            ).all()
            
            position_value = sum(
                float(p.current_price or p.buy_price) * p.quantity
                for p in positions
            )
            
            # 计算可用资金
            available_capital = total_capital - position_value
            
            # 计算累计盈亏
            total_profit_loss = sum(
                float(p.profit_loss or 0)
                for p in positions
            )
            
            # 计算收益率
            total_return_rate = (total_profit_loss / total_capital * 100) if total_capital > 0 else 0

            # ✅ 计算今日盈亏：区分今天买入和之前买入的股票
            today_profit_loss = 0
            today_profit_loss_pct = 0
            today = date.today()

            try:
                from src.tools.zhitu_api import ZhituAPI
                zhitu = ZhituAPI()

                # 获取所有持仓股票代码
                stock_codes = [p.stock_code for p in positions]

                if stock_codes:
                    # 获取实时行情（包含昨收价字段）
                    prices_data = zhitu.get_real_time_multi_broker(stock_codes)

                    # 计算今日盈亏
                    for position in positions:
                        price_info = prices_data.get(position.stock_code, {})
                        current_price = price_info.get('current_price', 0)  # 当前价

                        if not current_price:
                            continue

                        # 区分今天买入和之前买入
                        if position.buy_date == today:
                            # 今天买入：今日盈亏 = (当前价 - 买入价) × 数量
                            buy_price = float(position.buy_price)
                            position_today_pl = (current_price - buy_price) * position.quantity
                        else:
                            # 之前买入：今日盈亏 = (当前价 - 昨收价) × 数量
                            yesterday_close = price_info.get('pre_close_price', 0)
                            if not yesterday_close:
                                continue
                            position_today_pl = (current_price - yesterday_close) * position.quantity

                        today_profit_loss += position_today_pl

                    # 计算今日盈亏比
                    if total_capital > 0:
                        today_profit_loss_pct = (today_profit_loss / total_capital) * 100

            except Exception as e:
                print(f"❌ [远程用户] 计算今日盈亏失败: {e}")
                today_profit_loss = 0
                today_profit_loss_pct = 0

            return jsonify({
                "success": True,
                "data": {
                    "initial_capital": capital_config.get('initial_capital', 100000),
                    "additional_capital": capital_config.get('additional_capital', 0),
                    "withdrawn_capital": capital_config.get('withdrawn_capital', 0),
                    "total_capital": total_capital,
                    "available_capital": available_capital,
                    "position_value": position_value,
                    "total_profit_loss": total_profit_loss,
                    "total_return_rate": round(total_return_rate, 2),
                    "today_profit_loss": round(today_profit_loss, 2),  # ✅ 实现今日盈亏计算
                    "today_profit_loss_pct": round(today_profit_loss_pct, 2),  # ✅ 实现今日盈亏比计算
                    "last_updated": capital_config.get('last_updated', ''),
                    "source": "database"  # 标识数据来源
                }
            })
            
    except Exception as e:
        print(f"获取账户信息失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@account_api.route('/api/account/config', methods=['POST'])
def config_account():
    """
    配置账户资金
    
    Request Body:
        {
            "action": "set_initial",  // set_initial / add_capital / withdraw_capital
            "amount": 100000
        }
    
    Returns:
        {
            "success": true,
            "message": "操作成功",
            "data": {
                "total_capital": 100000,
                "available_capital": 95000
            }
        }
    """
    db = get_db()
    
    try:
        # ✅ 获取当前用户的session_id
        user_session_id = flask_session.get('user_session_id', 'default')

        data = request.get_json()
        action = data.get('action')
        amount = float(data.get('amount', 0))

        if not action or amount <= 0:
            return jsonify({
                "success": False,
                "message": "参数错误"
            }), 400

        with db.get_session() as session:
            # ✅ 获取配置（添加session_id过滤）
            config = session.query(SystemConfig).filter(
                SystemConfig.session_id == user_session_id,
                SystemConfig.config_key == 'account_capital'
            ).first()

            if not config:
                capital_config = {
                    "initial_capital": 0,
                    "additional_capital": 0,
                    "withdrawn_capital": 0
                }
            else:
                capital_config = json.loads(config.config_value)
            
            # 执行操作
            message = ""
            if action == 'set_initial':
                capital_config['initial_capital'] = amount
                message = f"初始资金设置成功：¥{amount:,.2f}"
            
            elif action == 'add_capital':
                capital_config['additional_capital'] = capital_config.get('additional_capital', 0) + amount
                message = f"追加资金成功：¥{amount:,.2f}"
            
            elif action == 'withdraw_capital':
                capital_config['withdrawn_capital'] = capital_config.get('withdrawn_capital', 0) + amount
                message = f"提取资金成功：¥{amount:,.2f}"
            
            else:
                return jsonify({
                    "success": False,
                    "message": "未知操作类型"
                }), 400
            
            # 更新时间
            capital_config['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 保存配置
            if config:
                config.config_value = json.dumps(capital_config)
            else:
                config = SystemConfig(
                    session_id=user_session_id,  # ✅ 添加session_id
                    config_key="account_capital",
                    config_type="json",
                    config_value=json.dumps(capital_config),
                    description="账户资金配置"
                )
                session.add(config)

            session.commit()

            # 计算最新数据
            total_capital = (
                capital_config['initial_capital'] +
                capital_config.get('additional_capital', 0) -
                capital_config.get('withdrawn_capital', 0)
            )

            # ✅ 计算持仓市值（添加session_id过滤）
            positions = session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'holding'
            ).all()
            
            position_value = sum(
                float(p.current_price or p.buy_price) * p.quantity
                for p in positions
            )
            
            available_capital = total_capital - position_value
            
            return jsonify({
                "success": True,
                "message": message,
                "data": {
                    "total_capital": total_capital,
                    "available_capital": available_capital,
                    "position_value": position_value
                }
            })
            
    except Exception as e:
        print(f"配置账户失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

