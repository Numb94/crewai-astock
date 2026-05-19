# 系统架构文档

> CrewAI A-Stock 的技术架构设计文档（开源版）

## 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                       Web 应用层                            │
│  Flask + Vue3 + Element Plus + ECharts                      │
│  - 多用户支持（Cookie 持久化 30 天）                        │
│  - 实时 K 线图 + 流式 AI 推荐（SSE）                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       API 接口层                            │
│  11 个 Flask 蓝图，RESTful + SSE 流式推送                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    CrewAI 智能体层                          │
│  7 个 Agent，3 个 Crew，48+ 工具，Memory 长期记忆           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       数据源层                              │
│  智兔 API（主力）+ 东方财富爬虫 + Grok（实时搜索）+ Tavily   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       数据库层                              │
│  SQLite + SQLAlchemy ORM，多用户隔离                        │
└─────────────────────────────────────────────────────────────┘
```

## 数据库层

### 15 张 ORM 表

| 表名 | 用途 | 多用户隔离 |
|---|---|---|
| `candidates` | 推荐候选股票池，含 6 维评分和绩效跟踪 | ✅ |
| `positions` | 持仓记录，含移动止盈和 AI 分析缓存 | ✅ |
| `transactions` | 交易记录（买入 / 卖出） | ✅ |
| `reviews` | 每日复盘 | ✅ |
| `agent_memory` | Agent 历史决策与反思 | ✅ |
| `market_sentiment` | 每日市场情绪 | ✅ |
| `system_config` | 动态系统配置 | ✅ |
| `strategy_executions` | 策略执行记录 | ✅ |
| `strategy_performance` | 策略绩效统计 | ✅ |
| `strategy_weights` | 策略权重（自进化） | ✅ |
| `agent_decision_logs` | Agent 决策日志 | ✅ |
| `meeting_logs` | Agent 协作"会议"记录 | ✅ |
| `stock_concepts` | 股票概念板块标签 | ❌（全局） |
| `agent_context` | Agent 间结构化数据传递总线 | ✅ |

### 关键设计

- **多用户隔离**：除 `stock_concepts` 外，所有表带 `session_id` 字段
- **价格精度**：所有价格 `DECIMAL(10,3)`，避免浮点误差
- **T+1 约束**：`positions.can_sell_date` 强制 T+1 规则
- **绩效跟踪**：`candidates` 表内置次日开盘 / 最高 / 收盘三个价格的收益率字段
- **AI 分析缓存**：`positions` 表缓存卖点建议、盘口分析、资金流向，减少重复 LLM 调用

### 非 ORM 表

- `stock_basic_info`：股票基础信息（5161 只股票代码、名称、板块），由 `scripts/init_stock_basic_info.py` 创建

## API 层（11 个蓝图）

| 蓝图 | 主要端点 | 功能 |
|---|---|---|
| `position_api` | `/api/positions/*` | 持仓查询 / 买入 / 卖出 / 监控 |
| `recommendation_api` | `/api/recommendations/latest` | 最近推荐 |
| `strategy_api` | `/api/strategies/performance` | 策略表现 |
| `market_api` | `/api/market/sentiment` | 市场情绪 |
| `account_api` | `/api/account/*` | 账户管理 |
| `market_insights_api` | `/api/market/ai-insights` | AI 市场洞察 |
| `performance_api` | `/api/performance/comparison` | 绩效对比 |
| `kline_api` | `/api/kline/<code>` | K 线（带推荐标记） |
| `crew_stream_api` | `/api/crew/stream` | CrewAI SSE 流式输出 |
| `stock_evaluation_api` | `/api/stock/evaluate` | 个股深度评估 |
| `market_data_api` | `/sectors`, `/limit-up` | 板块 / 涨停 |

## CrewAI 智能体层

### 7 个 Agent

| Agent | 函数 | 工具数 | 关键能力 |
|---|---|---|---|
| 复盘分析师 | `create_performance_analyst` | 3 | 绩效归因、5W1H 成功 / 鱼骨图失败 |
| 市场情报官 | `create_market_intelligence` | 8 | 市场阶段识别、动态策略生成 |
| 智能选股师 | `create_smart_screener` | 8 | 动态筛选、涨停股过滤 |
| 多维分析师 | `create_multi_dimensional_analyst` | 13 | 6 维并行分析、自动分批 |
| 风险管理官 | `create_risk_manager` | 6 | 一票否决、风险量化 |
| 投资决策官 | `create_investment_officer` | 6 | 智能仓位分配、推送 |
| 持仓监控师 | `create_position_monitor` | 8 | 移动止盈、隔夜短线策略 |

所有 Agent 定义集中在 `src/agents/smart_agents.py`。

### 3 个 Crew

| Crew | 文件 | Agent 数 | Task 数 | 用途 |
|---|---|---|---|---|
| 智能推荐 | `smart_recommendation_crew.py` | 6 | 6 | 完整推荐流水线 |
| 股票评估 | `stock_evaluation_crew.py` | 4 | 4 | 评估指定股票 |
| 持仓监控 | `position_monitor_crew.py` | 1 | 3 | 持仓卖点判断 |

### CrewAI Memory

- 使用硅基流动 `BAAI/bge-m3` 作为 Embeddings
- 仅启用 long-term memory（禁用 short-term 与 entity，避免 token 膨胀）
- 共享存储路径 `./storage/long_term_memory.db`
- 可选预热脚本 `scripts/warmup_memory.py` 导入历史经验

## 数据源层

| 数据源 | 类型 | 角色 | 文件 |
|---|---|---|---|
| 智兔 API | API | 主力 | `src/tools/zhitu_api.py` |
| 东方财富爬虫 | 爬虫 | 辅助 | `src/tools/eastmoney_crawler.py` |
| Grok | API | 主力（新闻 / 情绪） | `src/tools/grok_client.py` |
| Tavily | API | 备用（新闻） | `src/tools/tavily_api.py` |
| 数据源管理器 | 管理器 | 统一接口 | `src/tools/data_source_manager.py` |
| 新闻源管理器 | 管理器 | 新闻聚合（Tavily） | `src/tools/news_source_manager.py` |

### 智兔 API

主要功能：
- 股票列表 / 实时行情 / K 线
- 技术指标（MACD、KDJ、BOLL、MA 等）
- 涨停板池 / 财务指标
- 历史逐笔数据（每日 21:00 更新）

速率限制：包年版 3000 次/分钟。

### Grok（实时搜索）

通过 xAI Grok API 提供：
- 股票相关新闻搜索
- 社区情绪分析（雪球 / 东财股吧 / 淘股吧）
- 市场热点话题
- 话题趋势分析

`grok_client.py` 是简单 OpenAI SDK 封装，模型默认 `grok-beta`。

## 核心模块层

### 用户容器管理 `src/core/user_container.py`

每个用户拥有独立的 `UserContainer`，含：
- `scheduler_instance`：StockScheduler 实例
- `lock`：创建保护锁
- `last_active`：自动清理依据（默认 30 分钟空闲）

### Scheduler `scheduler.py`

每用户一个独立调度器，定时任务：
- 持仓监控（每 1 分钟，交易时间内）
- 新闻监控（动态频率，5–30 分钟）
- 绩效更新（每日 17:00）

## Web 应用层

- **多用户**：Cookie + session_id（30 天有效期）
- **页面**：`/trading`（主交易系统）、`/tools`、`/login`
- **前端**：Jinja2 模板 + Vue3 + Element Plus + ECharts + Bootstrap

## 安全与性能

### 安全

- 全部使用 SQLAlchemy ORM 参数化查询
- Session 隔离防止用户数据交叉
- 敏感凭据全部走 `.env`，仓库内无硬编码

### 性能

- 关键字段建立索引（`stock_code`, `session_id`, `recommend_time` 等）
- K 线 5 分钟缓存
- 多维分析 Task 内部并行分析多只股票
- CrewAI 异步执行不阻塞主线程

## 扩展性

- 新增 Agent：在 `src/agents/smart_agents.py` 添加 `create_xxx_agent()` 工厂函数
- 新增 Crew：在 `src/crews/` 创建新文件，按现有模式编排
- 新增数据源：实现统一接口，注册到 `data_source_manager.py`
- 新增策略：策略由 AI 动态生成，无需硬编码；如需固定策略，扩展提示词模板即可

## 已移除的功能（开源版）

为了开源合规与凭据安全，以下功能未包含：
- 同花顺 / QMT 实盘交易接入
- TrendRadar 新闻聚合服务（GPL v3 协议冲突）
- 自动买入 / 自动卖出闭环

如需研究上述功能，请参考各开源项目原仓库自行集成，并自行承担合规与安全责任。
