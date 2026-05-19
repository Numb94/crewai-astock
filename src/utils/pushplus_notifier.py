#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock V2.0 - PushPlus 推送通知器

提供微信推送功能,用于股票推荐、风险预警、会议纪要等

作者: AI Architect
版本: v2.0.5-db-complete
日期: 2025-10-21
"""

import os
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class PushPlusNotifier:
    """PushPlus 推送通知器

    官网: http://www.pushplus.plus
    功能: 微信公众号消息推送
    费用: 免费 (每日500条)
    """

    def __init__(self, token: str = None, topic: str = None):
        """初始化 PushPlus 通知器

        Args:
            token: PushPlus Token (默认从环境变量读取)
            topic: 群组编码 (默认从环境变量读取)
        """
        self.token = token or os.getenv("PUSHPLUS_TOKEN")
        self.topic = topic or os.getenv("PUSHPLUS_TOPIC")
        self.base_url = "http://www.pushplus.plus/send"

        if not self.token:
            logger.warning("PushPlus Token 未配置,推送功能将不可用")

    def send_message(
        self,
        title: str,
        content: str,
        template: str = "html",
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """发送消息

        Args:
            title: 消息标题
            content: 消息内容
            template: 消息格式 (html/txt/json/markdown)
            topic: 群组编码 (可选,默认使用初始化时的topic)

        Returns:
            {
                "code": 200,
                "msg": "请求成功",
                "data": "..."
            }
        """
        if not self.token:
            logger.error("PushPlus Token 未配置,无法发送推送")
            return {"code": 500, "msg": "Token 未配置"}

        data = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": template
        }

        # 使用提供的 topic 或默认 topic
        topic_to_use = topic or self.topic
        if topic_to_use:
            data["topic"] = topic_to_use

        try:
            response = requests.post(self.base_url, json=data, timeout=10)
            result = response.json()

            if result.get("code") == 200:
                logger.info(f"PushPlus 推送成功: {title}")
            else:
                logger.error(f"PushPlus 推送失败: {result.get('msg')}")

            return result

        except requests.exceptions.Timeout:
            logger.error("PushPlus 推送超时")
            return {"code": 500, "msg": "推送超时"}
        except requests.exceptions.RequestException as e:
            logger.error(f"PushPlus 推送网络异常: {str(e)}")
            return {"code": 500, "msg": f"网络异常: {str(e)}"}
        except Exception as e:
            logger.error(f"PushPlus 推送异常: {str(e)}")
            return {"code": 500, "msg": str(e)}

    def send_stock_recommendation(
        self,
        candidates: List[Dict[str, Any]],
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """推送股票推荐

        Args:
            candidates: 候选股票列表
                [
                    {
                        "stock_code": "000001",
                        "stock_name": "平安银行",
                        "final_score": 85.5,
                        "ceo_decision": "买入",
                        "position_size": "10%",
                        "reasoning": "技术面强势,资金流入明显"
                    },
                    ...
                ]
            topic: 群组编码 (可选)

        Returns:
            推送结果
        """
        if not candidates:
            logger.warning("股票推荐列表为空,跳过推送")
            return {"code": 400, "msg": "推荐列表为空"}

        # 构建HTML内容
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""
        <h2>📈 今日股票推荐</h2>
        <p><strong>推送时间:</strong> {current_time}</p>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #f0f0f0;">
                <th>股票</th>
                <th>评分</th>
                <th>决策</th>
                <th>仓位</th>
            </tr>
        """

        for stock in candidates:
            # 根据决策类型设置颜色
            decision = stock.get("ceo_decision", "观望")
            decision_color = "green" if "买入" in decision else "red" if "卖出" in decision else "gray"

            content += f"""
            <tr>
                <td><strong>{stock.get('stock_name', 'N/A')}</strong> ({stock.get('stock_code', 'N/A')})</td>
                <td>{stock.get('final_score', 0):.1f}分</td>
                <td style="color: {decision_color};"><strong>{decision}</strong></td>
                <td>{stock.get('position_size', 'N/A')}</td>
            </tr>
            """

        content += """
        </table>
        <br/>
        <h3>推荐理由:</h3>
        """

        for stock in candidates:
            content += f"""
            <p><strong>{stock.get('stock_name', 'N/A')}:</strong>
            {stock.get('reasoning', '暂无理由说明')}</p>
            """

        content += """
        <hr/>
        <p style="color: gray;"><em>本推荐由AI系统自动生成,仅供参考,投资有风险,决策需谨慎</em></p>
        """

        return self.send_message(
            title=f"📈 股票AI推荐 ({len(candidates)}只)",
            content=content,
            template="html",
            topic=topic
        )

    def send_risk_alert(
        self,
        alert_data: Dict[str, Any],
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """推送风险预警

        Args:
            alert_data: 预警数据
                {
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                    "current_price": 15.20,
                    "buy_price": 16.00,
                    "profit_loss_pct": -5.0,
                    "alert_type": "止损预警",
                    "message": "跌破止损线",
                    "suggestion": "建议立即卖出"
                }
            topic: 群组编码 (可选)

        Returns:
            推送结果
        """
        current_price = alert_data.get("current_price", 0)
        buy_price = alert_data.get("buy_price", 0)
        profit_loss_pct = alert_data.get("profit_loss_pct", 0)

        # 根据盈亏设置颜色
        color = "red" if profit_loss_pct < 0 else "green"

        content = f"""
        <h2>⚠️ 风险预警</h2>
        <p><strong>股票:</strong> {alert_data.get('stock_name', 'N/A')} ({alert_data.get('stock_code', 'N/A')})</p>
        <p><strong>当前价:</strong> {current_price:.2f}元</p>
        <p><strong>买入价:</strong> {buy_price:.2f}元</p>
        <p><strong>盈亏:</strong> <span style="color: {color};"><strong>{profit_loss_pct:+.2f}%</strong></span></p>
        <p><strong>预警原因:</strong> {alert_data.get('message', '未知原因')}</p>
        <p><strong>建议操作:</strong> <span style="color: red;"><strong>{alert_data.get('suggestion', '请关注')}</strong></span></p>
        <hr/>
        <p style="color: red;"><em>请及时关注行情变化,做出相应决策</em></p>
        """

        alert_type = alert_data.get("alert_type", "风险预警")
        stock_name = alert_data.get("stock_name", "未知股票")

        return self.send_message(
            title=f"⚠️ {alert_type} - {stock_name}",
            content=content,
            template="html",
            topic=topic
        )

    def send_meeting_summary(
        self,
        meeting_log: List[Dict[str, Any]],
        meeting_type: str = "盘前策略会议",
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """推送会议纪要

        Args:
            meeting_log: 会议日志列表
                [
                    {
                        "time": "09:00:00",
                        "speaker": "CMO",
                        "message": "今日市场情绪偏暖..."
                    },
                    ...
                ]
            meeting_type: 会议类型 (盘前策略会议/紧急决策会议/盘后复盘会议)
            topic: 群组编码 (可选)

        Returns:
            推送结果
        """
        if not meeting_log:
            logger.warning("会议日志为空,跳过推送")
            return {"code": 400, "msg": "会议日志为空"}

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = f"""
        <h2>📋 {meeting_type}纪要</h2>
        <p><strong>会议时间:</strong> {current_time}</p>
        <hr/>
        <ul style="line-height: 1.8;">
        """

        for log in meeting_log:
            speaker = log.get("speaker", "未知发言人")
            message = log.get("message", "")
            log_time = log.get("time", "")

            content += f"""
            <li>[{log_time}] <strong>{speaker}:</strong> {message}</li>
            """

        content += """
        </ul>
        <hr/>
        <p style="color: gray;"><em>会议纪要由AI系统自动生成</em></p>
        """

        return self.send_message(
            title=f"📋 {meeting_type}纪要",
            content=content,
            template="html",
            topic=topic
        )

    def send_daily_review(
        self,
        review_report: str,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """推送每日复盘报告

        Args:
            review_report: 复盘报告内容 (Markdown格式)
            topic: 群组编码 (可选)

        Returns:
            推送结果
        """
        if not review_report:
            logger.warning("复盘报告为空,跳过推送")
            return {"code": 400, "msg": "复盘报告为空"}

        return self.send_message(
            title="📊 每日交易复盘",
            content=review_report,
            template="markdown",
            topic=topic
        )


# ========================================
# 便捷函数
# ========================================

_notifier_instance = None


def get_pushplus_notifier() -> PushPlusNotifier:
    """获取全局 PushPlus 通知器实例"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = PushPlusNotifier()
    return _notifier_instance


def send_stock_recommendation(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """便捷函数: 推送股票推荐"""
    notifier = get_pushplus_notifier()
    return notifier.send_stock_recommendation(candidates)


def send_risk_alert(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """便捷函数: 推送风险预警"""
    # notifier = get_pushplus_notifier()
    # return notifier.send_risk_alert(alert_data)


def send_meeting_summary(meeting_log: List[Dict[str, Any]], meeting_type: str = "盘前策略会议") -> Dict[str, Any]:
    """便捷函数: 推送会议纪要"""
    notifier = get_pushplus_notifier()
    return notifier.send_meeting_summary(meeting_log, meeting_type)


def send_daily_review(review_report: str) -> Dict[str, Any]:
    """便捷函数: 推送每日复盘"""
    notifier = get_pushplus_notifier()
    return notifier.send_daily_review(review_report)


# ========================================
# 工厂函数: 根据环境变量选择推送渠道
# ========================================

def get_notifier():
    """
    获取通知器实例（根据环境变量自动选择推送渠道）

    环境变量: NOTIFICATION_CHANNEL
    - pushplus: 使用PushPlus推送（默认）
    - wechat: 使用微信公众号推送

    Returns:
        PushPlusNotifier 或 WeChatNotifier 实例

    Example:
        # 在 .env 中配置
        NOTIFICATION_CHANNEL=pushplus  # 或 wechat

        # 代码中使用
        notifier = get_notifier()
        notifier.send_message("标题", "内容")
    """
    channel = os.getenv('NOTIFICATION_CHANNEL', 'pushplus').lower().strip()

    if channel == 'wechat':
        logger.info("📱 使用微信公众号推送渠道")
        from src.utils.wechat_notifier import WeChatNotifier
        return WeChatNotifier()
    else:
        logger.info("📱 使用PushPlus推送渠道")
        return get_pushplus_notifier()
