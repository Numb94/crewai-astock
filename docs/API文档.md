# API接口文档

> CrewAI Stock - 完整的REST API接口说明

**版本**: v2.0  
**基础URL**: `http://localhost:7000`  
**更新时间**: 2025-11-10

---

## 📋 目录

- [1. 持仓监控API](#1-持仓监控api)
- [2. 推荐API](#2-推荐api)
- [3. 策略表现API](#3-策略表现api)
- [4. 市场情绪API](#4-市场情绪api)
- [5. 账户资金管理API](#5-账户资金管理api)
- [6. 市场洞察API](#6-市场洞察api)
- [7. 绩效API](#7-绩效api)
- [8. K线数据API](#8-k线数据api)
- [9. CrewAI流式推送API](#9-crewai流式推送api)
- [10. 股票评估API](#10-股票评估api)
- [11. 市场数据API](#11-市场数据api)

---

## 1. 持仓监控API

### 1.1 获取持仓监控数据

**端点**: `GET /api/positions/monitor`

**描述**: 获取所有持仓及智能卖点建议

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "positions": [
      {
        "id": 1,
        "stock_code": "600000",
        "stock_name": "浦发银行",
        "buy_price": 10.50,
        "current_price": 11.20,
        "quantity": 1000,
        "profit_loss": 700.00,
        "return_rate": 6.67,
        "sell_suggestion": "持有",
        "reason": "技术面良好，继续持有"
      }
    ],
    "total_profit_loss": 2500.00,
    "total_return_rate": 5.25
  }
}
```

### 1.2 买入股票

**端点**: `POST /api/positions/buy`

**描述**: 买入股票

**请求体**:
```json
{
  "stock_code": "600000",
  "stock_name": "浦发银行",
  "buy_price": 10.50,
  "quantity": 1000,
  "strategy": "龙头战法"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "买入成功",
  "data": {
    "position_id": 1,
    "transaction_id": 1
  }
}
```

### 1.3 卖出股票

**端点**: `POST /api/positions/sell`

**描述**: 卖出股票

**请求体**:
```json
{
  "position_id": 1,
  "sell_price": 11.20,
  "quantity": 1000,
  "reason": "止盈"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "卖出成功",
  "data": {
    "transaction_id": 2,
    "profit_loss": 700.00,
    "return_rate": 6.67
  }
}
```

---

## 2. 推荐API

### 2.1 获取最新推荐

**端点**: `GET /api/recommendations/latest`

**描述**: 获取最近3天的AI推荐（包括已过期的推荐）

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "recommendations": [
      {
        "id": 1,
        "stock_code": "600000",
        "stock_name": "浦发银行",
        "recommend_price": 10.50,
        "current_price": 11.20,
        "change_pct": 6.67,
        "strategy": "龙头战法",
        "final_score": 88.5,
        "reason": "技术面突破，资金流入明显",
        "target_price": 12.00,
        "recommend_date": "2025-11-10 09:30:00",
        "recommend_track": "track2_next"
      }
    ]
  }
}
```

---

## 3. 策略表现API

### 3.1 获取策略表现

**端点**: `GET /api/strategies/performance`

**描述**: 获取8大策略的胜率、收益率等统计数据

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "strategies": [
      {
        "name": "龙头战法",
        "win_rate": 70.5,
        "avg_return": 5.2,
        "trade_count": 10
      }
    ]
  }
}
```

---

## 4. 市场情绪API

### 4.1 获取市场情绪数据

**端点**: `GET /api/market/sentiment`

**描述**: 获取市场状态、情绪评分、涨跌停数据、热点题材等

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "market_state": "hot",
    "sentiment_score": 85,
    "limit_up_count": 120,
    "limit_down_count": 5,
    "gain_count": 3200,
    "loss_count": 1800,
    "hot_topics": [
      {"name": "AI", "count": 15},
      {"name": "新能源", "count": 12}
    ]
  }
}
```

---

## 5. 账户资金管理API

### 5.1 获取账户信息

**端点**: `GET /api/account/info`

**描述**: 获取账户资金信息

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "initial_capital": 100000,
    "additional_capital": 0,
    "withdrawn_capital": 0,
    "total_capital": 100000,
    "available_capital": 95000,
    "position_value": 5000,
    "total_profit_loss": 0,
    "total_return_rate": 0,
    "last_updated": "2025-11-04 15:30:00"
  }
}
```

### 5.2 配置账户资金

**端点**: `POST /api/account/config`

**描述**: 配置账户资金（设置初始资金、追加资金、提取资金）

**请求体**:
```json
{
  "action": "set_initial",
  "amount": 100000
}
```

**action可选值**:
- `set_initial` - 设置初始资金
- `add_capital` - 追加资金
- `withdraw_capital` - 提取资金

**响应示例**:
```json
{
  "success": true,
  "message": "操作成功",
  "data": {
    "total_capital": 100000,
    "available_capital": 95000
  }
}
```

---

## 6. 市场洞察API

### 6.1 获取AI市场解读

**端点**: `GET /api/market/ai-insights`

**描述**: 获取AI独有的市场洞察（非简单数据展示）

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "meeting_time": "2025-11-04 09:00:00",
    "market_state": "hot",
    "sentiment_score": 90,
    "ceo_view": "当前市场情绪高涨...",
    "cmo_analysis": "AI板块持续活跃...",
    "cro_warning": "市场短期过热...",
    "cso_strategy": "建议采用龙头战法...",
    "hot_topics": ["AI", "新能源", "芯片"]
  }
}
```

---

## 7. 绩效API

### 7.1 获取绩效统计

**端点**: `GET /api/performance/stats`

**描述**: 获取交易绩效统计数据

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "total_trades": 50,
    "win_trades": 35,
    "loss_trades": 15,
    "win_rate": 70.0,
    "total_profit": 25000,
    "total_loss": -5000,
    "net_profit": 20000,
    "avg_profit_per_trade": 400
  }
}
```

---

## 8. K线数据API

### 8.1 获取K线数据

**端点**: `GET /api/kline/data`

**描述**: 获取股票K线数据（5分钟级别）

**请求参数**:
- `stock_code` (必需): 股票代码
- `period` (可选): 周期（默认5m）
- `count` (可选): 数据条数（默认100）

**示例**: `GET /api/kline/data?stock_code=600000&period=5m&count=100`

**响应示例**:
```json
{
  "success": true,
  "data": {
    "stock_code": "600000",
    "stock_name": "浦发银行",
    "kline_data": [
      {
        "time": "2025-11-10 09:30:00",
        "open": 10.50,
        "high": 10.60,
        "low": 10.45,
        "close": 10.55,
        "volume": 1000000
      }
    ]
  }
}
```

---

## 9. CrewAI流式推送API

### 9.1 SSE流式推送

**端点**: `GET /api/crew/stream/{session_id}`

**描述**: SSE流式推送CrewAI执行过程

**请求参数**:
- `session_id` (路径参数): 用户会话ID

**响应格式**: Server-Sent Events (SSE)

**事件类型**:
- `agent_start` - Agent开始执行
- `agent_output` - Agent输出
- `task_complete` - 任务完成
- `error` - 错误信息

**示例**:
```
data: {"type": "agent_start", "agent": "复盘分析师", "message": "开始分析昨日推荐..."}

data: {"type": "agent_output", "agent": "复盘分析师", "output": "昨日推荐3只股票..."}

data: {"type": "task_complete", "task": "复盘分析", "result": "..."}
```

### 9.2 清空消息队列

**端点**: `POST /api/crew/clear/{session_id}`

**描述**: 清空指定会话的消息队列

**请求参数**:
- `session_id` (路径参数): 用户会话ID

**响应示例**:
```json
{
  "success": true,
  "message": "消息队列已清空"
}
```

---

## 10. 股票评估API

### 10.1 评估股票

**端点**: `GET /api/stock/evaluate`

**描述**: 评估指定股票（SSE流式推送）

**请求参数**:
- `stock_codes` (必需): 股票代码（逗号分隔，如：600000,000001,002163）
- `session_id` (必需): 用户session_id

**示例**: `GET /api/stock/evaluate?stock_codes=600000,000001&session_id=user123`

**响应格式**: Server-Sent Events (SSE)

**说明**: 调用完整的CrewAI流程，4个Agent协作（智能选股师 → 多维分析师 → 风险管理官 → 投资决策官）

---

## 11. 市场数据API

⚠️ **状态**: 已实现但未启用（前端未调用）

### 11.1 获取板块涨跌数据

**端点**: `GET /sectors`

**描述**: 获取板块涨跌数据

**请求参数**:
- `limit` (可选): 返回板块数量，默认50个

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "sector_code": "BK0001",
      "sector_name": "电子信息",
      "change_pct": 2.5,
      "volume": 123.45,
      "leading_stock_code": "600000",
      "leading_stock_name": "浦发银行",
      "leading_stock_change": 3.2
    }
  ]
}
```

### 11.2 获取市场热点数据

**端点**: `GET /hotspots`

**描述**: 获取市场热点数据

**请求参数**:
- `limit` (可选): 返回热点数量，默认20个

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "hotspot_name": "人工智能",
      "change_pct": 3.5,
      "volume": 234.56,
      "stock_count": 50,
      "leading_stocks": [
        {
          "code": "600000",
          "name": "浦发银行",
          "change_pct": 4.2
        }
      ]
    }
  ]
}
```

### 11.3 获取市场实时数据（旧版，已废弃）

**端点**: `GET /api/market/data`

**描述**: 获取市场实时数据（此端点已废弃，请使用market_api的/api/market/sentiment）

**请求参数**: 无

**响应示例**:
```json
{
  "success": true,
  "data": {
    "sh_index": {
      "current": 3200.50,
      "change": 1.5,
      "change_pct": 0.47
    },
    "sz_index": {
      "current": 11000.20,
      "change": 50.3,
      "change_pct": 0.46
    },
    "limit_up_count": 120,
    "limit_down_count": 5
  }
}
```

---

## 🔐 认证说明

### Cookie认证

所有API请求都需要携带Cookie中的`user_session_id`，系统会自动处理：

1. 首次访问时，跳转到登录页面输入用户名
2. 登录后，Cookie持久化30天
3. 每个用户的数据完全隔离

### 多用户支持

- ✅ 每个用户有独立的session_id
- ✅ 数据库查询自动过滤session_id
- ✅ 支持多用户并发访问

---

## 📝 错误处理

### 标准错误响应

```json
{
  "success": false,
  "error": "错误信息",
  "code": "ERROR_CODE"
}
```

### 常见错误码

| 错误码 | 说明 | HTTP状态码 |
|--------|------|-----------|
| `INVALID_PARAMS` | 参数错误 | 400 |
| `NOT_FOUND` | 资源不存在 | 404 |
| `SERVER_ERROR` | 服务器错误 | 500 |
| `UNAUTHORIZED` | 未授权 | 401 |

---

## 🧪 测试示例

### 使用curl测试

```bash
# 获取持仓监控数据
curl -X GET http://localhost:7000/api/positions/monitor \
  -H "Cookie: user_session_id=your_session_id"

# 买入股票
curl -X POST http://localhost:7000/api/positions/buy \
  -H "Content-Type: application/json" \
  -H "Cookie: user_session_id=your_session_id" \
  -d '{
    "stock_code": "600000",
    "stock_name": "浦发银行",
    "buy_price": 10.50,
    "quantity": 1000,
    "strategy": "龙头战法"
  }'

# 获取最新推荐
curl -X GET http://localhost:7000/api/recommendations/latest \
  -H "Cookie: user_session_id=your_session_id"
```

### 使用JavaScript测试

```javascript
// 获取持仓监控数据
fetch('/api/positions/monitor')
  .then(response => response.json())
  .then(data => console.log(data));

// 买入股票
fetch('/api/positions/buy', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    stock_code: '600000',
    stock_name: '浦发银行',
    buy_price: 10.50,
    quantity: 1000,
    strategy: '龙头战法'
  })
})
  .then(response => response.json())
  .then(data => console.log(data));
```

---

## 📚 相关文档

- [README.md](../README.md) - 项目概述
- [ARCHITECTURE.md](../ARCHITECTURE.md) - 系统架构
- [DEVELOPMENT.md](../DEVELOPMENT.md) - 开发指南

---

**维护者**: AI Architect
**最后更新**: 2025-11-10
**版本**: v2.0


