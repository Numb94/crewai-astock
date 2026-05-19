#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K线数据API - CrewAI A-Stock V2.0

提供K线图数据接口，支持推荐点标注、止盈止损线标注

作者: AI Architect
版本: v1.0.0
日期: 2025-11-05
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from loguru import logger
from src.tools.data_source_manager import create_data_manager
from src.database.db_manager import get_db
from src.database.models import Candidate, Position
from src.utils.trading_calendar import is_trading_day, adjust_to_trading_day

# 创建蓝图
kline_api = Blueprint('kline_api', __name__, url_prefix='/api/kline')

# 数据源管理器
data_manager = create_data_manager()


@kline_api.route('/<stock_code>', methods=['GET'])
def get_kline_data(stock_code):
    """
    获取K线数据
    
    Args:
        stock_code: 股票代码（如600478）
        
    Query Parameters:
        recommend_time: 推荐时间（ISO格式，如2025-11-05T10:57:38）
        days: 天数（默认2天：推荐日+次日）
        timeframe: 分时级别（默认5分钟）
        
    Returns:
        {
            "success": true,
            "data": {
                "stock_code": "600478",
                "stock_name": "科力远",
                "recommend_time": "2025-11-05 10:57:38",
                "recommend_price": 7.74,
                "target_price": 9.87,
                "kline_data": [...],
                "markers": [...]
            }
        }
    """
    try:
        # 获取参数
        recommend_time_str = request.args.get('recommend_time')
        days = int(request.args.get('days', 2))
        timeframe = request.args.get('timeframe', '5')  # 默认5分钟K线
        
        if not recommend_time_str:
            return jsonify({
                "success": False,
                "message": "缺少推荐时间参数"
            }), 400
        
        # 解析推荐时间
        recommend_time = datetime.fromisoformat(recommend_time_str.replace('Z', '+00:00'))

        # 查询推荐记录（可选）
        db = get_db()
        stock_name = None
        recommend_price = None
        target_price = None

        with db.get_session() as session:
            candidate = session.query(Candidate).filter(
                Candidate.stock_code == stock_code,
                Candidate.recommend_time == recommend_time
            ).first()

            if candidate:
                # 如果找到推荐记录，使用推荐数据
                stock_name = candidate.stock_name
                recommend_price = float(candidate.recommend_price)
                target_price = float(candidate.target_price) if candidate.target_price else None
            else:
                # 如果没有推荐记录（如持仓监控），从持仓表查找
                position = session.query(Position).filter(
                    Position.stock_code == stock_code,
                    Position.status == 'holding'
                ).first()

                if position:
                    stock_name = position.stock_name
                    recommend_price = float(position.buy_price)
                    target_price = None  # 持仓没有止盈价
                else:
                    # 如果都没找到，使用数据源获取股票名称
                    logger.warning(f"未找到推荐或持仓记录: {stock_code}，将使用实时数据")
                    stock_name = stock_code  # 默认使用股票代码
                    recommend_price = None
                    target_price = None
        
        # 计算时间范围
        recommend_date = recommend_time.date()

        # ✅ 过滤非交易日：如果推荐日期是周末，调整到最近的交易日
        from datetime import date
        today = date.today()

        if not is_trading_day(recommend_date):
            original_date = recommend_date
            recommend_date = adjust_to_trading_day(recommend_date, direction='backward')
            # logger.info(f"📅 推荐日期是非交易日，已调整: {original_date} -> {recommend_date}")  # 🔴 注释掉INFO日志

        start_date = recommend_date

        # ✅ 修复：计算end_date时考虑周末和节假日
        # 计算需要覆盖的天数（包括周末）
        # 如果推荐日期是过去，获取到今天；如果是今天或未来，获取days天
        if recommend_date < today:
            # 推荐日期是过去，获取到今天的数据
            # ✅ 重要：智兔API的et参数不包含结束日期，需要+1天
            end_date = today + timedelta(days=1)
        else:
            # 推荐日期是今天或未来，获取days天
            # ✅ 重要：智兔API的et参数不包含结束日期，需要+1天
            end_date = recommend_date + timedelta(days=days)

        # 格式化时间参数
        start_time = start_date.strftime('%Y%m%d')
        end_time = end_date.strftime('%Y%m%d')

        # 转换股票代码格式（600478 -> 600478.SH）
        stock_symbol = f"{stock_code}.{'SH' if stock_code.startswith('6') else 'SZ'}"

        # logger.debug(f"📡 获取K线: {stock_code} [{start_time}-{end_time}] {timeframe}分钟")  # 🔴 注释掉DEBUG日志

        kline_data = data_manager.zhitu_client.get_history_timeframe(
            stock_symbol=stock_symbol,
            timeframe=timeframe,
            adjust_type='n',  # 不复权
            start_time=start_time,
            end_time=end_time
        )

        if kline_data and isinstance(kline_data, list) and len(kline_data) > 0:
            first_date = kline_data[0].get('t', 'N/A')
            last_date = kline_data[-1].get('t', 'N/A')
            # logger.debug(f"✅ 获取{len(kline_data)}条K线 [{first_date} ~ {last_date}]")  # 🔴 注释掉DEBUG日志
        else:
            logger.warning(f"⚠️ 未获取到K线数据: {stock_code}")

        if not kline_data:
            return jsonify({
                "success": False,
                "message": f"未获取到K线数据: {stock_code}"
            }), 404
        
        # 格式化K线数据
        formatted_kline = []
        for k in kline_data:
            formatted_kline.append({
                "time": k['t'],
                "open": float(k['o']),
                "high": float(k['h']),
                "low": float(k['l']),
                "close": float(k['c']),
                "volume": int(k['v'])
            })
        
        # 生成标注点
        markers = []
        
        # 推荐点标注
        markers.append({
            "time": recommend_time.strftime('%Y-%m-%d %H:%M:%S'),
            "price": recommend_price,
            "type": "recommend",
            "label": "推荐点",
            "color": "#409EFF"
        })

        # 止盈线标注
        if target_price:
            markers.append({
                "type": "line",
                "price": target_price,
                "label": "止盈价",
                "color": "#67C23A",
                "lineStyle": "dashed"
            })

        # 返回数据
        return jsonify({
            "success": True,
            "data": {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "recommend_time": recommend_time.strftime('%Y-%m-%d %H:%M:%S'),
                "recommend_price": recommend_price,
                "target_price": target_price,
                "kline_data": formatted_kline,
                "markers": markers
            }
        })
        
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return jsonify({
            "success": False,
            "message": f"获取K线数据失败: {str(e)}"
        }), 500

