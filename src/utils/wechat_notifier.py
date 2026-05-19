#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信公众号推送通知模块

使用微信公众号模板消息发送股票推荐和风险预警通知
与PushPlus接口保持一致，方便切换使用

功能：
- 发送股票推荐通知
- 发送风险预警通知
- 发送每日复盘报告
- 发送会议总结

使用方法：
1. 配置环境变量：
   - WECHAT_APPID: 公众号AppID
   - WECHAT_SECRET: 公众号AppSecret
   - WECHAT_TEMPLATE_ID: 模板消息ID
   - WECHAT_OPENID: 接收者OpenID（可多个，逗号分隔）

2. 调用示例：
   from src.utils.wechat_notifier import WeChatNotifier
   notifier = WeChatNotifier()
   notifier.send_stock_recommendation(candidates)
"""

import os
import json
import time
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger


class WeChatNotifier:
    """
    微信公众号推送通知器

    使用模板消息发送通知，支持：
    - 股票推荐通知
    - 风险预警通知
    - 每日复盘报告
    - 会议总结
    """

    # 类变量：缓存access_token
    _access_token: Optional[str] = None
    _token_expires_at: float = 0

    def __init__(
        self,
        appid: str = None,
        secret: str = None,
        template_id: str = None,
        openid: str = None
    ):
        """
        初始化微信公众号通知器

        Args:
            appid: 公众号AppID，默认从环境变量获取
            secret: 公众号AppSecret，默认从环境变量获取
            template_id: 模板消息ID，默认从环境变量获取
            openid: 接收者OpenID，默认从环境变量获取（可多个，逗号分隔）
        """
        self.appid = appid or os.getenv("WECHAT_APPID")
        self.secret = secret or os.getenv("WECHAT_SECRET")
        self.template_id = template_id or os.getenv("WECHAT_TEMPLATE_ID")
        self.openid_list = self._parse_openids(openid or os.getenv("WECHAT_OPENID"))

        # API地址
        self.token_url = "https://api.weixin.qq.com/cgi-bin/token"
        self.send_url = "https://api.weixin.qq.com/cgi-bin/message/template/send"

        # 验证配置
        if not all([self.appid, self.secret]):
            logger.warning("微信公众号配置不完整，部分功能可能不可用")

    def _parse_openids(self, openid_str: Optional[str]) -> List[str]:
        """解析OpenID列表"""
        if not openid_str:
            return []
        return [oid.strip() for oid in openid_str.split(",") if oid.strip()]

    def _get_access_token(self) -> Optional[str]:
        """
        获取access_token，带缓存机制

        微信access_token有效期为7200秒（2小时），这里提前5分钟刷新

        Returns:
            access_token字符串，失败返回None
        """
        # 检查缓存是否有效（提前5分钟刷新）
        if WeChatNotifier._access_token and time.time() < WeChatNotifier._token_expires_at - 300:
            return WeChatNotifier._access_token

        if not self.appid or not self.secret:
            logger.error("微信公众号AppID或Secret未配置")
            return None

        try:
            params = {
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.secret
            }

            response = requests.get(self.token_url, params=params, timeout=10)
            result = response.json()

            if "access_token" in result:
                WeChatNotifier._access_token = result["access_token"]
                # 缓存有效期（默认7200秒）
                expires_in = result.get("expires_in", 7200)
                WeChatNotifier._token_expires_at = time.time() + expires_in
                logger.info(f"微信access_token获取成功，有效期{expires_in}秒")
                return WeChatNotifier._access_token
            else:
                logger.error(f"获取access_token失败: {result}")
                return None

        except Exception as e:
            logger.error(f"获取access_token异常: {e}")
            return None

    def send_template_message(
        self,
        openid: str,
        template_id: str,
        data: Dict[str, Any],
        url: str = None,
        miniprogram: Dict = None
    ) -> Dict[str, Any]:
        """
        发送模板消息

        Args:
            openid: 接收者OpenID
            template_id: 模板ID
            data: 模板数据，格式：{"keyword1": {"value": "xxx", "color": "#000000"}}
            url: 点击跳转URL（可选）
            miniprogram: 小程序跳转配置（可选）

        Returns:
            API响应结果
        """
        access_token = self._get_access_token()
        if not access_token:
            return {"success": False, "error": "获取access_token失败"}

        try:
            send_url = f"{self.send_url}?access_token={access_token}"

            payload = {
                "touser": openid,
                "template_id": template_id,
                "data": data
            }

            if url:
                payload["url"] = url
            if miniprogram:
                payload["miniprogram"] = miniprogram

            response = requests.post(
                send_url,
                json=payload,
                timeout=10
            )
            result = response.json()

            if result.get("errcode") == 0:
                logger.success(f"模板消息发送成功: openid={openid[:10]}...")
                return {"success": True, "msgid": result.get("msgid")}
            else:
                logger.error(f"模板消息发送失败: {result}")
                return {"success": False, "error": result}

        except Exception as e:
            logger.error(f"发送模板消息异常: {e}")
            return {"success": False, "error": str(e)}

    def send_message(
        self,
        title: str,
        content: str,
        template: str = "html",
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息（兼容PushPlus接口）

        由于微信模板消息格式固定，这里会尝试将内容适配到模板

        Args:
            title: 消息标题
            content: 消息内容
            template: 模板类型（忽略，微信使用固定模板）
            topic: 话题（忽略）

        Returns:
            发送结果
        """
        if not self.openid_list:
            logger.warning("未配置接收者OpenID")
            return {"success": False, "error": "未配置接收者OpenID"}

        if not self.template_id:
            logger.warning("未配置模板ID")
            return {"success": False, "error": "未配置模板ID"}

        # 构建模板数据
        # 这里使用通用格式，实际需要根据你的模板结构调整
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = {
            "first": {"value": title, "color": "#173177"},
            "keyword1": {"value": "股票推荐系统", "color": "#173177"},
            "keyword2": {"value": now, "color": "#173177"},
            "remark": {"value": self._truncate_content(content), "color": "#666666"}
        }

        # 发送给所有接收者
        results = []
        for openid in self.openid_list:
            result = self.send_template_message(openid, self.template_id, data)
            results.append(result)

        # 检查是否全部成功
        all_success = all(r.get("success") for r in results)
        return {
            "success": all_success,
            "results": results,
            "sent_count": len(results)
        }

    def _truncate_content(self, content: str, max_length: int = 200) -> str:
        """截断内容，微信模板消息有长度限制"""
        # 移除HTML标签
        import re
        clean_content = re.sub(r'<[^>]+>', '', content)
        clean_content = clean_content.replace('&nbsp;', ' ')

        if len(clean_content) > max_length:
            return clean_content[:max_length] + "..."
        return clean_content

    def send_stock_recommendation(
        self,
        candidates: List[Dict],
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送股票推荐通知

        Args:
            candidates: 候选股票列表
            topic: 话题（忽略）

        Returns:
            发送结果
        """
        if not candidates:
            logger.warning("没有推荐股票，跳过推送")
            return {"success": False, "error": "没有推荐股票"}

        if not self.openid_list:
            logger.warning("未配置接收者OpenID")
            return {"success": False, "error": "未配置接收者OpenID"}

        # 构建消息内容
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stock_count = len(candidates)

        # 构建股票列表摘要
        stock_summary = []
        for i, stock in enumerate(candidates[:3], 1):  # 最多显示3只
            code = stock.get('code', stock.get('stock_code', ''))
            name = stock.get('name', stock.get('stock_name', ''))
            score = stock.get('final_score', stock.get('score', 0))
            stock_summary.append(f"{i}.{name}({code}) 评分:{score}")

        summary_text = "\n".join(stock_summary)
        if stock_count > 3:
            summary_text += f"\n...等共{stock_count}只股票"

        # 构建模板数据
        data = {
            "first": {"value": f"📈 今日股票推荐 ({stock_count}只)", "color": "#FF4500"},
            "keyword1": {"value": "AI智能推荐", "color": "#173177"},
            "keyword2": {"value": now, "color": "#173177"},
            "remark": {"value": summary_text, "color": "#666666"}
        }

        # 发送给所有接收者
        results = []
        for openid in self.openid_list:
            result = self.send_template_message(
                openid,
                self.template_id,
                data
            )
            results.append(result)

        all_success = all(r.get("success") for r in results)
        return {
            "success": all_success,
            "results": results,
            "sent_count": len(results),
            "stock_count": stock_count
        }

    def send_risk_alert(
        self,
        alert_data: Dict,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送风险预警通知

        Args:
            alert_data: 预警数据，包含：
                - stock_code: 股票代码
                - stock_name: 股票名称
                - alert_type: 预警类型
                - message: 预警消息
                - suggestion: 操作建议
                - profit_pct: 盈亏比例（可选）
            topic: 话题（忽略）

        Returns:
            发送结果
        """
        if not self.openid_list:
            logger.warning("未配置接收者OpenID")
            return {"success": False, "error": "未配置接收者OpenID"}

        stock_code = alert_data.get('stock_code', '')
        stock_name = alert_data.get('stock_name', '')
        alert_type = alert_data.get('alert_type', '风险预警')
        message = alert_data.get('message', '')
        suggestion = alert_data.get('suggestion', '')
        profit_pct = alert_data.get('profit_pct', None)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建预警摘要
        remark_parts = []
        if profit_pct is not None:
            remark_parts.append(f"盈亏: {profit_pct:+.2f}%")
        if message:
            remark_parts.append(message[:50])
        if suggestion:
            remark_parts.append(f"建议: {suggestion[:30]}")

        remark_text = "\n".join(remark_parts) if remark_parts else "请及时关注"

        # 构建模板数据
        data = {
            "first": {"value": f"🚨 {alert_type}", "color": "#FF0000"},
            "keyword1": {"value": f"{stock_name}({stock_code})", "color": "#173177"},
            "keyword2": {"value": now, "color": "#173177"},
            "remark": {"value": remark_text, "color": "#FF4500"}
        }

        # 发送给所有接收者
        results = []
        for openid in self.openid_list:
            result = self.send_template_message(
                openid,
                self.template_id,
                data
            )
            results.append(result)

        all_success = all(r.get("success") for r in results)
        return {
            "success": all_success,
            "results": results,
            "sent_count": len(results)
        }

    def send_meeting_summary(
        self,
        meeting_log: List[Dict],
        meeting_type: str = "AI分析会议",
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送会议总结

        Args:
            meeting_log: 会议日志列表
            meeting_type: 会议类型
            topic: 话题（忽略）

        Returns:
            发送结果
        """
        if not meeting_log:
            logger.warning("没有会议日志，跳过推送")
            return {"success": False, "error": "没有会议日志"}

        if not self.openid_list:
            logger.warning("未配置接收者OpenID")
            return {"success": False, "error": "未配置接收者OpenID"}

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 统计会议参与者
        agents = set()
        for log in meeting_log:
            if 'agent' in log:
                agents.add(log['agent'])

        agent_count = len(agents)
        log_count = len(meeting_log)

        # 构建摘要
        summary_text = f"参与Agent: {agent_count}个\n会议记录: {log_count}条"

        # 提取最后一条结论（如果有）
        last_log = meeting_log[-1] if meeting_log else {}
        if 'conclusion' in last_log:
            conclusion = last_log['conclusion'][:100]
            summary_text += f"\n结论: {conclusion}"

        # 构建模板数据
        data = {
            "first": {"value": f"📋 {meeting_type}总结", "color": "#173177"},
            "keyword1": {"value": meeting_type, "color": "#173177"},
            "keyword2": {"value": now, "color": "#173177"},
            "remark": {"value": summary_text, "color": "#666666"}
        }

        # 发送给所有接收者
        results = []
        for openid in self.openid_list:
            result = self.send_template_message(
                openid,
                self.template_id,
                data
            )
            results.append(result)

        all_success = all(r.get("success") for r in results)
        return {
            "success": all_success,
            "results": results,
            "sent_count": len(results)
        }

    def send_daily_review(
        self,
        review_report: str,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送每日复盘报告

        Args:
            review_report: 复盘报告内容
            topic: 话题（忽略）

        Returns:
            发送结果
        """
        if not review_report:
            logger.warning("没有复盘报告，跳过推送")
            return {"success": False, "error": "没有复盘报告"}

        if not self.openid_list:
            logger.warning("未配置接收者OpenID")
            return {"success": False, "error": "未配置接收者OpenID"}

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.now().strftime("%Y-%m-%d")

        # 截取报告摘要
        summary = self._truncate_content(review_report, 150)

        # 构建模板数据
        data = {
            "first": {"value": f"📊 每日复盘报告", "color": "#173177"},
            "keyword1": {"value": today, "color": "#173177"},
            "keyword2": {"value": now, "color": "#173177"},
            "remark": {"value": summary, "color": "#666666"}
        }

        # 发送给所有接收者
        results = []
        for openid in self.openid_list:
            result = self.send_template_message(
                openid,
                self.template_id,
                data
            )
            results.append(result)

        all_success = all(r.get("success") for r in results)
        return {
            "success": all_success,
            "results": results,
            "sent_count": len(results)
        }


# ==================== 便捷函数（与PushPlus保持一致） ====================

def send_stock_recommendation(candidates: List[Dict], topic: Optional[str] = None) -> Dict[str, Any]:
    """发送股票推荐通知（便捷函数）"""
    notifier = WeChatNotifier()
    return notifier.send_stock_recommendation(candidates, topic)


def send_risk_alert(alert_data: Dict, topic: Optional[str] = None) -> Dict[str, Any]:
    """发送风险预警通知（便捷函数）"""
    notifier = WeChatNotifier()
    return notifier.send_risk_alert(alert_data, topic)


def send_meeting_summary(
    meeting_log: List[Dict],
    meeting_type: str = "AI分析会议",
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """发送会议总结（便捷函数）"""
    notifier = WeChatNotifier()
    return notifier.send_meeting_summary(meeting_log, meeting_type, topic)


def send_daily_review(review_report: str, topic: Optional[str] = None) -> Dict[str, Any]:
    """发送每日复盘报告（便捷函数）"""
    notifier = WeChatNotifier()
    return notifier.send_daily_review(review_report, topic)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 测试微信公众号推送
    notifier = WeChatNotifier()

    # 检查配置
    print("=" * 50)
    print("微信公众号推送配置检查")
    print("=" * 50)
    print(f"AppID: {notifier.appid[:10]}..." if notifier.appid else "AppID: 未配置")
    print(f"Secret: {'已配置' if notifier.secret else '未配置'}")
    print(f"Template ID: {notifier.template_id[:10]}..." if notifier.template_id else "Template ID: 未配置")
    print(f"OpenID列表: {len(notifier.openid_list)}个接收者")

    # 测试发送
    if notifier.appid and notifier.secret and notifier.template_id and notifier.openid_list:
        print("\n开始测试发送...")

        # 测试股票推荐
        test_candidates = [
            {
                "code": "600000",
                "name": "浦发银行",
                "final_score": 85,
                "decision": "STRONG_BUY"
            },
            {
                "code": "000001",
                "name": "平安银行",
                "final_score": 78,
                "decision": "BUY"
            }
        ]

        result = notifier.send_stock_recommendation(test_candidates)
        print(f"股票推荐发送结果: {result}")
    else:
        print("\n配置不完整，跳过发送测试")
        print("请配置以下环境变量：")
        print("  - WECHAT_APPID")
        print("  - WECHAT_SECRET")
        print("  - WECHAT_TEMPLATE_ID")
        print("  - WECHAT_OPENID")
