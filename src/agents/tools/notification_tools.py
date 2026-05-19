#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - 推送通知工具

为CrewAI Agent提供微信推送通知能力
"""

from crewai.tools import tool
from typing import Dict
import json


@tool("发送推送通知")
def send_push_notification(title: str, content: str) -> str:
    """
    发送微信推送通知

    Args:
        title: 消息标题
        content: 消息内容

    Returns:
        发送结果(自然语言描述)
    """
    from src.utils.pushplus_notifier import get_notifier

    try:
        notifier = get_notifier()
        
        # 发送推送
        result = notifier.send_message(
            title=title,
            content=content,
            template="html"
        )
        
        if result.get('code') == 200:
            return f"✓ 推送成功: {title}"
        else:
            return f"✗ 推送失败: {result.get('msg', '未知错误')}"
            
    except Exception as e:
        return f"发送推送失败: {str(e)}"


@tool("发送股票推荐通知")
def send_stock_recommendation(recommendations: str) -> str:
    """
    发送股票推荐通知（格式化为HTML）

    Args:
        recommendations: 推荐内容（JSON字符串或文本）

    Returns:
        发送结果(自然语言描述)
    """
    from src.utils.pushplus_notifier import get_notifier
    from datetime import datetime

    try:
        notifier = get_notifier()
        
        # 尝试解析JSON
        try:
            rec_data = json.loads(recommendations)
            
            # 构建HTML内容
            html_content = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
        📈 CrewAI A-Stock 今日推荐
    </h2>

    <div style="background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <p style="margin: 5px 0;"><strong>📅 日期:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        <p style="margin: 5px 0;"><strong>📊 策略:</strong> <span style="color: #e74c3c; font-weight: bold;">{rec_data.get('strategy', 'N/A')}</span></p>
        <p style="margin: 5px 0;"><strong>🌡️ 市场状态:</strong> <span style="color: #27ae60; font-weight: bold;">{rec_data.get('market_state', 'N/A').upper()}</span></p>
    </div>
"""

            # 🔴 新增：持仓对比分析
            position_comparison = rec_data.get('position_comparison', [])
            if position_comparison:
                html_content += """
    <h3 style="color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px;">
        🔄 持仓对比分析
    </h3>
"""
                for comp in position_comparison:
                    decision = comp.get('decision', '')
                    if decision == 'KEEP_POSITION':
                        bg_color = '#d4edda'
                        icon = '✅'
                        decision_text = '保留持仓'
                    elif decision == 'SELL_AND_BUY':
                        bg_color = '#fff3cd'
                        icon = '🔄'
                        decision_text = '建议换仓'
                    else:
                        bg_color = '#f8d7da'
                        icon = '⚠️'
                        decision_text = '观望'

                    html_content += f"""
    <div style="background: {bg_color}; padding: 10px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #ffc107;">
        <p style="margin: 5px 0;"><strong>{icon} {decision_text}</strong></p>
        <p style="margin: 5px 0;">持仓：{comp.get('position_name', 'N/A')}({comp.get('position_code', 'N/A')}) - 评分 {comp.get('position_score', 0)}/100</p>
        <p style="margin: 5px 0;">候选：{comp.get('candidate_name', 'N/A')}({comp.get('candidate_code', 'N/A')}) - 评分 {comp.get('candidate_score', 0)}/100</p>
        <p style="margin: 5px 0; color: #666; font-size: 0.9em;">{comp.get('reason', '')}</p>
    </div>
"""

            # 推荐股票
            html_content += """
    <h3 style="color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px;">
        🎯 推荐股票
    </h3>
"""

            stocks = rec_data.get('stocks', [])
            for i, stock in enumerate(stocks, 1):
                # 决策颜色
                decision = stock.get('decision', 'BUY')
                if decision == 'STRONG_BUY':
                    decision_color = '#27ae60'
                    decision_icon = '🚀'
                elif decision == 'BUY':
                    decision_color = '#3498db'
                    decision_icon = '📈'
                else:
                    decision_color = '#95a5a6'
                    decision_icon = '⏸️'

                # 是否替换持仓
                replace_info = ""
                if stock.get('replace_position'):
                    replace = stock['replace_position']
                    replace_info = f"""
        <div style="background: #fff3cd; padding: 8px; margin: 8px 0; border-radius: 3px;">
            <p style="margin: 3px 0; font-size: 0.9em;">
                🔄 <strong>替换持仓:</strong> {replace.get('name', 'N/A')}({replace.get('code', 'N/A')})
                评分 {replace.get('score', 0)}/100
            </p>
        </div>
"""

                # 处理仓位百分比（兼容0-1小数和0-100百分比）
                position_pct = stock.get('position_pct', 0)
                if isinstance(position_pct, (int, float)):
                    if position_pct > 1:
                        # 已经是百分比（如100、50）
                        position_pct_display = f"{position_pct:.1f}%"
                    else:
                        # 是小数（如0.5、1.0）
                        position_pct_display = f"{position_pct*100:.1f}%"
                else:
                    position_pct_display = str(position_pct)

                # 处理止损止盈（兼容价格和百分比）
                recommend_price = stock.get('recommend_price', 0)
                stop_loss = stock.get('stop_loss', 0)
                target_price = stock.get('target_price', 0)

                # 判断止损是价格还是百分比
                if isinstance(stop_loss, (int, float)):
                    if stop_loss < 0:
                        # 是百分比（如-8表示-8%）
                        stop_loss_display = f"{stop_loss}%（{recommend_price * (1 + stop_loss/100):.2f}元）"
                    elif stop_loss < recommend_price * 0.5:
                        # 止损价格太小，可能是百分比
                        stop_loss_display = f"{stop_loss}%（{recommend_price * (1 + stop_loss/100):.2f}元）"
                    else:
                        # 是价格
                        stop_loss_pct = (stop_loss / recommend_price - 1) * 100 if recommend_price > 0 else 0
                        stop_loss_display = f"{stop_loss:.2f}元（{stop_loss_pct:.1f}%）"
                else:
                    stop_loss_display = str(stop_loss)

                # 判断止盈是价格还是百分比
                if isinstance(target_price, (int, float)):
                    if target_price < recommend_price * 0.5:
                        # 止盈价格太小，可能是百分比
                        target_price_display = f"+{target_price}%（{recommend_price * (1 + target_price/100):.2f}元）"
                    else:
                        # 是价格
                        target_pct = (target_price / recommend_price - 1) * 100 if recommend_price > 0 else 0
                        target_price_display = f"{target_price:.2f}元（+{target_pct:.1f}%）"
                else:
                    target_price_display = str(target_price)

                html_content += f"""
    <div style="border: 2px solid #3498db; padding: 15px; margin: 15px 0; border-radius: 8px; background: #fff;">
        <h4 style="color: #2c3e50; margin: 0 0 10px 0;">
            #{i} {stock.get('name', 'N/A')} ({stock.get('code', 'N/A')})
        </h4>

        <p style="margin: 8px 0;">
            <strong>决策:</strong>
            <span style="color: {decision_color}; font-weight: bold; font-size: 1.1em;">
                {decision_icon} {decision}
            </span>
        </p>

        {replace_info}

        <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>综合评分</strong></td>
                <td style="padding: 8px; border: 1px solid #bdc3c7; color: #e74c3c; font-weight: bold;">
                    {stock.get('final_score', 0)}/100
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">技术面</td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{stock.get('technical_score', 0)}/100</td>
            </tr>
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;">资金面</td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{stock.get('fund_score', 0)}/100</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">基本面</td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{stock.get('fundamental_score', 0)}/100</td>
            </tr>
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;">新闻面</td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{stock.get('news_score', 0)}/100</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">逐笔交易</td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{stock.get('tick_score', 0)}/100</td>
            </tr>
            <tr style="background: #ecf0f1;">
                <td style="padding: 8px; border: 1px solid #bdc3c7;">社区情绪</td>
                <td style="padding: 8px; border: 1px solid #bdc3c7;">{stock.get('community_sentiment_score', 0)}/100</td>
            </tr>
        </table>

        <div style="background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px;">
            <p style="margin: 5px 0;"><strong>💰 建议价格:</strong> {recommend_price:.2f}元</p>
            <p style="margin: 5px 0;"><strong>📊 建议仓位:</strong> {position_pct_display}</p>
            <p style="margin: 5px 0;"><strong>🛡️ 止损位:</strong> {stop_loss_display}</p>
            <p style="margin: 5px 0;"><strong>🎯 止盈位:</strong> {target_price_display}</p>
        </div>

        <div style="background: #e8f5e9; padding: 10px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #4caf50;">
            <p style="margin: 5px 0; color: #2e7d32;"><strong>💡 推荐理由:</strong></p>
            <p style="margin: 5px 0; color: #555;">{stock.get('reason', 'N/A')}</p>
        </div>
    </div>
"""

            # CEO总结
            if rec_data.get('ceo_summary'):
                html_content += f"""
    <div style="background: #fff3cd; padding: 15px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #ffc107;">
        <h3 style="color: #856404; margin: 0 0 10px 0;">📝 CEO总结</h3>
        <p style="margin: 0; color: #856404; line-height: 1.6;">{rec_data.get('ceo_summary')}</p>
    </div>
"""

            # 免责声明
            html_content += """
    <div style="background: #f8f9fa; padding: 10px; margin: 20px 0; border-radius: 5px; text-align: center;">
        <p style="margin: 0; color: #6c757d; font-size: 0.85em;">
            ⚠️ 本推荐由AI系统自动生成，仅供参考。投资有风险，决策需谨慎。
        </p>
    </div>
</div>
"""
            
        except json.JSONDecodeError:
            # 如果不是JSON，直接使用文本
            html_content = f"""
<h2>📈 今日股票推荐</h2>
<p><strong>日期:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<pre>{recommendations}</pre>
"""
        
        # 发送推送
        result = notifier.send_message(
            title="📈 CrewAI A-Stock 今日推荐",
            content=html_content,
            template="html"
        )
        
        if result.get('code') == 200:
            return "✓ 股票推荐已推送到微信"
        else:
            return f"✗ 推送失败: {result.get('msg', '未知错误')}"
            
    except Exception as e:
        return f"发送股票推荐失败: {str(e)}"


@tool("发送预警通知")
def send_alert_notification(alert_type: str, stock_code: str, message: str, suggestion: str = "") -> str:
    """
    发送止损/止盈预警通知（带推送去重机制）

    Args:
        alert_type: 预警类型（stop_loss/take_profit/risk_warning）
        stock_code: 股票代码
        message: 预警消息
        suggestion: AI建议（用于去重判断）

    Returns:
        发送结果(自然语言描述)
    """
    from src.utils.pushplus_notifier import get_notifier
    from src.database.db_manager import get_db
    from src.database.models import Position
    from datetime import datetime, timedelta, date
    from src.agents.tools.database_tools import get_current_session_id

    try:
        # 🔴 推送去重检查
        db = get_db()
        session_id = get_current_session_id()  # 使用全局session_id，避免Flask上下文问题

        with db.get_session() as db_session:
            position = db_session.query(Position).filter(
                Position.session_id == session_id,
                Position.stock_code == stock_code,
                Position.status == 'holding'
            ).first()

            if position:
                now = datetime.now()

                # 检查1：60分钟内推送过相同建议
                if position.last_push_time and position.last_push_suggestion == suggestion:
                    time_diff = (now - position.last_push_time).total_seconds() / 60
                    if time_diff < 60:
                        return f"⏭️ 跳过推送: {stock_code}（60分钟内已推送相同建议）"

                # 检查2：今日推送次数≥2次
                if position.push_count_today and position.push_count_today >= 2:
                    return f"⏭️ 跳过推送: {stock_code}（今日已推送{position.push_count_today}次）"

                # 检查3：每日0点重置推送计数
                if position.last_push_time and position.last_push_time.date() < date.today():
                    position.push_count_today = 0

        # 发送推送
        notifier = get_notifier()

        # 预警类型映射
        alert_titles = {
            'stop_loss': '🚨 止损预警',
            'take_profit': '🎯 止盈提醒',
            'risk_warning': '⚠️ 风险警告'
        }

        title = alert_titles.get(alert_type, '⚠️ 系统预警')

        # 构建HTML内容
        html_content = f"""
<h2>{title}</h2>
<p><strong>时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p><strong>股票:</strong> {stock_code}</p>
<p><strong>消息:</strong></p>
<div style="background:#fff3cd; padding:15px; border-left:4px solid #ffc107; margin:10px 0;">
    {message}
</div>
<p><strong>建议:</strong> 请及时查看持仓并做出决策</p>
"""

        # 发送推送
        result = notifier.send_message(
            title=f"{title} - {stock_code}",
            content=html_content,
            template="html"
        )

        # 更新推送记录
        if result.get('code') == 200 and position:
            with db.get_session() as db_session:
                position = db_session.query(Position).filter(
                    Position.session_id == session_id,
                    Position.stock_code == stock_code,
                    Position.status == 'holding'
                ).first()

                if position:
                    position.last_push_time = datetime.now()
                    position.last_push_suggestion = suggestion
                    position.push_count_today = (position.push_count_today or 0) + 1
                    db_session.commit()

            return f"✓ 预警通知已发送: {stock_code}（今日第{position.push_count_today}次）"
        else:
            return f"✗ 推送失败: {result.get('msg', '未知错误')}"

    except Exception as e:
        return f"发送预警通知失败: {str(e)}"

