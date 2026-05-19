# CrewAI Stock — AI 协作指南

> 这份文档面向在本仓库工作的 AI 助手（如 Claude Code），用于快速建立项目心智模型。

## 项目定位

基于 CrewAI 多智能体协作的 A 股智能分析与推荐系统。**仅供学习研究，不含实盘交易**。

## 模块索引

| 模块 | 路径 | 职责 |
|---|---|---|
| agents | `src/agents/` | 7 个 Agent 定义 + 48+ 工具 |
| api | `src/api/` | Flask 蓝图（11 个），含 SSE 流式 |
| config | `src/config/` | LLM / Embeddings 配置 |
| core | `src/core/` | 用户容器管理、新闻监控调度 |
| crews | `src/crews/` | 3 个 Crew 配置（推荐 / 评估 / 监控） |
| database | `src/database/` | ORM 模型（14 张表）+ DB 管理 |
| tools | `src/tools/` | 数据源适配（智兔 / 东财 / Grok / Tavily） |
| utils | `src/utils/` | 通用工具（推送、缓存、交易日历） |

## 关键架构决策

- **多用户隔离**：所有 ORM 表带 `session_id` 字段，每个用户有独立的 Scheduler 实例
- **Agent 间通信**：通过 `agent_context` 表传递结构化数据，避免纯自然语言信息丢失
- **价格类型**：所有价格字段使用 `DECIMAL(10,3)`，避免浮点误差
- **CrewAI Memory**：仅启用 long-term memory（避免 short-term 的 token 膨胀），用硅基流动 Embeddings
- **Crew 执行模式**：Sequential，Task 4（多维分析）内部并行

## 7 个 Agent 流水线

```
复盘分析师 → 市场情报官 → 智能选股师 → 多维分析师 → 风险管理官 → 投资决策官
                                                          ↓ 一票否决
持仓监控师（独立 Crew，5 分钟轮询）
```

## 数据库表（14 张 ORM + 1 张非 ORM + 1 张新闻）

`candidates` / `positions` / `transactions` / `reviews` / `agent_memory` / `market_sentiment` /
`system_config` / `strategy_executions` / `strategy_performance` / `strategy_weights` /
`agent_decision_logs` / `meeting_logs` / `stock_concepts` / `agent_context` / `market_news` /
`stock_basic_info`（非 ORM，5161 只股票基础信息）

## 数据源

| 数据源 | 角色 | 用途 |
|---|---|---|
| 智兔 API | 主力 | 股票行情 / 技术指标 / 涨停板 / 财务 / 历史逐笔 |
| 东方财富爬虫 | 辅助 | 实时行情 / 板块 / 当天逐笔 |
| Grok | 主力 | 实时新闻 / 社区情绪（具备实时搜索能力） |
| Tavily | 备用 | 新闻搜索（紧急情况调用） |

## 开发约定

- **Python**：PEP 8，使用 type hints，Google 风格 docstring
- **Git**：约定式提交（`feat:` / `fix:` / `docs:` / `refactor:` 等）
- **多用户**：新增表必须有 `session_id` 字段（除非确实是全局共享）
- **价格字段**：必须用 `DECIMAL`，不用 `Float`
- **凭据**：严禁硬编码 API key / 密码，全部走 `.env`

## 已移除的功能

开源版本相对原工程移除：
- 同花顺 / QMT 实盘交易接入
- TrendRadar 新闻聚合服务
- 自动买入 / 自动卖出闭环

涉及这些功能的历史代码已删除。如果在 docs/ 旧文档中遇到相关说明，以本文档为准。

## 启动命令

```bash
# 初始化数据库
python -m src.database.init_db

# 启动 Web 应用
python app.py
# → http://localhost:5000
```

更详细的架构说明见 [ARCHITECTURE.md](ARCHITECTURE.md)，开发指南见 [DEVELOPMENT.md](DEVELOPMENT.md)。
