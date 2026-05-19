#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - 股票评估Crew

专门用于评估指定股票，不推送通知
4个Agent协作完成股票评估：
1. 智能选股师（验证股票） → 2. 多维分析师（深度分析） → 3. 风险管理官（风险评估） → 4. 投资决策官（给出建议）
"""

from crewai import Crew, Task, Process
from src.agents.smart_agents import create_all_smart_agents
from datetime import datetime
from loguru import logger


def create_stock_evaluation_crew(stock_codes: str, session_id: str = 'default'):
    """
    创建股票评估Crew
    
    Args:
        stock_codes: 股票代码（逗号分隔，如：600000,000001,002163）
        session_id: 用户session_id，用于数据隔离
    
    Returns:
        Crew实例
    """
    logger.info(f"🏗️ 创建股票评估Crew: stock_codes={stock_codes}, session_id={session_id[:8]}...")
    
    # ✅ 设置当前session_id（使用contextvars）
    from src.agents.tools.database_tools import set_current_session_id
    set_current_session_id(session_id)
    
    # 创建所有Agent
    agents = create_all_smart_agents()
    
    # ========================================
    # Task 1: 验证股票并获取基本信息
    # ========================================
    task_validate = Task(
        description=f'''验证用户输入的股票代码，获取基本信息。

## 📋 你需要完成的任务

### 第1步：验证股票代码
**工具**：analyze_stocks_parallel

**任务**：
- 验证股票代码：{stock_codes}
- 获取股票基本信息（名称、行业、市值等）
- 获取最新价格和涨跌幅
- 如果股票代码无效，返回错误信息

### 第2步：输出验证结果
**格式**：
```
## 📊 股票基本信息

| 股票代码 | 股票名称 | 最新价 | 涨跌幅 | 行业 | 市值 |
|---------|---------|--------|--------|------|------|
| 600000  | 浦发银行 | 8.50   | +1.2%  | 银行 | 2500亿 |
```

**重要说明**：
- ✅ 如果股票代码无效，直接返回错误信息，不继续后续分析
- ✅ 如果股票代码有效，输出基本信息，继续后续分析
''',
        agent=agents['smart_screener'],
        expected_output='股票基本信息表格（Markdown格式）'
    )
    
    # ========================================
    # Task 2: 多维度深度分析
    # ========================================
    task_analyze = Task(
        description=f'''对股票进行多维度深度分析（技术面、资金面、基本面、新闻面、社区情绪）。

## 📋 你需要完成的任务

### 第1步：技术面分析
**工具**：analyze_stocks_parallel

**任务**：
- 分析K线形态（趋势、支撑位、压力位）
- 分析技术指标（MACD、KDJ、RSI等）
- 判断技术面强弱

### 第2步：资金面分析
**工具**：analyze_stocks_parallel

**任务**：
- 分析资金流向（主力资金、散户资金）
- 分析成交量变化
- 判断资金面强弱

### 第3步：基本面分析
**工具**：analyze_stocks_parallel

**任务**：
- 分析财务数据（营收、利润、ROE等）
- 分析估值水平（PE、PB等）
- 判断基本面强弱

### 第4步：新闻面分析
**工具**：analyze_stocks_parallel

**任务**：
- 搜索最新新闻
- 分析新闻情绪（利好/利空）
- 判断新闻面影响

### 第5步：社区情绪分析
**工具**：get_stock_community_comments

**任务**：
- 获取雪球、东财股吧、淘股吧的评论
- 分析散户情绪（乐观/悲观/分歧）
- 识别讨论热度和关键观点

### 第6步：输出分析结果
**格式**：
```
## 📊 多维度分析

### 技术面 ⭐⭐⭐⭐
- K线形态：上升趋势，突破压力位
- 技术指标：MACD金叉，KDJ超买
- 综合评分：80分

### 资金面 ⭐⭐⭐
- 资金流向：主力资金流入
- 成交量：放量上涨
- 综合评分：70分

### 基本面 ⭐⭐⭐⭐⭐
- 财务数据：营收增长30%，利润增长50%
- 估值水平：PE 15倍，低于行业平均
- 综合评分：90分

### 新闻面 ⭐⭐⭐⭐
- 最新新闻：公司中标重大项目
- 新闻情绪：利好
- 综合评分：85分

### 社区情绪 ⭐⭐⭐
- 散户情绪：适度乐观，有分歧
- 讨论热度：中等
- 综合评分：75分
```
''',
        agent=agents['multi_analyst'],
        expected_output='多维度分析报告（Markdown格式）',
        context=[task_validate]
    )
    
    # ========================================
    # Task 3: 风险评估
    # ========================================
    task_risk = Task(
        description=f'''评估股票的风险等级，给出风险提示。

## 📋 你需要完成的任务

### 第1步：评估风险等级
**参考信息**：
- 技术面分析结果
- 资金面分析结果
- 基本面分析结果
- 新闻面分析结果
- 社区情绪分析结果

**任务**：
- 评估技术风险（如：超买、破位等）
- 评估资金风险（如：主力出货、成交量萎缩等）
- 评估基本面风险（如：业绩下滑、估值过高等）
- 评估新闻风险（如：利空消息、监管风险等）
- 评估情绪风险（如：散户过度乐观、讨论热度异常等）
- 综合评估风险等级（低风险、中风险、高风险）

### 第2步：输出风险评估
**格式**：
```
## ⚠️ 风险评估

### 风险等级：中风险 ⚠️

### 风险点：
1. **技术风险**：KDJ超买，短期可能回调
2. **资金风险**：主力资金流入放缓
3. **基本面风险**：估值略高于行业平均
4. **新闻风险**：无重大利空
5. **情绪风险**：散户情绪适度乐观，无过热迹象

### 风险提示：
- ⚠️ 短期技术面超买，建议等待回调后再买入
- ⚠️ 主力资金流入放缓，需要关注资金面变化
- ✅ 基本面良好，长期投资价值较高
```
''',
        agent=agents['risk_manager'],
        expected_output='风险评估报告（Markdown格式）',
        context=[task_validate, task_analyze]
    )

    # ========================================
    # Task 4: 投资决策（不推送通知）
    # ========================================
    task_decision = Task(
        description=f'''综合所有分析结果，给出投资建议和评分，**不推送通知**。

## 📋 你需要完成的任务

### 第1步：获取实时价格
**工具**：get_realtime_prices

**任务**：
- 获取股票当前实时价格
- 用于计算目标价位和止损价位

### 第2步：综合评分
**参考信息**：
- 股票基本信息
- 多维度分析结果
- 风险评估结果
- **当前实时价格**（从第1步获取）

**任务**：
- 综合技术面、资金面、基本面、新闻面、社区情绪评分
- 计算综合评分（0-100分）
- 给出投资建议（强烈推荐、推荐、谨慎推荐、观望、不推荐）

### 第3步：输出投资决策
**格式**：
```
## 🎯 投资决策

### 当前价格：XX.XX元

### 综合评分：85分 ⭐⭐⭐⭐

### 投资建议：推荐 👍

### 理由：
1. **技术面**：上升趋势，突破压力位，技术面强势
2. **资金面**：主力资金流入，成交量放大，资金面良好
3. **基本面**：业绩增长强劲，估值合理，基本面优秀
4. **新闻面**：利好消息，市场情绪积极

### 操作建议：
- ✅ **买入时机**：等待回调至支撑位（XX元）附近买入
- ✅ **目标价位**：短期目标XX元，中期目标XX元
- ✅ **止损价位**：跌破XX元止损
- ⚠️ **风险提示**：短期技术面超买，建议分批买入

### 仓位建议：
- 建议仓位：20-30%
- 风险等级：中风险
```

**重要说明**：
- ❌ **不推送通知**（这是股票评估，不是AI推荐）
- ❌ **不查询持仓**（这是单个股票评估，不需要对比持仓）
- ✅ **必须获取实时价格**（用于计算目标价位和止损价位）
- ✅ **必须在输出中显示当前价格**
- ✅ 只输出投资决策报告
''',
        agent=agents['investment_officer'],
        expected_output='投资决策报告（Markdown格式）',
        context=[task_validate, task_analyze, task_risk]
    )

    # 创建Crew
    crew = Crew(
        agents=[
            agents['smart_screener'],
            agents['multi_analyst'],
            agents['risk_manager'],
            agents['investment_officer']
        ],
        tasks=[
            task_validate,
            task_analyze,
            task_risk,
            task_decision
        ],
        process=Process.sequential,  # 顺序执行
        verbose=False,  # 🔴 关闭详细日志，减少控制台输出
        memory=False,  # 禁用memory（DeepSeek不支持embeddings）
        cache=False    # 禁用cache（避免response_format错误）
    )

    logger.info(f"✅ 股票评估Crew创建完成: {len(crew.tasks)}个任务")

    return crew

