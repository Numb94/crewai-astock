# Stock MCP 社区评论集成指南

**版本**: 1.0  
**日期**: 2025-11-20  
**状态**: ✅ 生产就绪

---

## 📚 快速导航

- [功能概述](#功能概述)
- [架构设计](#架构设计)
- [使用方法](#使用方法)
- [API参考](#api参考)
- [最佳实践](#最佳实践)
- [故障排查](#故障排查)

---

## 功能概述

### 核心功能

✅ **三大平台社区评论获取**:
- 雪球（专业投资者讨论）
- 东方财富股吧（散户聚集地）
- 淘股吧（短线高手）

✅ **CrewAI Agent集成**:
- 市场情报官Agent可直接使用
- 自动格式化输出
- 完善的错误处理

✅ **高性能异步调用**:
- 使用MCP协议
- 支持TOON格式（简洁高效）
- 5分钟缓存机制

---

## 架构设计

### 三层架构

```
┌─────────────────────────────────────────┐
│         CrewAI Agent Layer              │
│  (市场情报官使用社区评论工具)            │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Agent Tools Layer               │
│  (community_sentiment_tools.py)         │
│  - get_stock_community_comments         │
│  - get_xueqiu_comments                  │
│  - get_eastmoney_comments               │
│  - get_taoguba_comments                 │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         MCP Client Layer                │
│  (stock_mcp_community.py)               │
│  - StockMCPCommunity                    │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         Stock MCP Server                │
│  (https://stock.doiiars.com/mcp)        │
└─────────────────────────────────────────┘
```

---

## 使用方法

### 方法1: 在CrewAI Agent中使用（推荐）

```python
from src.agents.smart_agents import create_market_intelligence
from crewai import Task, Crew

# 创建市场情报官Agent
agent = create_market_intelligence()

# 创建任务
task = Task(
    description="""
    分析平安银行(000001)的社区情绪：
    1. 使用 get_stock_community_comments 获取评论
    2. 分析散户情绪（乐观/悲观/分歧）
    3. 识别高频关键词和讨论热点
    4. 判断是否存在异常讨论热度
    """,
    expected_output="社区情绪分析报告",
    agent=agent
)

# 执行
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
```

### 方法2: 直接调用Agent工具

```python
from src.agents.tools.community_sentiment_tools import get_stock_community_comments

# 获取评论（注意：需要使用.func调用）
result = get_stock_community_comments.func("000001", max_items=20)
print(result)
```

### 方法3: 使用MCP客户端

```python
from src.tools.stock_mcp_community import get_community_client
import asyncio

# 创建客户端
client = get_community_client()

# 获取所有平台评论
comments = asyncio.run(client.get_all_platforms_comments("000001"))
print(comments)

# 获取单个平台评论
xq_comments = asyncio.run(client.get_xueqiu_comments("000001"))
em_comments = asyncio.run(client.get_eastmoney_comments("000001"))
tgb_comments = asyncio.run(client.get_taoguba_comments("000001"))
```

---

## API参考

### Agent工具

#### `get_stock_community_comments`

获取股票在社区平台的讨论评论（雪球+东财股吧+淘股吧）

**参数**:
- `stock_code` (str): 股票代码（6位数字，如"000001"）
- `max_items` (int): 每个平台的最大评论数，默认20条

**返回**: 社区评论摘要（包含散户情绪、讨论热度、关键观点）

**示例**:
```python
result = get_stock_community_comments.func("000001", max_items=20)
```

---

#### `get_xueqiu_comments`

获取股票在雪球的讨论评论

**参数**:
- `stock_code` (str): 股票代码
- `max_items` (int): 最大评论数，默认20条

**返回**: 雪球评论数据

---

#### `get_eastmoney_comments`

获取股票在东方财富股吧的讨论评论

**参数**:
- `stock_code` (str): 股票代码
- `max_items` (int): 最大评论数，默认20条

**返回**: 东财股吧评论数据

---

#### `get_taoguba_comments`

获取股票在淘股吧的讨论评论

**参数**:
- `stock_code` (str): 股票代码
- `max_items` (int): 最大评论数，默认20条

**返回**: 淘股吧评论数据

---

### MCP客户端

#### `StockMCPCommunity`

**方法**:
- `async get_xueqiu_comments(symbol, max_items, timeout)` - 获取雪球评论
- `async get_eastmoney_comments(symbol, max_items, timeout)` - 获取东财评论
- `async get_taoguba_comments(symbol, max_items, timeout)` - 获取淘股吧评论
- `async get_all_platforms_comments(symbol, max_items, timeout)` - 获取所有平台评论

---

## 最佳实践

### 1. 社区情绪分析场景

**适用场景**:
- ✅ 判断散户情绪是否过热（追涨风险）
- ✅ 识别市场分歧（可能变盘信号）
- ✅ 发现新的题材和热点
- ✅ 验证新闻热点的真实性

**分析维度**:
- **情绪倾向**: 乐观/悲观/分歧
- **讨论热度**: 评论数量、点赞数
- **关键词**: 高频词汇、题材概念
- **异常信号**: 突然增加的讨论量

### 2. 三大平台特点

| 平台 | 用户特点 | 关注重点 | 推荐度 |
|------|----------|----------|--------|
| **雪球** | 专业投资者 | 基本面、技术面分析 | ⭐⭐⭐⭐⭐ |
| **东财股吧** | 散户聚集地 | 市场情绪、短期波动 | ⭐⭐⭐⭐ |
| **淘股吧** | 短线高手 | 题材热点、涨停板 | ⭐⭐⭐⭐ |

### 3. 推荐使用方式

**推荐**: 使用 `get_stock_community_comments`
- ✅ 一次性获取三个平台评论
- ✅ 数据更全面，分析更准确
- ✅ 性能优化，并行获取

---

## 故障排查

### 问题1: MCP连接超时

**错误**: `TimeoutError: Couldn't connect to the MCP server`

**解决方案**:
1. 检查网络连接
2. 增加超时时间：`STOCK_MCP_CONNECT_TIMEOUT=120`
3. 检查MCP服务器状态

### 问题2: 工具调用失败

**错误**: `'Tool' object is not callable`

**解决方案**:
使用 `.func` 调用工具：
```python
# ❌ 错误
result = get_stock_community_comments("000001")

# ✅ 正确
result = get_stock_community_comments.func("000001")
```

### 问题3: 数据为空

**可能原因**:
- 股票代码错误
- 该股票没有社区讨论
- MCP服务器缓存未更新

**解决方案**:
1. 检查股票代码格式（6位数字）
2. 尝试其他热门股票
3. 等待5分钟后重试（缓存刷新）

---

**维护者**: AI Architect  
**最后更新**: 2025-11-20  
**使用模型**: Claude Sonnet 4.5

