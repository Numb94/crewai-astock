#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - 持仓监控Crew

实现持仓监控的完整流程：
1. 查询所有持仓
2. 获取实时价格和盘口数据
3. 智能卖点分析
4. 风险预警推送

✅ 支持多用户隔离：每个session_id有独立的Crew实例
"""

from crewai import Crew, Task
from src.agents.smart_agents import create_position_monitor
from src.config.llm_config import get_decision_llm
from loguru import logger


def create_position_monitor_crew(session_id: str = 'default'):
    """
    创建持仓监控Crew

    Args:
        session_id: 用户session_id，用于数据隔离

    Returns:
        Crew实例
    """
    logger.info(f"🏗️ 创建持仓监控Crew: session_id={session_id[:8]}...")

    # ✅ 设置当前session_id（使用contextvars）
    from src.agents.tools.database_tools import set_current_session_id
    set_current_session_id(session_id)

    # 创建Agent
    monitor_agent = create_position_monitor()
    
    # Task 1: 查询持仓并获取实时数据 + 隔夜短线信号检查
    task1_query = Task(
        description='''查询所有持仓股票，获取实时数据，并检查隔夜短线信号：

1. 使用工具【query_current_positions】查询所有持仓
2. 如果没有持仓，返回"当前无持仓"
3. 如果有持仓，提取所有股票代码列表
4. 使用工具【get_realtime_prices】批量获取实时价格

🌙 **隔夜短线策略信号检查**（必须执行）：

5. 使用工具【check_opening_signal】检查开盘信号
   - 🟢 高开≥3%：冲高止盈信号，开盘就卖
   - 🟡 高开1-3%：正常，等冲高再卖
   - ⚪ 平开±1%：观察开盘走势
   - 🟠 低开1-3%：警惕，设好止损
   - 🔴 低开≥3%：紧急止损信号

6. 使用工具【check_morning_time_window】检查早盘时间窗口
   - 9:30-9:45：黄金15分钟，冲高回落要快速反应
   - 9:45-10:00：趋势确认期，涨幅不及预期减仓50%
   - 10:00-10:30：最后窗口，不涨反跌应清仓
   - 10:30后：已过最佳卖点

输出格式：
```
持仓股票数量: X只
股票列表: [代码1, 代码2, ...]
实时价格已获取

=== 隔夜短线信号 ===
开盘信号: X只高开 / X只低开
时间窗口: 【当前窗口名称】
紧急操作: 是/否
```
''',
        agent=monitor_agent,
        expected_output='持仓股票列表、实时价格、开盘信号和时间窗口分析'
    )
    
    # Task 2: 逐个分析持仓股票（含隔夜短线策略）
    task2_analyze = Task(
        description='''对每只持仓股票进行深度分析（隔夜短线策略优先）：

🌙 **隔夜短线策略核心原则**：
- 尾盘买入 → 早盘卖出，持仓通常1天
- 10:30前必须有结论，过时不候
- 高开必卖，低开止损，快进快出

对于每只股票，按以下步骤分析：

1. **更新移动止盈数据**（必须，T+1约束）
   - 使用工具【update_trailing_stop_data】更新可卖出持仓的移动止盈数据

2. **5分钟ATR波动分析**（🆕 隔夜短线必须）
   - 使用工具【calculate_5min_atr】计算5分钟级别ATR
   - **判断标准**：
     * 回落 > 1.5×ATR_5min → 🔴 明显冲高回落，止盈信号
     * 回落 > 1.0×ATR_5min → 🟠 有回落迹象，关注
     * 回落 < 1.0×ATR_5min → 🟢 正常波动，持有

3. **获取五档盘口数据**（必须）
   - 使用工具【get_five_level_quotes】获取五档盘口
   - 分析买卖力量对比

4. **获取技术指标 + 5分钟K线**（必须）
   - 使用工具【get_technical_indicators】获取完整技术数据

5. **综合判断卖点**（隔夜短线优先规则）

   【强烈建议卖出】（high urgency）- 隔夜短线优先触发：

   🌙 **隔夜短线专用规则**（最高优先级）：
   - 🔴 **开盘信号：高开≥3%** → 冲高止盈，开盘就卖
   - 🔴 **开盘信号：低开≥3%** → 紧急止损，立即卖出
   - 🔴 **时间窗口：10:00-10:30 + 不涨反跌** → 最后窗口，必须清仓
   - 🔴 **ATR信号：回落 > 1.5×ATR_5min** → 明显冲高回落，止盈

   📊 **通用规则**：
   - 🔥 **动态移动止盈触发** → 必须立即止盈
   - 🔥 **5分钟K线卖点信号**：连续3根阴线/冲高回落/均线死叉
   - **总盈利≥10%** → 必须止盈
   - **总亏损≥8%** → 必须止损
   - **当日跌幅≥8%** → 必须紧急止损

   【建议卖出】（medium urgency）：
   - 🌙 **时间窗口：9:45-10:00 + 涨幅<预期** → 趋势确认期，减仓50%
   - 🌙 **ATR信号：回落 > 1.0×ATR_5min** → 有回落迹象，关注
   - 总盈利≥5% 且 持仓≥3天 → 可考虑止盈
   - 总亏损≥5% → 建议止损
   - 五档盘口卖盘压力大 → 上涨乏力

   【建议持有/观望】（low urgency）：
   - 🌙 **时间窗口：9:30-9:45 + 走势正常** → 黄金15分钟，继续观察
   - ATR信号：回落 < 1.0×ATR_5min → 正常波动
   - 总盈利>0% 且 五档买盘强劲 → 趋势良好

输出格式（每只股票）：
```
股票: XXX(代码)
当前价: XX.XX元
总盈亏: +X.XX% (XX元)
当日涨跌: +X.XX%
持仓天数: X天

🌙【隔夜短线信号】
开盘信号: 🟢高开X%/🔴低开X%/⚪平开
时间窗口: 黄金15分钟/趋势确认期/最后窗口/已过最佳卖点
ATR分析: 回落X.XX×ATR（正常/关注/止盈信号）

【五档盘口】
买卖比: X.XX
分析: 买盘力量强劲/卖盘压力大/均衡

【5分钟K线】⭐
最近走势: 上涨/下跌/横盘/冲高回落
卖点信号: 无/冲高回落/连续阴线

【卖点建议】
紧急程度: high/medium/low
操作建议: 强烈建议卖出/建议卖出/建议持有/建议观望
理由: XXX（必须说明隔夜短线信号 + 总盈亏 + 当日涨跌）
```
''',
        agent=monitor_agent,
        expected_output='每只持仓股票的详细分析和卖点建议（含隔夜短线信号）',
        context=[task1_query]
    )
    
    # Task 3: 风险预警和推送通知
    task3_alert = Task(
        description='''汇总分析结果，发送风险预警：

1. 统计各紧急程度的股票数量：
   - high urgency（强烈建议卖出）: X只
   - medium urgency（建议卖出）: X只
   - low urgency（建议持有/观望）: X只

2. 🔴 **推送去重机制**（避免频繁打扰用户）

   对于high urgency的股票，检查是否需要推送：
   - 如果上次推送时间<60分钟 且 建议相同 → 跳过推送
   - 如果今日推送次数≥2次 → 跳过推送
   - 否则 → 发送紧急预警

   使用工具【send_alert_notification】发送紧急预警：
   - 标题: "🚨 持仓预警：强烈建议卖出"
   - 内容: 股票名称、盈亏比例、卖出理由（不要包含盈亏金额）

   推送后更新数据库：
   - last_push_time = 当前时间
   - last_push_suggestion = 当前建议
   - push_count_today += 1

3. 生成监控报告

输出格式：
```
=== 持仓监控报告 ===

监控时间: YYYY-MM-DD HH:MM:SS
持仓数量: X只

【紧急预警】(high urgency)
1. XXX(代码) | 盈亏+X.XX% | 理由: XXX
...

【建议关注】(medium urgency)
1. XXX(代码) | 盈亏+X.XX% | 理由: XXX
...

【正常持有】(low urgency)
1. XXX(代码) | 盈亏+X.XX% | 理由: XXX
...

已发送X条紧急预警通知
```
''',
        agent=monitor_agent,
        expected_output='持仓监控报告和预警通知发送结果',
        context=[task2_analyze]
    )
    
    # 创建Crew
    crew = Crew(
        agents=[monitor_agent],
        tasks=[task1_query, task2_analyze, task3_alert],
        manager_llm=get_decision_llm(),
        verbose=False  # 🔴 关闭详细日志，减少控制台输出
    )
    
    return crew


def parse_ai_analysis_result(result_text: str):
    """
    解析AI分析结果，提取关键信息

    支持两种格式：
    1. Task 2的结构化格式（股票: XXX(代码)）
    2. Task 3的报告格式（【紧急预警】1. XXX(代码) | 理由: ...）

    Args:
        result_text: AI分析结果文本

    Returns:
        dict: 解析后的分析结果
        {
            'stock_code': {
                'suggestion': '强烈建议卖出/建议卖出/建议持有/建议观望',
                'reason': '卖出理由',
                'urgency': 'high/medium/low',
                'bid_ask_ratio': None,
                'bid_ask_analysis': '',
                'fund_flow': '',
                'fund_flow_analysis': '',
                'technical_analysis': ''
            }
        }
    """
    import re
    from decimal import Decimal

    analysis_results = {}

    try:
        # 🔴 优先尝试解析Task 3的报告格式
        # 格式: 【紧急预警】(high urgency) 或 【建议关注】(medium urgency) 或 【正常持有】(low urgency)
        # 1. 欢瑞世纪(000892) | 盈亏-4.49% | 理由: XXX

        # 提取【紧急预警】部分
        high_urgency_match = re.search(r'【紧急预警】.*?\n(.*?)(?=【|$)', result_text, re.DOTALL)
        if high_urgency_match:
            high_content = high_urgency_match.group(1)
            # 提取股票信息: 1. 欢瑞世纪(000892) | 盈亏-4.49% | 理由: XXX
            stock_matches = re.findall(r'\d+\.\s*([^\(]+)\((\d{6})\)[^\|]*\|[^\|]*\|\s*理由:\s*([^\n]+)', high_content)
            for stock_name, stock_code, reason in stock_matches:
                analysis_results[stock_code] = {
                    'suggestion': '强烈建议卖出',
                    'reason': reason.strip(),
                    'urgency': 'high',
                    'bid_ask_ratio': None,
                    'bid_ask_analysis': '',
                    'fund_flow': '',
                    'fund_flow_analysis': '',
                    'technical_analysis': ''
                }
                logger.debug(f"解析 {stock_name.strip()}({stock_code}) AI分析: 强烈建议卖出 (high)")

        # 提取【建议关注】部分
        medium_urgency_match = re.search(r'【建议关注】.*?\n(.*?)(?=【|$)', result_text, re.DOTALL)
        if medium_urgency_match:
            medium_content = medium_urgency_match.group(1)
            stock_matches = re.findall(r'\d+\.\s*([^\(]+)\((\d{6})\)[^\|]*\|[^\|]*\|\s*理由:\s*([^\n]+)', medium_content)
            for stock_name, stock_code, reason in stock_matches:
                analysis_results[stock_code] = {
                    'suggestion': '建议卖出',
                    'reason': reason.strip(),
                    'urgency': 'medium',
                    'bid_ask_ratio': None,
                    'bid_ask_analysis': '',
                    'fund_flow': '',
                    'fund_flow_analysis': '',
                    'technical_analysis': ''
                }
                logger.debug(f"解析 {stock_name.strip()}({stock_code}) AI分析: 建议卖出 (medium)")

        # 提取【正常持有】部分
        low_urgency_match = re.search(r'【正常持有】.*?\n(.*?)(?=【|$)', result_text, re.DOTALL)
        if low_urgency_match:
            low_content = low_urgency_match.group(1)
            stock_matches = re.findall(r'\d+\.\s*([^\(]+)\((\d{6})\)[^\|]*\|[^\|]*\|\s*理由:\s*([^\n]+)', low_content)
            for stock_name, stock_code, reason in stock_matches:
                analysis_results[stock_code] = {
                    'suggestion': '建议持有',
                    'reason': reason.strip(),
                    'urgency': 'low',
                    'bid_ask_ratio': None,
                    'bid_ask_analysis': '',
                    'fund_flow': '',
                    'fund_flow_analysis': '',
                    'technical_analysis': ''
                }
                logger.debug(f"解析 {stock_name.strip()}({stock_code}) AI分析: 建议持有 (low)")

        # 如果Task 3格式解析成功，直接返回
        if analysis_results:
            logger.info(f"✅ 成功解析Task 3报告格式，共{len(analysis_results)}只股票")
            return analysis_results

        # 🔴 如果Task 3格式解析失败，尝试解析Task 2的结构化格式
        # 按股票分段（查找"股票: XXX(代码)"模式）
        stock_sections = re.split(r'股票:\s*([^\(]+)\((\d{6})\)', result_text)

        # stock_sections格式: ['', '股票名', '股票代码', '内容', '股票名', '股票代码', '内容', ...]
        for i in range(1, len(stock_sections), 3):
            if i + 2 > len(stock_sections):
                break

            stock_name = stock_sections[i].strip()
            stock_code = stock_sections[i + 1].strip()
            content = stock_sections[i + 2]

            # 提取卖点建议
            suggestion_match = re.search(r'操作建议:\s*([^\n]+)', content)
            suggestion = suggestion_match.group(1).strip() if suggestion_match else '建议持有'

            # 提取紧急程度
            urgency_match = re.search(r'紧急程度:\s*(high|medium|low)', content)
            urgency = urgency_match.group(1).strip() if urgency_match else 'low'

            # 提取理由
            reason_match = re.search(r'理由:\s*([^\n]+)', content)
            reason = reason_match.group(1).strip() if reason_match else ''

            # 提取买卖比
            bid_ask_ratio_match = re.search(r'买卖比:\s*([\d\.]+)', content)
            bid_ask_ratio = Decimal(bid_ask_ratio_match.group(1)) if bid_ask_ratio_match else None

            # 提取盘口分析
            bid_ask_analysis_match = re.search(r'分析:\s*([^\n]+)', content)
            bid_ask_analysis = bid_ask_analysis_match.group(1).strip() if bid_ask_analysis_match else ''

            # 提取资金流向
            fund_flow_match = re.search(r'资金流向:\s*([^\n]+)', content)
            fund_flow = fund_flow_match.group(1).strip() if fund_flow_match else ''

            # 提取技术指标分析
            technical_lines = []
            macd_match = re.search(r'MACD:\s*([^\n]+)', content)
            if macd_match:
                technical_lines.append(f"MACD: {macd_match.group(1).strip()}")
            kdj_match = re.search(r'KDJ:\s*([^\n]+)', content)
            if kdj_match:
                technical_lines.append(f"KDJ: {kdj_match.group(1).strip()}")
            technical_analysis = ', '.join(technical_lines)

            analysis_results[stock_code] = {
                'suggestion': suggestion,
                'reason': reason,
                'urgency': urgency,
                'bid_ask_ratio': bid_ask_ratio,
                'bid_ask_analysis': bid_ask_analysis,
                'fund_flow': fund_flow,
                'fund_flow_analysis': '',  # 可以从逐笔交易部分提取
                'technical_analysis': technical_analysis
            }

            logger.debug(f"解析 {stock_name}({stock_code}) AI分析: {suggestion} ({urgency})")

        if analysis_results:
            logger.info(f"✅ 成功解析Task 2结构化格式，共{len(analysis_results)}只股票")

    except Exception as e:
        logger.error(f"解析AI分析结果失败: {e}")
        logger.exception("详细错误:")

    return analysis_results


def save_ai_analysis_to_db(analysis_results: dict):
    """
    将AI分析结果保存到数据库

    Args:
        analysis_results: 解析后的分析结果字典
    """
    from src.database.db_manager import get_db
    from src.database.models import Position
    from datetime import datetime

    db = get_db()

    try:
        with db.get_session() as session:
            for stock_code, analysis in analysis_results.items():
                # 查找持仓记录
                position = session.query(Position).filter(
                    Position.stock_code == stock_code,
                    Position.status == 'holding'
                ).first()

                if position:
                    # 更新AI分析字段
                    position.ai_sell_suggestion = analysis['suggestion']
                    position.ai_sell_reason = analysis['reason']
                    position.ai_urgency = analysis['urgency']
                    position.ai_analysis_time = datetime.now()
                    position.ai_bid_ask_ratio = analysis['bid_ask_ratio']
                    position.ai_bid_ask_analysis = analysis['bid_ask_analysis']
                    position.ai_fund_flow = analysis['fund_flow']
                    position.ai_fund_flow_analysis = analysis['fund_flow_analysis']
                    position.ai_technical_analysis = analysis['technical_analysis']

                    logger.success(f"✅ 已保存 {position.stock_name}({stock_code}) 的AI分析结果")
                else:
                    logger.warning(f"⚠️ 未找到 {stock_code} 的持仓记录")

            session.commit()
            logger.success(f"✅ 已保存 {len(analysis_results)} 只股票的AI分析结果到数据库")

    except Exception as e:
        logger.error(f"❌ 保存AI分析结果到数据库失败: {e}")
        raise


def run_position_monitor(session_id: str = None):
    """
    运行持仓监控

    Args:
        session_id: 用户session_id，如果为None则从contextvars获取

    Returns:
        监控结果
    """
    logger.info("🔍 开始持仓监控...")

    try:
        # 🔴 如果没有传入session_id，从contextvars获取
        if session_id is None:
            from src.agents.tools.database_tools import get_current_session_id
            session_id = get_current_session_id()

        # 运行AI分析
        crew = create_position_monitor_crew(session_id=session_id)
        result = crew.kickoff()

        # 解析AI分析结果
        result_text = str(result)
        analysis_results = parse_ai_analysis_result(result_text)

        # 保存到数据库
        if analysis_results:
            save_ai_analysis_to_db(analysis_results)
        else:
            logger.warning("⚠️ 未解析到AI分析结果，跳过数据库保存")

        logger.info("✅ 持仓监控完成")
        return result

    except Exception as e:
        logger.error(f"❌ 持仓监控失败: {e}")
        raise


if __name__ == "__main__":
    # 测试持仓监控
    result = run_position_monitor()
    print("\n" + "="*50)
    print("持仓监控结果:")
    print("="*50)
    print(result)

