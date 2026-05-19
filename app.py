#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock V2.0 - Web管理界面

提供数据源、数据库、推送功能的Web管理界面

作者: AI Architect
版本: v1.0.0-web-interface
日期: 2025-10-31
"""

# ❌ 必须在所有import之前设置环境变量和警告过滤器
import os
os.environ['PYTHONWARNINGS'] = 'ignore::UserWarning'  # 环境变量方式隐藏警告

import warnings
warnings.simplefilter('ignore', UserWarning)  # 使用simplefilter而不是filterwarnings

import asyncio
import json
import secrets
from datetime import datetime, date, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from loguru import logger
from sqlalchemy import func

# 导入系统模块
from src.tools.data_source_manager import create_data_manager, DataSource
from src.database.db_manager import get_db
from src.database.models import Candidate, Position, Transaction, MarketSentiment, SystemConfig
from src.utils.pushplus_notifier import get_pushplus_notifier

# 导入API蓝图
from src.api.position_api import position_api
from src.api.recommendation_api import recommendation_api
from src.api.strategy_api import strategy_api
from src.api.market_api import market_api
from src.api.account_api import account_api
from src.api.market_insights_api import market_insights_api
from src.api.performance_api import performance_api
from src.api.kline_api import kline_api
from src.api.crew_stream_api import crew_stream_api
from src.api.stock_evaluation_api import stock_evaluation_api
from src.api.market_data_api import market_data_api

# ✅ Scheduler已移除全局导入，每个用户有独立的Scheduler实例

# 创建Flask应用
app = Flask(__name__)

# ✅ Flask Session配置（多用户支持）
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'  # 使用文件系统存储Session
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Session有效期30天

# 禁用模板缓存（开发环境）
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# 注册API蓝图
app.register_blueprint(position_api)
app.register_blueprint(recommendation_api)
app.register_blueprint(strategy_api)
app.register_blueprint(market_api)
app.register_blueprint(account_api)
app.register_blueprint(market_insights_api)
app.register_blueprint(performance_api)
app.register_blueprint(kline_api)
app.register_blueprint(crew_stream_api)
app.register_blueprint(stock_evaluation_api)
app.register_blueprint(market_data_api)

# ✅ Session初始化中间件（多用户支持 + 用户名系统）
@app.before_request
def ensure_session():
    """
    确保每个请求都有session_id

    策略：
    1. 优先从Cookie获取username（持久化30天）
    2. 如果Cookie不存在，跳转到登录页面（输入用户名）
    3. 用户名作为session_id
    """
    # 跳过登录页面和静态资源的检查
    # ⚠️ API接口不跳过，需要验证用户身份
    if request.path in ['/login', '/api/login', '/static/'] or request.path.startswith('/static/'):
        return

    # 尝试从Cookie获取username
    username = request.cookies.get('username')

    if username:
        # Cookie存在，使用用户名作为session_id
        session['user_session_id'] = username
        session['username'] = username
        session.permanent = True

        # ✅ 使用UserContainerManager管理用户容器（自动创建）
        from src.core.user_container import get_container_manager
        container_manager = get_container_manager()

        # ✅ 获取或创建用户容器（包含独立的Scheduler）
        user_container = container_manager.get_or_create(username)

        # ✅ 如果用户的Scheduler未启动，则启动（双重检查锁定，防止并发创建）
        if user_container.scheduler_instance is None:
            with user_container.lock:  # 🔒 加锁
                if user_container.scheduler_instance is None:  # 🔒 双重检查
                    from scheduler import StockScheduler
                    user_container.scheduler_instance = StockScheduler(session_id=username)
                    user_container.scheduler_instance.start()
                    logger.info(f"🚀 [{username[:8]}...] 启动用户Scheduler")
        elif not user_container.scheduler_instance.is_running:
            user_container.scheduler_instance.start()
            logger.info(f"🔄 [{username[:8]}...] 重启用户Scheduler")

        # logger.debug(f"✅ 用户登录: {username[:8]}...")  # 🔴 注释掉频繁的DEBUG日志
    elif 'user_session_id' not in session:
        # Cookie不存在且Session也不存在，跳转到登录页面
        if request.path != '/login':
            return redirect(url_for('login_page', next=request.path))


@app.after_request
def save_user_cookie(response):
    """
    将username和session_id保存到Cookie（持久化30天）

    这样即使关闭浏览器，下次打开仍然是同一个用户
    """
    if 'username' in session:
        # 保存username（httponly=True，防止JavaScript访问）
        response.set_cookie(
            'username',
            session['username'],
            max_age=30*24*60*60,  # 30天过期
            httponly=True,        # 防止JavaScript访问（安全）
            samesite='Lax'        # CSRF保护
        )

        # 保存session_id（httponly=False，允许JavaScript访问）
        response.set_cookie(
            'session_id',
            session['username'],  # session_id就是username
            max_age=30*24*60*60,  # 30天过期
            httponly=False,       # 允许JavaScript访问（用于SSE连接）
            samesite='Lax'        # CSRF保护
        )
    return response

# 全局变量
data_manager = None
db_manager = None
push_notifier = None
# ✅ scheduler已移除，每个用户有独立的Scheduler实例（存储在UserContainer中）

def init_services():
    """初始化服务"""
    global data_manager, db_manager, push_notifier
    try:
        # 加载环境变量
        from dotenv import load_dotenv
        load_dotenv()
        print("📄 环境变量已加载")

        # 初始化数据源管理器
        try:
            data_manager = create_data_manager()
            print("✅ 数据源管理器初始化成功")
        except Exception as e:
            print(f"❌ 数据源管理器初始化失败: {e}")
            logger.exception("数据源管理器详细错误:")

        # 初始化数据库管理器
        try:
            db_manager = get_db()
            print("✅ 数据库管理器初始化成功")
        except Exception as e:
            print(f"❌ 数据库管理器初始化失败: {e}")
            logger.exception("数据库管理器详细错误:")

        # 初始化推送通知器
        try:
            push_notifier = get_pushplus_notifier()
            print("✅ 推送通知器初始化成功")
            print(f"   - Token配置: {bool(push_notifier.token)}")
            print(f"   - Topic配置: {bool(push_notifier.topic)}")
        except Exception as e:
            print(f"❌ 推送通知器初始化失败: {e}")
            logger.exception("推送通知器详细错误:")

        # ✅ 初始化用户容器管理器（Scheduler按用户独立创建）
        try:
            from src.core.user_container import get_container_manager
            container_manager = get_container_manager()
            print("✅ 用户容器管理器初始化成功")
            print("   - 每个用户有独立的Scheduler实例")
            print("   - 支持多用户并发运行")
            print("   - 自动清理过期容器（30分钟）")
        except Exception as e:
            print(f"❌ 用户容器管理器初始化失败: {e}")
            logger.exception("用户容器管理器详细错误:")

        logger.info("服务初始化完成")
    except Exception as e:
        logger.error(f"服务初始化失败: {e}")
        logger.exception("详细错误信息:")

# 页面路由
@app.route('/')
def index():
    """首页 - 重定向到交易系统"""
    from flask import redirect
    return redirect('/trading')

@app.route('/trading')
def trading():
    """交易系统主页（Element Plus版本）"""
    return render_template('trading.html')

@app.route('/tools')
def tools():
    """AI工具中心页面"""
    return render_template('tools.html')

@app.route('/widget')
def widget():
    """桌面挂件页面"""
    return render_template('widget.html')

@app.route('/test')
def test_route():
    """测试路由"""
    return "Test route works!"

# 调度器API（已移至文件末尾，统一管理）

# 获取服务实例的辅助函数
def get_service_manager(service_type):
    """获取服务管理器实例"""
    try:
        if service_type == 'data_manager':
            return create_data_manager()
        elif service_type == 'db_manager':
            return get_db()
        elif service_type == 'push_notifier':
            return get_pushplus_notifier()
        else:
            return None
    except Exception as e:
        logger.error(f"获取{service_type}失败: {e}")
        return None

# 登录页面
@app.route('/login')
def login_page():
    """登录页面"""
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """用户登录API"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()

        if not username:
            return jsonify({"success": False, "error": "用户名不能为空"})

        # 用户名长度限制
        if len(username) > 20:
            return jsonify({"success": False, "error": "用户名不能超过20个字符"})

        # 用户名只能包含中文、英文、数字、下划线
        import re
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$', username):
            return jsonify({"success": False, "error": "用户名只能包含中文、英文、数字、下划线"})

        # 保存到Session
        session['user_session_id'] = username
        session['username'] = username
        session.permanent = True

        # ✅ 创建用户容器（包含独立的Scheduler）
        from src.core.user_container import get_container_manager
        from scheduler import StockScheduler

        container_manager = get_container_manager()
        user_container = container_manager.get_or_create(username)

        # ✅ 启动用户的Scheduler
        if user_container.scheduler_instance is None:
            user_container.scheduler_instance = StockScheduler(session_id=username)
            user_container.scheduler_instance.start()
            logger.info(f"🚀 [{username[:8]}...] 启动用户Scheduler")

        logger.info(f"🆕 用户登录: {username[:8]}...")

        return jsonify({"success": True, "username": username})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """用户登出API"""
    try:
        username = session.get('username', 'unknown')
        session.clear()
        logger.info(f"👋 用户登出: {username}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# API路由
@app.route('/api/user/info')
def api_user_info():
    """获取当前用户信息"""
    try:
        username = session.get('username', 'unknown')
        user_session_id = session.get('user_session_id', 'unknown')
        cookie_username = request.cookies.get('username', 'none')

        # 查询用户数据统计
        dbm = get_service_manager('db_manager')
        user_stats = {
            'candidates': 0,
            'positions': 0,
            'transactions': 0,
            'strategies': 0
        }

        if dbm:
            try:
                with dbm.get_session() as db_session:
                    from src.database.models import StrategyWeight
                    user_stats['candidates'] = db_session.query(Candidate).filter(
                        Candidate.session_id == user_session_id
                    ).count()
                    user_stats['positions'] = db_session.query(Position).filter(
                        Position.session_id == user_session_id
                    ).count()
                    user_stats['transactions'] = db_session.query(Transaction).filter(
                        Transaction.session_id == user_session_id
                    ).count()
                    user_stats['strategies'] = db_session.query(StrategyWeight).filter(
                        StrategyWeight.session_id == user_session_id
                    ).count()
            except Exception as e:
                logger.error(f"查询用户数据失败: {e}")

        return jsonify({
            "success": True,
            "username": username,
            "user_id": user_session_id,
            "cookie_exists": cookie_username != 'none',
            "stats": user_stats
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/status')
def api_status():
    """获取系统状态"""
    try:
        # 加载环境变量
        from dotenv import load_dotenv
        load_dotenv()

        # 数据源状态
        dm = get_service_manager('data_manager')
        data_source_status = {}
        if dm:
            data_source_status = dm.get_status()

        # 数据库状态
        dbm = get_service_manager('db_manager')
        db_status = {"status": "connected"}
        if dbm:
            try:
                with dbm.get_session() as session:
                    # 检查数据库连接
                    candidate_count = session.query(Candidate).count()
                    position_count = session.query(Position).count()
                    transaction_count = session.query(Transaction).count()

                    db_status.update({
                        "candidates": candidate_count,
                        "positions": position_count,
                        "transactions": transaction_count
                    })
            except Exception as e:
                db_status = {"status": "error", "error": str(e)}

        # 推送服务状态
        pn = get_service_manager('push_notifier')
        notification_status = {"status": "configured"}
        if pn:
            notification_status.update({
                "token_configured": bool(pn.token),
                "topic_configured": bool(pn.topic)
            })

        return jsonify({
            "success": True,
            "data_sources": data_source_status,
            "database": db_status,
            "notifications": notification_status,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/data_sources/test')
def api_test_data_source():
    """测试数据源"""
    source = request.args.get('source', 'zhitu')
    method = request.args.get('method', 'stock_info')
    stock_code = request.args.get('stock_code', '600000')

    try:
        # 动态获取数据源管理器
        dm = get_service_manager('data_manager')
        if not dm:
            return jsonify({"success": False, "error": "数据源管理器初始化失败"})

        # 创建异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 执行异步请求
        if source and source != 'auto':
            # 强制使用指定的数据源
            response = loop.run_until_complete(dm._execute_request(
                getattr(DataSource, source.upper()),
                method,
                {'stock_code': stock_code}
            ))
        else:
            # 自动选择最佳数据源
            if method == 'stock_info':
                response = loop.run_until_complete(dm.get_stock_info(stock_code))
            elif method == 'realtime_quote':
                response = loop.run_until_complete(dm.get_realtime_quote(stock_code))
            elif method == 'limit_up_stocks':
                response = loop.run_until_complete(dm.get_limit_up_stocks())
            else:
                response = loop.run_until_complete(dm.get_data(method, {'stock_code': stock_code}))

        loop.close()

        return jsonify({
            "success": response.success,
            "data": response.data,
            "source": response.source.value if response.source else None,
            "response_time": response.response_time,
            "cached": response.cached,
            "error": response.error
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/database/tables')
def api_database_tables():
    """获取数据库表信息"""
    try:
        # 动态获取数据库管理器
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as session:
            # 获取各表的记录数
            tables_info = {
                "candidates": session.query(Candidate).count(),
                "positions": session.query(Position).count(),
                "transactions": session.query(Transaction).count(),
                "market_sentiments": session.query(MarketSentiment).count(),
                "system_configs": session.query(SystemConfig).count()
            }

            # 获取最新的几条记录
            recent_candidates = []
            for candidate in session.query(Candidate).order_by(Candidate.recommend_time.desc()).limit(5).all():
                recent_candidates.append({
                    "stock_code": candidate.stock_code,
                    "stock_name": candidate.stock_name,
                    "strategy_name": candidate.strategy_name,
                    "final_score": float(candidate.final_score) if candidate.final_score else 0,
                    "ceo_decision": candidate.ceo_decision,
                    "recommend_time": candidate.recommend_time.isoformat() if candidate.recommend_time else None
                })

            current_positions = []
            for position in session.query(Position).filter(Position.status == 'holding').all():
                current_positions.append({
                    "stock_code": position.stock_code,
                    "stock_name": position.stock_name,
                    "buy_price": float(position.buy_price) if position.buy_price else 0,
                    "quantity": position.quantity,
                    "profit_loss": float(position.profit_loss) if position.profit_loss else 0,
                    "profit_loss_ratio": float(position.profit_loss_pct) if position.profit_loss_pct else 0
                })

            return jsonify({
                "success": True,
                "tables": tables_info,
                "recent_candidates": recent_candidates,
                "current_positions": current_positions
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/database/query', methods=['POST'])
def api_database_query():
    """执行数据库查询"""
    try:
        data = request.get_json()
        table = data.get('table', 'candidates')
        limit = data.get('limit', 10)

        # 动态获取数据库管理器
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as session:
            results = []

            if table == 'candidates':
                query = session.query(Candidate).order_by(Candidate.recommend_time.desc()).limit(limit)
                for item in query.all():
                    results.append({
                        "id": item.id,
                        "stock_code": item.stock_code,
                        "stock_name": item.stock_name,
                        "strategy_name": item.strategy_name,
                        "final_score": float(item.final_score) if item.final_score else 0,
                        "ceo_decision": item.ceo_decision,
                        "recommend_time": item.recommend_time.isoformat() if item.recommend_time else None
                    })

            elif table == 'positions':
                query = session.query(Position).filter(Position.status == 'holding').limit(limit)
                for item in query.all():
                    results.append({
                        "id": item.id,
                        "stock_code": item.stock_code,
                        "stock_name": item.stock_name,
                        "buy_price": float(item.buy_price) if item.buy_price else 0,
                        "quantity": item.quantity,
                        "current_price": float(item.current_price) if item.current_price else 0,
                        "profit_loss": float(item.profit_loss) if item.profit_loss else 0,
                        "buy_date": item.buy_date.isoformat() if item.buy_date else None
                    })

            elif table == 'transactions':
                query = session.query(Transaction).order_by(Transaction.trade_date.desc(), Transaction.trade_time.desc()).limit(limit)
                for item in query.all():
                    results.append({
                        "id": item.id,
                        "stock_code": item.stock_code,
                        "stock_name": item.stock_name,
                        "trade_type": item.trade_type,
                        "trade_price": float(item.price) if item.price else 0,
                        "quantity": item.quantity,
                        "trade_amount": float(item.amount) if item.amount else 0,
                        "profit_loss": float(item.profit_loss) if item.profit_loss else 0,
                        "trade_time": item.trade_time.isoformat() if item.trade_time else None,
                        "trade_date": item.trade_date.isoformat() if item.trade_date else None
                    })

        return jsonify({
            "success": True,
            "data": results,
            "table": table,
            "count": len(results)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/notifications/test', methods=['POST'])
def api_test_notification():
    """测试推送功能"""
    try:
        data = request.get_json()
        notification_type = data.get('type', 'message')

        # 动态获取推送通知器
        pn = get_service_manager('push_notifier')
        if not pn:
            return jsonify({"success": False, "error": "推送服务初始化失败"})

        result = None

        if notification_type == 'message':
            title = data.get('title', '测试消息')
            content = data.get('content', '这是一条测试消息')
            result = pn.send_message(title=title, content=content)

        elif notification_type == 'stock_recommendation':
            candidates = data.get('candidates', [{
                "stock_code": "600000",
                "stock_name": "浦发银行",
                "final_score": 85.5,
                "ceo_decision": "买入",
                "position_size": "10%",
                "reasoning": "测试推荐"
            }])
            result = pn.send_stock_recommendation(candidates)

        elif notification_type == 'risk_alert':
            alert_data = data.get('alert_data', {
                "stock_code": "600000",
                "stock_name": "浦发银行",
                "current_price": 10.50,
                "buy_price": 11.00,
                "profit_loss_pct": -4.55,
                "alert_type": "测试预警",
                "message": "测试预警消息",
                "suggestion": "建议关注"
            })
            result = pn.send_risk_alert(alert_data)

        return jsonify({
            "success": result.get("code") == 200 if result else False,
            "data": result,
            "message": "推送成功" if result and result.get("code") == 200 else "推送失败"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/notifications/history')
def api_notification_history():
    """获取推送历史"""
    try:
        # 这里可以添加推送历史查询逻辑
        # 目前返回模拟数据
        return jsonify({
            "success": True,
            "data": [
                {
                    "id": 1,
                    "type": "股票推荐",
                    "title": "今日推荐2只股票",
                    "status": "成功",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/recommendations')
def api_recommendations():
    """获取股票推荐列表（用户隔离）"""
    try:
        # ✅ 获取当前用户session_id
        user_session_id = session.get('user_session_id', 'default')

        # 参数解析
        track = request.args.get('track', 'all')
        decision = request.args.get('decision', 'all')
        approved = request.args.get('approved', 'all')
        date_range = request.args.get('date_range', 'today')
        strategy = request.args.get('strategy', 'all')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        sort_by = request.args.get('sort_by', 'recommend_time')
        sort_order = request.args.get('sort_order', 'desc')

        # 获取数据库管理器
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as db_session:
            # ✅ 导入交易日判断工具
            from datetime import timedelta
            from src.utils.trading_calendar import is_trading_day

            # ✅ 构建查询（添加session_id过滤）
            query = db_session.query(Candidate).filter(
                Candidate.session_id == user_session_id
            )

            # 日期筛选
            if date_range == 'today':
                query = query.filter(func.date(Candidate.recommend_time) == date.today())
            elif date_range == '3days':
                # ✅ 修复：使用日期而不是时间戳，确保包含完整的3天数据
                start_date = (datetime.now() - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(Candidate.recommend_time >= start_date)
            elif date_range == '7days':
                # ✅ 修复：使用日期而不是时间戳，确保包含完整的7天数据
                start_date = (datetime.now() - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(Candidate.recommend_time >= start_date)

            # 推荐渠道筛选
            if track != 'all':
                query = query.filter(Candidate.recommend_track == track)

            # CEO决策筛选
            if decision != 'all':
                query = query.filter(Candidate.ceo_decision == decision)

            # CRO审批筛选
            if approved != 'all':
                approved_bool = approved.lower() == 'true'
                query = query.filter(Candidate.cro_approved == approved_bool)

            # 策略筛选
            if strategy != 'all':
                query = query.filter(Candidate.strategy_name == strategy)

            # 排序
            if hasattr(Candidate, sort_by):
                sort_column = getattr(Candidate, sort_by)
                if sort_order == 'desc':
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())

            # 查询所有符合条件的推荐
            all_candidates = query.all()

            # ✅ 过滤非交易日的推荐
            filtered_candidates = []
            for cand in all_candidates:
                recommend_date = cand.recommend_time.date()
                if is_trading_day(recommend_date):
                    filtered_candidates.append(cand)

            # ✅ 统计数据（基于过滤后的结果）
            total = len(filtered_candidates)

            # 统计今天的推荐（只统计交易日）
            today = date.today()
            if is_trading_day(today):
                track1_count = db_session.query(Candidate).filter(
                    Candidate.session_id == user_session_id,
                    Candidate.recommend_track == 'track1_tail',
                    func.date(Candidate.recommend_time) == today
                ).count()
                track2_count = db_session.query(Candidate).filter(
                    Candidate.session_id == user_session_id,
                    Candidate.recommend_track == 'track2_next',
                    func.date(Candidate.recommend_time) == today
                ).count()
                approved_count = db_session.query(Candidate).filter(
                    Candidate.session_id == user_session_id,
                    Candidate.cro_approved == True,
                    func.date(Candidate.recommend_time) == today
                ).count()
            else:
                track1_count = 0
                track2_count = 0
                approved_count = 0

            # 平均分数（基于过滤后的结果）
            avg_score = sum([c.final_score or 0 for c in filtered_candidates]) / len(filtered_candidates) if filtered_candidates else 0

            # 分页（在过滤后的结果上分页）
            candidates = filtered_candidates[offset:offset+limit]

            # 批量获取实时价格（包含推荐后最高价）
            stock_codes = [cand.stock_code for cand in candidates]
            prices_dict = {}

            if stock_codes:
                try:
                    from src.tools.zhitu_api import ZhituAPI
                    import signal

                    # ✅ 设置超时（5秒）
                    def timeout_handler(signum, frame):
                        raise TimeoutError("批量获取实时价格超时")

                    # Windows不支持signal.alarm，使用try-except包裹
                    try:
                        zhitu = ZhituAPI()
                        # 使用券商数据源批量获取实时价格
                        prices_data = zhitu.get_real_time_multi_broker(stock_codes)
                        if prices_data:
                            for stock_code, price_info in prices_data.items():
                                if price_info and 'current_price' in price_info:
                                    prices_dict[stock_code] = {
                                        'current_price': float(price_info['current_price']),
                                        'change_pct': float(price_info.get('change_pct', 0)),
                                        'high_price': float(price_info.get('high_price', 0))  # 今日最高价（暂时保留）
                                    }
                    except TimeoutError:
                        logger.warning("批量获取实时价格超时，跳过")
                except Exception as e:
                    logger.error(f"批量获取实时价格失败: {e}")

            # ✅ 优化：跳过K线数据获取（太慢，容易超时）
            # 计算推荐后最高价和次日最高价
            # logger.info(f"⚠️ 跳过K线数据获取（性能优化）")

            # 直接跳过K线数据获取
            if False:  # ❌ 禁用K线数据获取
                for candidate in candidates:
                    stock_code = candidate.stock_code
                    recommend_time = candidate.recommend_time

                    # 即使prices_dict为空，也要尝试获取K线数据
                    if recommend_time:
                        # 如果stock_code不在prices_dict中，先初始化
                        if stock_code not in prices_dict:
                            prices_dict[stock_code] = {}
                        try:
                            from src.tools.zhitu_api import ZhituAPI
                            zhitu = ZhituAPI()

                            # 转换股票代码格式
                            stock_symbol = f"{stock_code}.{'SH' if stock_code.startswith('6') else 'SZ'}"

                            # 获取推荐日期（用于计算次日）
                            recommend_date = recommend_time.date()

                            # 获取最新的5分钟K线数据（使用最新分时交易API，速度更快）
                            kline_data = zhitu.get_latest_timeframe(
                                stock_symbol=stock_symbol,
                                timeframe='5',  # 5分钟K线
                                adjust_type='n',
                                limit=100  # 获取最新100条，覆盖今天全天（一天最多48条5分钟K线）
                            )

                            # 计算推荐后最高价
                            high_after_recommend = None
                            if kline_data:
                                # 筛选推荐时间之后的K线
                                after_recommend = []
                                for k in kline_data:
                                    try:
                                        # 尝试解析时间（可能包含或不包含时分秒）
                                        k_time_str = k['t']
                                        if ' ' in k_time_str:
                                            k_time = datetime.strptime(k_time_str, '%Y-%m-%d %H:%M:%S')
                                        else:
                                            k_time = datetime.strptime(k_time_str, '%Y-%m-%d')

                                        if k_time >= recommend_time:
                                            after_recommend.append(k)
                                    except Exception as e:
                                        print(f"解析K线时间失败 {k['t']}: {e}")
                                        continue

                                if after_recommend:
                                    high_after_recommend = max([float(k['h']) for k in after_recommend])

                            # ✅ 新增：同时考虑当前实时价格（因为当前K线可能还没收盘）
                            current_price = prices_dict.get(stock_code, {}).get('current_price')
                            if current_price and recommend_time.date() == date.today():
                                # 只有推荐日期是今天，才考虑当前价格
                                if high_after_recommend is None:
                                    high_after_recommend = current_price
                                else:
                                    high_after_recommend = max(high_after_recommend, current_price)

                            # 获取次日最高价
                            next_day = recommend_date + timedelta(days=1)
                            next_day_kline = zhitu.get_latest_timeframe(
                                stock_symbol=stock_symbol,
                                timeframe='d',  # 日K线
                                adjust_type='n',
                                limit=1
                            )

                            next_day_high = None
                            if next_day_kline and len(next_day_kline) > 0:
                                try:
                                    # 检查是否是次日数据（时间格式可能包含或不包含时分秒）
                                    k_time_str = next_day_kline[0]['t']
                                    if ' ' in k_time_str:
                                        kline_date = datetime.strptime(k_time_str, '%Y-%m-%d %H:%M:%S').date()
                                    else:
                                        kline_date = datetime.strptime(k_time_str, '%Y-%m-%d').date()

                                    if kline_date == next_day:
                                        next_day_high = float(next_day_kline[0]['h'])
                                except Exception as e:
                                    print(f"解析次日K线时间失败 {next_day_kline[0]['t']}: {e}")

                            # 更新prices_dict
                            prices_dict[stock_code]['high_after_recommend'] = high_after_recommend
                            prices_dict[stock_code]['next_day_high'] = next_day_high

                        except Exception as e:
                            print(f"计算推荐后最高价失败 {stock_code}: {e}")

            # 序列化
            results = []
            for candidate in candidates:
                # 获取当前价、涨幅、推荐后最高价、次日最高价
                price_info = prices_dict.get(candidate.stock_code, {})
                current_price = price_info.get('current_price')
                change_pct = price_info.get('change_pct')
                high_after_recommend = price_info.get('high_after_recommend')  # 推荐后最高价
                next_day_high = price_info.get('next_day_high')  # 次日最高价

                results.append({
                    "id": candidate.id,
                    "stock_code": candidate.stock_code,
                    "stock_name": candidate.stock_name,
                    "recommend_time": candidate.recommend_time.isoformat() if candidate.recommend_time else None,
                    "recommend_track": candidate.recommend_track,
                    "strategy_name": candidate.strategy_name,
                    "final_score": float(candidate.final_score) if candidate.final_score else 0,
                    "cto_score": float(candidate.cto_score) if candidate.cto_score else 0,
                    "cfo_score": float(candidate.cfo_score) if candidate.cfo_score else 0,
                    "cmo_score": float(candidate.cmo_score) if candidate.cmo_score else 0,
                    "cso_score": float(candidate.cso_score) if candidate.cso_score else 0,
                    "ceo_decision": candidate.ceo_decision,
                    "ceo_reason": candidate.ceo_reason,
                    "cro_approved": candidate.cro_approved,
                    "cro_risk_level": candidate.cro_risk_level,
                    "recommend_price": float(candidate.recommend_price) if candidate.recommend_price else None,
                    "current_price": current_price,  # 当前价
                    "change_pct": change_pct,  # 涨跌幅
                    "high_after_recommend": high_after_recommend,  # 推荐后最高价
                    "next_day_high": next_day_high,  # 次日最高价
                    "target_price": float(candidate.target_price) if candidate.target_price else None,
                    "can_sell_date": candidate.can_sell_date.isoformat() if candidate.can_sell_date else None
                })

            return jsonify({
                "success": True,
                "data": {
                    "summary": {
                        "total_count": total,
                        "track1_count": track1_count,
                        "track2_count": track2_count,
                        "approved_count": approved_count,
                        "avg_score": float(avg_score)
                    },
                    "candidates": results,
                    "pagination": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "has_more": (offset + limit) < total
                    }
                }
            })
    except Exception as e:
        logger.exception("获取推荐数据失败:")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/positions')
def api_positions():
    """获取持仓列表（用户隔离）"""
    try:
        # ✅ 获取当前用户session_id
        user_session_id = session.get('user_session_id', 'default')

        # 获取数据库管理器
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as db_session:
            # ✅ 查询当前持仓（添加session_id过滤）
            positions = db_session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'holding'
            ).all()

            # 计算统计数据
            total_stocks = len(positions)
            total_market_value = 0
            total_profit_loss = 0
            profit_stocks = 0
            loss_stocks = 0

            results = []
            risk_alerts = []

            for position in positions:
                # 计算市值和盈亏
                market_value = (position.current_price or position.buy_price) * position.quantity
                total_market_value += market_value

                pnl = position.profit_loss or 0
                total_profit_loss += pnl

                if pnl > 0:
                    profit_stocks += 1
                elif pnl < 0:
                    loss_stocks += 1

                # 检查是否可卖 (T+1)
                can_sell_today = position.can_sell_date <= date.today() if position.can_sell_date else False

                # 风险预警
                pnl_pct = position.profit_loss_pct or 0
                if pnl_pct < -5:
                    risk_alerts.append({
                        "stock_code": position.stock_code,
                        "stock_name": position.stock_name,
                        "alert_type": "loss_warning" if pnl_pct > -8 else "stop_loss",
                        "message": f"亏损{abs(pnl_pct):.2f}%，建议关注",
                        "current_loss_pct": pnl_pct
                    })

                results.append({
                    "id": position.id,
                    "stock_code": position.stock_code,
                    "stock_name": position.stock_name,
                    "buy_date": position.buy_date.isoformat() if position.buy_date else None,
                    "buy_time": position.buy_time.isoformat() if position.buy_time else None,
                    "buy_price": float(position.buy_price) if position.buy_price else 0,
                    "current_price": float(position.current_price) if position.current_price else float(position.buy_price),
                    "quantity": position.quantity,
                    "market_value": float(market_value),
                    "profit_loss": float(pnl),
                    "profit_loss_pct": float(pnl_pct),
                    "position_pct": float(position.position_pct) if position.position_pct else 0,
                    "strategy_used": position.strategy_used,
                    "can_sell_date": position.can_sell_date.isoformat() if position.can_sell_date else None,
                    "can_sell_today": can_sell_today,
                    "hold_days": (date.today() - position.buy_date).days if position.buy_date else 0
                })

            # 计算总收益率
            total_cost = total_market_value - total_profit_loss
            total_profit_loss_pct = (total_profit_loss / total_cost * 100) if total_cost > 0 else 0

            return jsonify({
                "success": True,
                "data": {
                    "summary": {
                        "total_stocks": total_stocks,
                        "total_market_value": total_market_value,
                        "total_profit_loss": total_profit_loss,
                        "total_profit_loss_pct": total_profit_loss_pct,
                        "profit_stocks": profit_stocks,
                        "loss_stocks": loss_stocks
                    },
                    "positions": results,
                    "risk_alerts": risk_alerts
                }
            })
    except Exception as e:
        logger.exception("获取持仓数据失败:")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/positions/sell', methods=['POST'])
def api_sell_position():
    """卖出持仓（用户隔离）"""
    try:
        # ✅ 获取当前用户的session_id
        user_session_id = session.get('user_session_id', 'default')

        data = request.get_json()
        position_id = data.get('position_id')
        sell_type = data.get('sell_type')  # 'profit' 或 'loss'

        # 确保参数类型正确
        try:
            sell_price = float(data.get('sell_price'))
            quantity = int(data.get('quantity'))
        except (TypeError, ValueError) as e:
            return jsonify({"success": False, "error": f"参数类型错误: {str(e)}"})

        if not all([position_id, sell_price, quantity]):
            return jsonify({"success": False, "error": "缺少必要参数"})

        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as db_session:
            # ✅ 查找持仓记录（添加session_id过滤）
            position = db_session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.id == position_id
            ).first()
            if not position:
                return jsonify({"success": False, "error": "持仓记录不存在或不属于当前用户"})

            if position.status != 'holding':
                return jsonify({"success": False, "error": "该持仓已卖出"})

            # 计算盈亏 - 统一转换为float避免Decimal类型错误
            buy_price_float = float(position.buy_price)

            buy_cost = buy_price_float * quantity
            sell_amount = sell_price * quantity
            profit_loss = sell_amount - buy_cost
            profit_loss_pct = (profit_loss / buy_cost * 100) if buy_cost > 0 else 0

            # 更新持仓状态
            position.status = 'sold'
            position.sell_date = date.today()
            position.sell_time = datetime.now().time()
            position.sell_price = sell_price
            position.profit_loss = profit_loss
            position.profit_loss_pct = profit_loss_pct
            position.updated_at = datetime.now()

            # ✅ 创建交易记录（添加session_id）
            transaction = Transaction(
                session_id=user_session_id,  # ✅ 添加session_id
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                trade_type='SELL',
                trade_date=date.today(),
                trade_time=datetime.now().time(),
                price=sell_price,
                quantity=quantity,
                amount=sell_amount,
                profit_loss=profit_loss,
                profit_loss_pct=profit_loss_pct,
                strategy_used=position.strategy_used,
                position_id=position.id,  # 关联持仓ID
                created_at=datetime.now()
            )

            db_session.add(transaction)
            db_session.commit()

            logger.info(f"卖出成功: {position.stock_code} {position.stock_name}, 盈亏: {profit_loss:.2f}")

            return jsonify({
                "success": True,
                "data": {
                    "position_id": position_id,
                    "stock_code": position.stock_code,
                    "stock_name": position.stock_name,
                    "sell_price": sell_price,
                    "quantity": quantity,
                    "profit_loss": profit_loss,
                    "profit_loss_pct": profit_loss_pct,
                    "sell_type": sell_type
                },
                "message": f"{'止盈' if sell_type == 'profit' else '止损'}成功"
            })

    except Exception as e:
        logger.exception("卖出操作失败:")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/positions/analyze', methods=['POST'])
def api_analyze_positions():
    """手动触发持仓AI分析（多用户容器隔离）"""
    try:
        # ✅ 获取当前用户session_id
        user_session_id = session.get('user_session_id', 'default')
        logger.info(f"🔍 [{user_session_id[:8]}...] 手动触发持仓AI分析...")

        # 检查是否有持仓
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as db_session:
            position_count = db_session.query(Position).filter(
                Position.session_id == user_session_id,
                Position.status == 'holding'
            ).count()

            if position_count == 0:
                return jsonify({"success": False, "error": "当前无持仓，无需分析"})

        # ✅ 使用UserContainerManager管理用户容器
        from src.core.user_container import get_container_manager
        from src.crews.position_monitor_crew import create_position_monitor_crew

        container_manager = get_container_manager()

        # ✅ 获取或创建用户容器
        user_container = container_manager.get_or_create(user_session_id)

        # ✅ 使用用户级锁
        if not user_container.task_lock.acquire(blocking=False):
            logger.warning(f"⚠️ [{user_session_id[:8]}...] 您有任务正在运行")
            return jsonify({
                "success": False,
                "error": "您有任务正在运行，请稍后再试"
            })

        try:
            # ✅ 设置当前session_id（使用contextvars）
            container_manager.set_current_session(user_session_id)

            # ✅ 标记容器正在运行
            container_manager.mark_running(user_session_id, True)

            # ✅ 创建或复用持仓监控Crew实例
            if user_container.position_crew_instance is None:
                user_container.position_crew_instance = create_position_monitor_crew(user_session_id)
                logger.info(f"🆕 [{user_session_id[:8]}...] 创建新持仓监控Crew实例")
            else:
                logger.info(f"♻️ [{user_session_id[:8]}...] 复用现有持仓监控Crew实例")

            # ✅ 运行持仓监控Crew
            from src.crews.position_monitor_crew import run_position_monitor
            result = run_position_monitor()

            logger.success(f"✅ [{user_session_id[:8]}...] 手动触发持仓AI分析完成")

            return jsonify({
                "success": True,
                "message": "AI分析完成",
                "result": str(result)
            })
        finally:
            # ✅ 标记容器运行完成
            container_manager.mark_running(user_session_id, False)

            # ✅ 释放用户级锁
            user_container.task_lock.release()

    except Exception as e:
        logger.error(f"手动触发持仓AI分析失败: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/positions/add_test_data', methods=['POST'])
def api_add_test_positions():
    """添加测试持仓数据"""
    try:
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as session:
            # 检查是否已有持仓
            existing = session.query(Position).filter(Position.status == 'holding').count()
            if existing > 0:
                return jsonify({"success": False, "error": "已存在持仓数据，无需添加测试数据"})

            # 添加3个测试持仓
            test_positions = [
                {
                    "stock_code": "600036",
                    "stock_name": "招商银行",
                    "buy_price": 36.85,
                    "current_price": 38.50,
                    "quantity": 1000,
                    "strategy_used": "龙头战法"
                },
                {
                    "stock_code": "601318",
                    "stock_name": "中国平安",
                    "buy_price": 42.50,
                    "current_price": 40.20,
                    "quantity": 800,
                    "strategy_used": "低吸埋伏"
                },
                {
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "buy_price": 1688.00,
                    "current_price": 1720.50,
                    "quantity": 20,
                    "strategy_used": "题材轮动"
                }
            ]

            from datetime import timedelta
            for i, pos_data in enumerate(test_positions):
                buy_cost = pos_data['buy_price'] * pos_data['quantity']
                current_value = pos_data['current_price'] * pos_data['quantity']
                profit_loss = current_value - buy_cost
                profit_loss_pct = (profit_loss / buy_cost * 100) if buy_cost > 0 else 0

                position = Position(
                    stock_code=pos_data['stock_code'],
                    stock_name=pos_data['stock_name'],
                    buy_date=date.today() - timedelta(days=i+1),
                    buy_time=datetime.now().time(),
                    buy_price=pos_data['buy_price'],
                    quantity=pos_data['quantity'],
                    current_price=pos_data['current_price'],
                    market_value=current_value,
                    cost_basis=buy_cost,
                    profit_loss=profit_loss,
                    profit_loss_pct=profit_loss_pct,
                    position_pct=30 - i*5,
                    status='holding',
                    strategy_used=pos_data['strategy_used'],
                    can_sell_date=date.today(),
                    created_at=datetime.now()
                )
                session.add(position)

            session.commit()
            logger.info("测试持仓数据添加成功")

            return jsonify({
                "success": True,
                "message": f"成功添加{len(test_positions)}个测试持仓"
            })

    except Exception as e:
        logger.exception("添加测试数据失败:")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/transactions')
def api_transactions():
    """获取交易历史"""
    try:
        # 参数解析 - 支持新旧两种参数格式
        session_id = request.args.get('session_id', 'default')

        # 新格式参数
        trade_type_new = request.args.get('type', '')  # 'buy' 或 'sell'
        start_date_str = request.args.get('start_date', '')
        end_date_str = request.args.get('end_date', '')

        # 旧格式参数（向后兼容）
        trade_type = request.args.get('trade_type', 'all')
        pnl_status = request.args.get('pnl_status', 'all')
        strategy = request.args.get('strategy', 'all')
        date_range = request.args.get('date_range', '30days')
        sort_by = request.args.get('sort_by', 'trade_date')
        limit = int(request.args.get('limit', 100))

        # 获取数据库管理器
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as session:
            # 构建查询
            query = session.query(Transaction)

            # 日期筛选 - 优先使用新格式
            from datetime import timedelta, datetime
            if start_date_str and end_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    query = query.filter(Transaction.trade_date >= start_date, Transaction.trade_date <= end_date)
                except ValueError:
                    pass  # 日期格式错误，忽略
            elif date_range == '7days':
                query = query.filter(Transaction.trade_date >= date.today() - timedelta(days=7))
            elif date_range == '30days':
                query = query.filter(Transaction.trade_date >= date.today() - timedelta(days=30))
            elif date_range == '90days':
                query = query.filter(Transaction.trade_date >= date.today() - timedelta(days=90))

            # 交易类型筛选 - 优先使用新格式
            if trade_type_new:
                query = query.filter(Transaction.trade_type == trade_type_new.upper())
            elif trade_type != 'all':
                query = query.filter(Transaction.trade_type == trade_type)

            # 盈亏筛选 (仅对卖出交易)
            if pnl_status == 'profit':
                query = query.filter(Transaction.trade_type == 'SELL', Transaction.profit_loss > 0)
            elif pnl_status == 'loss':
                query = query.filter(Transaction.trade_type == 'SELL', Transaction.profit_loss < 0)

            # 策略筛选
            if strategy != 'all':
                query = query.filter(Transaction.strategy_used == strategy)

            # 排序
            if hasattr(Transaction, sort_by):
                query = query.order_by(getattr(Transaction, sort_by).desc())

            # 分页
            transactions = query.limit(limit).all()

            # 计算统计数据
            total_trades = len(transactions)
            sell_transactions = [t for t in transactions if t.trade_type == 'SELL']

            profit_trades = len([t for t in sell_transactions if (t.profit_loss or 0) > 0])
            loss_trades = len([t for t in sell_transactions if (t.profit_loss or 0) < 0])

            total_profit = sum([t.profit_loss for t in sell_transactions if (t.profit_loss or 0) > 0])
            total_loss = sum([t.profit_loss for t in sell_transactions if (t.profit_loss or 0) < 0])
            net_profit = total_profit + total_loss

            win_rate = (profit_trades / len(sell_transactions) * 100) if len(sell_transactions) > 0 else 0

            avg_profit = total_profit / profit_trades if profit_trades > 0 else 0
            avg_loss = total_loss / loss_trades if loss_trades > 0 else 0
            profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0

            max_profit = max([t.profit_loss for t in sell_transactions if t.profit_loss], default=0)
            max_loss = min([t.profit_loss for t in sell_transactions if t.profit_loss], default=0)

            # 平均收益率
            avg_profit_pct = sum([t.profit_loss / t.amount * 100 for t in sell_transactions if t.profit_loss and t.amount]) / len(sell_transactions) if len(sell_transactions) > 0 else 0

            # 序列化
            results = []
            for tx in transactions:
                profit_loss_pct = None
                if tx.trade_type == 'SELL' and tx.profit_loss and tx.amount:
                    profit_loss_pct = (tx.profit_loss / tx.amount) * 100

                results.append({
                    "id": tx.id,
                    "trade_date": tx.trade_date.isoformat() if tx.trade_date else None,
                    "trade_time": tx.trade_time.isoformat() if tx.trade_time else None,
                    "stock_code": tx.stock_code,
                    "stock_name": tx.stock_name,
                    "trade_type": tx.trade_type,
                    "price": round(float(tx.price), 3) if tx.price else 0,  # ✅ 保留3位小数
                    "quantity": tx.quantity,
                    "amount": float(tx.amount) if tx.amount else 0,
                    "profit_loss": float(tx.profit_loss) if tx.profit_loss else None,
                    "profit_loss_pct": float(profit_loss_pct) if profit_loss_pct else None,
                    "strategy_used": tx.strategy_used
                })

            # 图表数据 - 累计盈亏曲线
            cumulative_pnl = []
            cumulative = 0
            sell_txs_sorted = sorted(sell_transactions, key=lambda t: t.trade_date)
            for tx in sell_txs_sorted:
                cumulative += (tx.profit_loss or 0)
                cumulative_pnl.append({
                    "date": tx.trade_date.isoformat() if tx.trade_date else None,
                    "pnl": cumulative
                })

            # 策略贡献度
            strategy_contribution = {}
            for tx in sell_transactions:
                if tx.profit_loss and tx.strategy_used:
                    strategy_contribution[tx.strategy_used] = strategy_contribution.get(tx.strategy_used, 0) + tx.profit_loss

            # 返回格式 - 支持新旧两种格式
            response_data = {
                "success": True,
                "transactions": results,  # 新格式：直接返回交易列表
                "data": {  # 旧格式：保持向后兼容
                    "summary": {
                        "total_trades": total_trades,
                        "profit_trades": profit_trades,
                        "loss_trades": loss_trades,
                        "win_rate": win_rate,
                        "total_profit": total_profit,
                        "total_loss": total_loss,
                        "net_profit": net_profit,
                        "avg_profit": avg_profit,
                        "avg_loss": avg_loss,
                        "avg_profit_pct": avg_profit_pct,
                        "profit_loss_ratio": profit_loss_ratio,
                        "max_profit": max_profit,
                        "max_loss": max_loss
                    },
                    "transactions": results,
                    "chart_data": {
                        "cumulative_pnl": cumulative_pnl,
                        "strategy_contribution": strategy_contribution
                    }
                }
            }

            return jsonify(response_data)
    except Exception as e:
        logger.exception("获取交易数据失败:")
        return jsonify({"success": False, "error": str(e)})

def get_mock_dashboard_data():
    """获取模拟仪表板数据（用于演示）"""
    from datetime import timedelta
    import random

    # 模拟核心指标
    metrics = {
        "total_market_value": 156800.00,
        "today_pnl": 3520.00,
        "win_rate": 65.5,
        "profit_trades": 21,
        "loss_trades": 11,
        "total_return_pct": 12.8,
        "net_profit": 18560.00
    }

    # 模拟累计盈亏曲线（最近30天）
    pnl_curve = []
    base_pnl = 10000
    for i in range(30):
        base_pnl += random.randint(-500, 1000)
        target_date = date.today() - timedelta(days=29-i)
        pnl_curve.append({
            "date": target_date.strftime("%m-%d"),
            "pnl": float(base_pnl)
        })

    # 模拟持仓分布
    position_distribution = [
        {"stock_code": "600000 浦发银行", "value": 35000},
        {"stock_code": "601318 中国平安", "value": 28000},
        {"stock_code": "600519 贵州茅台", "value": 42000},
        {"stock_code": "000001 平安银行", "value": 22000},
        {"stock_code": "601166 兴业银行", "value": 18000},
        {"stock_code": "600036 招商银行", "value": 11800}
    ]

    # 模拟策略绩效
    strategy_performance = {
        "龙头战法": 5600,
        "低吸埋伏": 3200,
        "题材轮动": 4800,
        "异常波动跟踪": 2100,
        "尾盘急拉": 1850,
        "新闻驱动": 1010
    }

    # 模拟交易量趋势
    volume_trend = []
    for i in range(7):
        target_date = date.today() - timedelta(days=6-i)
        volume_trend.append({
            "date": target_date.strftime("%m-%d"),
            "count": random.randint(3, 12)
        })

    charts = {
        "pnl_curve": pnl_curve,
        "position_distribution": position_distribution,
        "strategy_performance": strategy_performance,
        "volume_trend": volume_trend
    }

    # 模拟今日推荐
    recommendations = [
        {
            "stock_code": "600036",
            "stock_name": "招商银行",
            "strategy_name": "龙头战法",
            "final_score": 88.5,
            "ceo_decision": "STRONG_BUY",
            "recommend_price": 36.85
        },
        {
            "stock_code": "601318",
            "stock_name": "中国平安",
            "strategy_name": "低吸埋伏",
            "final_score": 82.3,
            "ceo_decision": "BUY",
            "recommend_price": 42.50
        },
        {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "strategy_name": "题材轮动",
            "final_score": 91.2,
            "ceo_decision": "STRONG_BUY",
            "recommend_price": 1688.00
        },
        {
            "stock_code": "000001",
            "stock_name": "平安银行",
            "strategy_name": "异常波动跟踪",
            "final_score": 76.8,
            "ceo_decision": "BUY",
            "recommend_price": 12.35
        },
        {
            "stock_code": "601166",
            "stock_name": "兴业银行",
            "strategy_name": "尾盘急拉",
            "final_score": 68.5,
            "ceo_decision": "HOLD",
            "recommend_price": 15.20
        }
    ]

    # 模拟风险预警
    alerts = [
        {
            "stock_code": "600000",
            "stock_name": "浦发银行",
            "alert_type": "loss_warning",
            "message": "持仓亏损5.2%，建议关注",
            "current_loss_pct": -5.2
        },
        {
            "stock_code": "601166",
            "stock_name": "兴业银行",
            "alert_type": "stop_loss",
            "message": "持仓亏损8.5%，建议止损",
            "current_loss_pct": -8.5
        }
    ]

    return {
        "metrics": metrics,
        "charts": charts,
        "recommendations": recommendations,
        "alerts": alerts
    }

@app.route('/api/dashboard')
def api_dashboard():
    """获取仪表板聚合数据"""
    try:
        dbm = get_service_manager('db_manager')
        if not dbm:
            return jsonify({"success": False, "error": "数据库管理器初始化失败"})

        with dbm.get_session() as session:
            from datetime import timedelta

            # ========== 检查是否有数据 ==========
            has_data = session.query(Position).count() > 0 or session.query(Transaction).count() > 0

            # 如果没有数据，返回模拟数据
            if not has_data:
                logger.info("数据库无数据，返回模拟数据")
                return jsonify({
                    "success": True,
                    "data": get_mock_dashboard_data()
                })

            # ========== 核心指标 ==========
            # 持仓数据
            positions = session.query(Position).filter(Position.status == 'holding').all()
            total_market_value = sum([(p.current_price or p.buy_price) * p.quantity for p in positions])
            total_profit_loss = sum([p.profit_loss or 0 for p in positions])

            # 交易数据（近30天）
            recent_date = date.today() - timedelta(days=30)
            transactions = session.query(Transaction).filter(
                Transaction.trade_date >= recent_date
            ).all()

            sell_transactions = [t for t in transactions if t.trade_type == 'SELL']
            profit_trades = len([t for t in sell_transactions if (t.profit_loss or 0) > 0])
            loss_trades = len([t for t in sell_transactions if (t.profit_loss or 0) < 0])
            win_rate = (profit_trades / len(sell_transactions) * 100) if len(sell_transactions) > 0 else 0

            total_profit = sum([t.profit_loss for t in sell_transactions if (t.profit_loss or 0) > 0])
            total_loss = sum([t.profit_loss for t in sell_transactions if (t.profit_loss or 0) < 0])
            net_profit = total_profit + total_loss

            # 总收益率计算
            total_cost = total_market_value - total_profit_loss
            total_return_pct = (total_profit_loss / total_cost * 100) if total_cost > 0 else 0

            # 今日盈亏（简化版，实际需要实时行情）
            today_pnl = sum([p.profit_loss or 0 for p in positions if p.buy_date == date.today()])

            metrics = {
                "total_market_value": float(total_market_value),
                "today_pnl": float(today_pnl),
                "win_rate": float(win_rate),
                "profit_trades": profit_trades,
                "loss_trades": loss_trades,
                "total_return_pct": float(total_return_pct),
                "net_profit": float(net_profit)
            }

            # ========== 图表数据 ==========
            # 1. 累计盈亏曲线
            pnl_curve = []
            cumulative = 0
            sell_txs_sorted = sorted(sell_transactions, key=lambda t: t.trade_date)
            for tx in sell_txs_sorted[-30:]:  # 最近30笔
                cumulative += (tx.profit_loss or 0)
                pnl_curve.append({
                    "date": tx.trade_date.strftime("%m-%d") if tx.trade_date else "",
                    "pnl": float(cumulative)
                })

            # 2. 持仓分布
            position_distribution = []
            for p in positions[:8]:  # 前8个持仓
                value = (p.current_price or p.buy_price) * p.quantity
                position_distribution.append({
                    "stock_code": p.stock_code,
                    "value": float(value)
                })

            # 3. 策略绩效对比
            strategy_performance = {}
            for tx in sell_transactions:
                if tx.profit_loss and tx.strategy_used:
                    strategy_performance[tx.strategy_used] = \
                        strategy_performance.get(tx.strategy_used, 0) + float(tx.profit_loss)

            # 4. 交易量趋势（近7天）
            volume_trend = []
            for i in range(7):
                target_date = date.today() - timedelta(days=6-i)
                count = len([t for t in transactions if t.trade_date == target_date])
                volume_trend.append({
                    "date": target_date.strftime("%m-%d"),
                    "count": count
                })

            charts = {
                "pnl_curve": pnl_curve,
                "position_distribution": position_distribution,
                "strategy_performance": strategy_performance,
                "volume_trend": volume_trend
            }

            # ========== 今日推荐 ==========
            recommendations = []
            today_candidates = session.query(Candidate).filter(
                func.date(Candidate.recommend_time) == date.today()
            ).order_by(Candidate.final_score.desc()).limit(5).all()

            for candidate in today_candidates:
                recommendations.append({
                    "stock_code": candidate.stock_code,
                    "stock_name": candidate.stock_name,
                    "strategy_name": candidate.strategy_name,
                    "final_score": float(candidate.final_score) if candidate.final_score else 0,
                    "ceo_decision": candidate.ceo_decision,
                    "recommend_price": float(candidate.recommend_price) if candidate.recommend_price else None
                })

            # ========== 风险预警 ==========
            alerts = []
            for position in positions:
                pnl_pct = position.profit_loss_pct or 0
                if pnl_pct < -5:
                    alerts.append({
                        "stock_code": position.stock_code,
                        "stock_name": position.stock_name,
                        "alert_type": "loss_warning" if pnl_pct > -8 else "stop_loss",
                        "message": f"持仓亏损{abs(pnl_pct):.2f}%，建议关注",
                        "current_loss_pct": float(pnl_pct)
                    })

            return jsonify({
                "success": True,
                "data": {
                    "metrics": metrics,
                    "charts": charts,
                    "recommendations": recommendations,
                    "alerts": alerts
                }
            })
    except Exception as e:
        logger.exception("获取仪表板数据失败:")
        return jsonify({"success": False, "error": str(e)})

# ==================== 调度器手动触发API ====================

@app.route('/api/scheduler/run-recommendation', methods=['POST'])
def trigger_recommendation():
    """
    手动触发股票推荐+自动买入（多用户容器隔离）

    流程：
    1. 触发AI推荐（6个Agent协作）
    2. 如果有实盘权限 → 自动买入推荐股票
    3. 如果无实盘权限 → 仅推荐，不买入
    """
    try:
        # ✅ 获取当前用户的session_id
        user_session_id = session.get('user_session_id', 'default')
        logger.info(f"🔍 [{user_session_id[:8]}...] 手动触发股票推荐+买入...")

        # ✅ 使用UserContainerManager管理用户容器
        from src.core.user_container import get_container_manager
        from src.crews.smart_recommendation_crew import create_smart_recommendation_crew

        container_manager = get_container_manager()

        # ✅ 获取或创建用户容器
        user_container = container_manager.get_or_create(user_session_id)

        # ✅ 使用用户级锁（不是全局锁）
        if not user_container.task_lock.acquire(blocking=False):
            logger.warning(f"⚠️ [{user_session_id[:8]}...] 您有任务正在运行")
            return jsonify({
                "success": False,
                "error": "您有任务正在运行，请稍后再试"
            })

        try:
            # ✅ 设置当前session_id（使用contextvars）
            container_manager.set_current_session(user_session_id)

            # ✅ 标记容器正在运行
            container_manager.mark_running(user_session_id, True)

            # ========================================
            # 步骤1：触发AI推荐
            # ========================================
            logger.info(f"🤖 [{user_session_id[:8]}...] 步骤1：触发AI推荐...")

            # ✅ 创建或复用CrewAI实例
            if user_container.crew_instance is None:
                user_container.crew_instance = create_smart_recommendation_crew(user_session_id)
                logger.info(f"🆕 [{user_session_id[:8]}...] 创建新Crew实例")
            else:
                logger.info(f"♻️ [{user_session_id[:8]}...] 复用现有Crew实例")

            # ✅ 运行CrewAI（实时显示过程，同时记录到日志）
            import io
            import sys
            import re

            # 🔴 Tee类：同时输出到终端和StringIO
            class Tee:
                def __init__(self, *files):
                    self.files = files
                def write(self, data):
                    for f in self.files:
                        f.write(data)
                        f.flush()
                def flush(self):
                    for f in self.files:
                        f.flush()

            logger.info(f"🚀 [{user_session_id[:8]}...] 开始执行CrewAI...")

            # 保存原始的stdout和stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            # 创建StringIO捕获输出
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            # 🔴 使用Tee同时输出到终端和StringIO（实时显示过程）
            sys.stdout = Tee(old_stdout, stdout_capture)
            sys.stderr = stderr_capture  # stderr只捕获，不显示（隐藏Pydantic警告）

            try:
                result = user_container.crew_instance.kickoff()

                # 获取CrewAI的输出
                crew_output = stdout_capture.getvalue()

                # 恢复stdout和stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                logger.info(f"✅ [{user_session_id[:8]}...] CrewAI执行完成，输出长度: {len(crew_output)} 字符")

                # 清理ANSI颜色代码和装饰性字符
                def clean_output(text):
                    """清理CrewAI输出中的ANSI代码和装饰性字符"""
                    # 清理ANSI颜色代码
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    text = ansi_escape.sub('', text)

                    # 清理装饰性框线字符
                    box_chars = ['│', '╭', '╰', '├', '└', '─', '╮', '╯', '┤', '┴', '┬', '┼']
                    for char in box_chars:
                        text = text.replace(char, '')

                    return text.strip()

                # 记录CrewAI输出到日志文件（清理后）
                if crew_output:
                    logger.info(f"=== [{user_session_id[:8]}...] CrewAI输出 ===")
                    for line in crew_output.split('\n'):
                        if line.strip():
                            clean_line = clean_output(line)
                            if clean_line:  # 只记录非空行
                                logger.info(f"[{user_session_id[:8]}...] {clean_line}")
                    logger.info(f"=== [{user_session_id[:8]}...] 输出结束 ===")

                    # 🔴 同时打印到终端（用户可见，保留美化格式）
                    print(crew_output)
                else:
                    logger.warning(f"⚠️ [{user_session_id[:8]}...] CrewAI输出为空！")

            except Exception as e:
                # 恢复stdout和stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                logger.error(f"❌ [{user_session_id[:8]}...] CrewAI执行异常: {e}")
                raise e

            logger.success(f"✅ [{user_session_id[:8]}...] AI推荐完成！")


            return jsonify({
                "success": True,
                "message": "股票推荐已成功运行",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "result": str(result)
            })

        finally:
            # ✅ 标记容器运行完成
            container_manager.mark_running(user_session_id, False)

            # ✅ 释放用户级锁
            user_container.task_lock.release()

    except Exception as e:
        logger.exception("手动触发推荐失败:")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/scheduler/run-monitor', methods=['POST'])
def trigger_monitor():
    """手动触发持仓监控（多用户容器隔离）"""
    try:
        # ✅ 获取当前用户session_id
        user_session_id = session.get('user_session_id', 'default')
        logger.info(f"📊 [{user_session_id[:8]}...] 手动触发持仓监控...")

        # ✅ 使用UserContainerManager获取用户Scheduler
        from src.core.user_container import get_container_manager

        container_manager = get_container_manager()
        user_container = container_manager.get_or_create(user_session_id)

        # ✅ 确保Scheduler已启动
        if user_container.scheduler_instance is None:
            from scheduler import StockScheduler
            user_container.scheduler_instance = StockScheduler(session_id=user_session_id)
            user_container.scheduler_instance.start()

        # ✅ 运行监控
        user_container.scheduler_instance.run_monitor()

        return jsonify({
            "success": True,
            "message": "持仓监控已成功运行",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logger.exception("手动触发监控失败:")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    """获取调度器状态（多用户容器隔离）"""
    try:
        # ✅ 获取当前用户session_id
        user_session_id = session.get('user_session_id', 'default')

        # ✅ 使用UserContainerManager获取用户Scheduler
        from src.core.user_container import get_container_manager

        container_manager = get_container_manager()
        user_container = container_manager.get_or_create(user_session_id)

        # ✅ 确保Scheduler已启动
        if user_container.scheduler_instance is None:
            from scheduler import StockScheduler
            user_container.scheduler_instance = StockScheduler(session_id=user_session_id)
            user_container.scheduler_instance.start()

        scheduler = user_container.scheduler_instance

        return jsonify({
            "success": True,
            "data": {
                "is_running": scheduler.is_running,
                "monitor_interval": scheduler.monitor_interval,
                "last_monitor_time": scheduler.last_monitor_time.strftime('%Y-%m-%d %H:%M:%S') if scheduler.last_monitor_time else None,
                "session_id": user_session_id[:8] + "..."
            }
        })
    except Exception as e:
        logger.exception("获取调度器状态失败:")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/containers/stats', methods=['GET'])
def get_container_stats():
    """获取用户容器统计信息"""
    try:
        from src.core.user_container import get_container_manager

        container_manager = get_container_manager()
        stats = container_manager.get_stats()

        return jsonify({
            "success": True,
            "data": stats
        })
    except Exception as e:
        logger.exception("获取容器统计失败:")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# 启动应用
if __name__ == '__main__':
    # ========================================
    # 配置日志系统（双重日志）
    # ========================================

    # 1. 配置loguru（Web应用日志）
    # 🔴 移除默认的控制台输出（避免DEBUG日志污染）
    logger.remove()

    # 🔴 只记录INFO及以上级别到文件，过滤DEBUG日志
    logger.add("logs/web_app.log", rotation="1 day", retention="7 days", level="INFO", filter=lambda record: record["level"].no >= 20)

    # 🔴 控制台只输出INFO及以上级别（过滤DEBUG日志）
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # 2. 配置标准logging（CrewAI和工具日志）
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[
            logging.StreamHandler(),  # 输出到控制台
            logging.FileHandler('logs/crewai_stock.log', encoding='utf-8')  # 输出到文件
        ]
    )

    # 🔴 降低第三方库和工具模块的日志级别（减少技术细节日志）
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # HTTP请求日志
    logging.getLogger('httpx').setLevel(logging.WARNING)  # HTTP客户端日志
    logging.getLogger('httpcore').setLevel(logging.WARNING)  # HTTP核心日志
    logging.getLogger('urllib3').setLevel(logging.WARNING)  # urllib3日志
    logging.getLogger('src.tools.data_source_manager').setLevel(logging.WARNING)  # 数据源管理器
    logging.getLogger('src.tools.zhitu_api').setLevel(logging.WARNING)  # 智兔API
    logging.getLogger('src.tools.eastmoney_crawler').setLevel(logging.WARNING)  # 东方财富爬虫
    logging.getLogger('src.tools.mcp_client').setLevel(logging.WARNING)  # MCP客户端
    logging.getLogger('src.tools.news_source_manager').setLevel(logging.WARNING)  # 新闻源管理器
    logging.getLogger('src.agents.tools.context_tools').setLevel(logging.WARNING)  # 上下文工具
    logging.getLogger('src.agents.tools.database_tools').setLevel(logging.WARNING)  # 数据库工具

    # 🔴 抑制 CrewAI 相关的详细日志
    logging.getLogger('crewai').setLevel(logging.WARNING)  # CrewAI框架
    logging.getLogger('langchain').setLevel(logging.WARNING)  # LangChain
    logging.getLogger('openai').setLevel(logging.WARNING)  # OpenAI客户端

    # ✅ 保留LiteLLM的INFO日志（显示LLM调用和回复）
    logging.getLogger('LiteLLM').setLevel(logging.INFO)

    # 3. 让loguru拦截标准logging（可选，统一到web_app.log）
    # from loguru import logger
    # import logging
    #
    # class InterceptHandler(logging.Handler):
    #     def emit(self, record):
    #         # Get corresponding Loguru level if it exists
    #         try:
    #             level = logger.level(record.levelname).name
    #         except ValueError:
    #             level = record.levelno
    #
    #         # Find caller from where originated the logged message
    #         frame, depth = logging.currentframe(), 2
    #         while frame.f_code.co_filename == logging.__file__:
    #             frame = frame.f_back
    #             depth += 1
    #
    #         logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
    #
    # logging.basicConfig(handlers=[InterceptHandler()], level=0)

    logger.info("✅ 日志系统已配置（loguru + logging）")
    logger.info("   - Web应用日志: logs/web_app.log")
    logger.info("   - CrewAI日志: logs/crewai_stock.log")

    # 初始化服务
    print("🔧 正在初始化服务...")
    init_services()

    # ✅ 启动全局新闻监控调度器
    from global_news_scheduler import get_global_news_scheduler
    global_news_scheduler = get_global_news_scheduler()
    global_news_scheduler.start()
    print("✅ 全局新闻监控调度器已启动")

    # ✅ 用户容器管理器已初始化，Scheduler按用户独立创建
    print("✅ 用户容器管理器已就绪")
    print("   - 用户登录时自动创建独立的Scheduler实例")
    print("   - 支持多用户并发运行")

    # 检查初始化状态
    print(f"✅ 数据源管理器: {'已初始化' if data_manager else '未初始化'}")
    print(f"✅ 数据库管理器: {'已初始化' if db_manager else '未初始化'}")
    print(f"✅ 推送通知器: {'已初始化' if push_notifier else '未初始化'}")

    if push_notifier:
        print(f"   - Token配置: {bool(push_notifier.token)}")
        print(f"   - Topic配置: {bool(push_notifier.topic)}")

    def run_flask():
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('WEB_PORT', 7000)),
            debug=False,
            extra_files=[],
            use_reloader=False,  # Disable reloader when running with widget to avoid multiple windows
            reloader_type='stat'
        )

    # Check if widget mode is requested (via command line arg or env var)
    import sys
    if '--widget' in sys.argv or os.getenv('LAUNCH_WIDGET', 'false').lower() == 'true':
        logger.info("🚀 启动模式: Web服务 + 桌面挂件")
        
        # Run Flask in a separate thread
        import threading
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        # Run Widget in main thread
        try:
            import webview
            import time
            
            # Wait for Flask to start
            time.sleep(2) 
            
            port = int(os.getenv('WEB_PORT', 7000))
            webview.create_window(
                'Quantum Widget',
                url=f'http://127.0.0.1:{port}/widget',
                width=320,
                height=480,
                frameless=True,
                easy_drag=True,
                on_top=True,
                transparent=True
            )
            webview.start()
        except ImportError:
            logger.error("❌ 缺少 pywebview 库，无法启动挂件。请运行 pip install pywebview")
            run_flask() # Fallback to normal run
    else:
        logger.info("🚀 启动模式: 仅Web服务")
        run_flask()
