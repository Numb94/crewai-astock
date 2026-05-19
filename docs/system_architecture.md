# 系统架构详解 (System Architecture)

本文档详细介绍了 CrewAI Stock V2.0 的系统设计、核心组件交互以及数据流向。

## 🏗️ 总体架构图

```mermaid
graph TD
    User[用户 (Web/API)] --> WebServer[Web服务器 (Flask)]
    WebServer --> Scheduler[调度器 (独立实例)]
    WebServer --> DB[(PostgreSQL)]
    
    subgraph "Multi-Agent Core (CrewAI)"
        RecommendationCrew[智能推荐 Crew]
        PositionMonitorCrew[持仓监控 Crew]
        EvaluationCrew[股票评估 Crew]
    end
    
    Scheduler --> RecommendationCrew
    Scheduler --> PositionMonitorCrew
    
    subgraph "Agent Team"
        A1[复盘分析师]
        A2[市场情报官]
        A3[智能选股师]
        A4[多维分析师]
        A5[风险管理官]
        A6[投资决策官]
        A7[持仓监控师]
    end
    
    RecommendationCrew --> A1 & A2 & A3 & A4 & A5 & A6
    PositionMonitorCrew --> A7
    
    subgraph "Data Layer"
        DSM[DataSourceManager]
        Zhitu[智兔 API]
        EM[东方财富爬虫]
        MCP[MCP Tools]
    end
    
    Agent Team --> DSM
    DSM --> Zhitu & EM & MCP
```

## 🧠 智能 Agent 体系

系统包含 7 个经过专门提示工程设计的 AI Agent，每个 Agent 都有明确的角色和工具集。

### 1. 复盘分析师 (Performance Analyst)
- **目标**：以史为鉴，优化策略。
- **核心任务**：
  - 分析昨日推荐表现（T+1胜率）。
  - 分析今日推荐的日内表现。
  - 统计各策略的历史胜率（Top 10）。
  - 提炼成功模式（5W1H分析）和失败教训（鱼骨图分析）。
- **输出**：策略排名报告、成功/失败案例分析。

### 2. 市场情报官 (Market Intelligence)
- **目标**：感知市场温度，动态调整方向。
- **核心任务**：
  - 分析涨停板数据（封板率、连板高度）。
  - 识别市场情绪（HOT/WARM/NEUTRAL/COLD）。
  - 结合复盘结果，动态生成选股参数（如：牛市追涨、熊市低吸）。
  - **冷启动模式**：当历史数据不足时，基于规则生成策略。
- **输出**：具体的选股参数（JSON格式），如 `price_change_min`, `sectors`, `concepts`。

### 3. 智能选股师 (Smart Screener)
- **目标**：广撒网，初筛优质标的。
- **核心任务**：
  - 接收市场情报官的参数。
  - 全市场扫描，过滤掉ST、退市股。
  - 执行基础技术过滤（如：均线排列、成交量要求）。
- **输出**：30-50只候选股票列表。

### 4. 多维分析师 (Multi-dimensional Analyst)
- **目标**：深度体检，全方位扫描。
- **核心任务**：
  - **并行分析**：同时对所有候选股进行分析。
  - **技术面**：MACD, KDJ, RSI, 均线形态。
  - **资金面**：逐笔交易分析（大单买入/卖出）、主力资金流向。
  - **基本面**：PE/PB, 营收增长, ROE。
  - **新闻面**：最近24/48小时新闻情感分析。
- **输出**：每只股票的综合评分报告。

### 5. 风险管理官 (Risk Manager)
- **目标**：一票否决，严控风险。
- **核心任务**：
  - 审核多维分析师的报告。
  - **一票否决**：发现重大风险（如：即将解禁、高位巨量阴线、利空新闻）直接剔除。
  - 设定个性化的止损位和止盈位。
- **输出**：通过审核的股票列表及风险提示。

### 6. 投资决策官 (Investment Officer)
- **目标**：最终拍板，仓位管理。
- **核心任务**：
  - 综合所有前序Agent的信息。
  - 结合当前持仓情况（避免行业过于集中）。
  - 给出最终操作建议（买入/观望）。
  - 分配建议仓位。
- **输出**：最终推荐列表（通常1-3只）。

### 7. 持仓监控师 (Position Monitor)
- **目标**：死盯盘口，卖在关键点。
- **核心任务**：
  - 实时获取五档盘口和逐笔明细。
  - **移动止盈**：根据盈利幅度动态调整回撤阈值。
  - 识别盘口异动（如：大单压盘、钓鱼线）。
  - 发出卖出预警（High/Medium/Low urgency）。

## 🔄 核心工作流 (Crews)

### 智能推荐流程 (`SmartRecommendationCrew`)
这是系统最核心的每日任务，通常在盘后（复盘）或盘中（午盘）运行。
1. **复盘**：分析师回顾历史数据。
2. **定策**：情报官根据复盘+今日行情定策略。
3. **初筛**：选股师选出30-50只。
4. **精选**：多维分析师+风险官+决策官层层过滤，最终产出1-3只精选股。

### 持仓监控流程 (`PositionMonitorCrew`)
这是一个高频运行的轻量级任务，专注于已持有的股票。
1. **更新数据**：获取持仓股的实时价格和盘口。
2. **规则检查**：是否触发硬性止盈止损。
3. **AI诊断**：分析盘口买卖气势，判断是否"该涨不涨"或"诱多"。
4. **预警**：通过PushPlus推送到微信。

## 💾 数据源管理 (DataSourceManager)

系统采用统一的 `DataSourceManager` 类来管理所有外部数据交互，实现了高可用性设计。

### 策略路由
- **行情数据**：首选智兔API（速度快），备选东方财富爬虫。
- **盘口数据**：首选东方财富爬虫（数据全），备选智兔API。
- **历史数据**：首选智兔API，备选MCP工具。

### 容错与缓存
- **自动降级**：主源失败自动切换备源。
- **缓存机制**：5分钟内存缓存，减少API调用，防止超限。
- **并发控制**：智兔API限制3000次/分钟，系统内部有速率限制。

## 👥 多用户隔离机制

为了支持多人使用，系统在内存和数据库层面实现了完全隔离。

1. **Session ID**：每个请求和调度任务都绑定唯一的 `session_id` (通常是用户名)。
2. **ContextVar**：使用 Python 的 `contextvars` 在异步/线程环境中传递用户上下文。
3. **独立容器**：`UserContainer` 为每个用户维护独立的 `Scheduler` 实例和全局变量。
4. **数据隔离**：所有数据库查询自动附加 `session_id` 过滤条件。

## 🔌 外部接口

- **PushPlus**：用于发送实时的微信通知（推荐结果、风险预警）。
- **同花顺 (ThsTrader)**：通过 `xiadan` 库对接Windows版同花顺客户端，实现实盘交易（可选）。
- **MCP Server**：通过 Model Context Protocol 连接外部高级工具。
