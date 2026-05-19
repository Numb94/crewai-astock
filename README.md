# CrewAI A-Stock

> 基于 CrewAI 多智能体协作的 A 股智能分析与推荐系统（学习研究用）

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CrewAI](https://img.shields.io/badge/CrewAI-0.95.0+-green.svg)](https://docs.crewai.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## ⚠️ 免责声明

**本项目仅供个人学习、技术研究和 AI 多智能体协作模式探索使用，不构成任何投资建议。**

- ❗ AI 推荐结果不保证准确性，过往业绩不代表未来表现
- ❗ 股票投资有风险，使用本项目产生的任何投资盈亏由使用者本人承担
- ❗ 项目不包含实盘交易接口，**请勿用于真实资金的自动化交易**
- ❗ 中国境内向不特定对象提供投资咨询需要相应资质，本项目不具备此资质

## 功能概览

### 多智能体协作推荐

7 个专业 Agent 协作完成股票推荐与持仓监控：

| Agent | 职责 |
|---|---|
| 复盘分析师 | 复盘历史推荐 + 策略胜率归因 |
| 市场情报官 | 市场环境识别 + 新闻热点 + 动态策略 |
| 智能选股师 | 动态筛选候选池 + 质量评估 |
| 多维分析师 | 技术 / 资金 / 基本面 / 新闻 / 逐笔 / 社区情绪 6 维分析 |
| 风险管理官 | 风险评估，一票否决 |
| 投资决策官 | 综合评分 + 仓位分配 + 推送 |
| 持仓监控师 | 实时监控持仓 + 智能卖点建议 |

### Crew 编排

- **智能推荐 Crew**：6 个 Agent 串行协作，输出推荐列表
- **股票评估 Crew**：针对指定股票做 4 维评估
- **持仓监控 Crew**：监控持仓 → 卖点分析 → 推送

### Web 管理界面（Flask + Vue3 + ECharts）

- 多用户支持（Cookie / session 隔离 30 天）
- 实时 K 线 + 推荐标记
- 流式 AI 推荐（SSE）
- 持仓 / 交易 / 绩效查询
- 微信推送（PushPlus，可选）

### CrewAI Memory 长期记忆

- 硅基流动 `BAAI/bge-m3` Embeddings
- 跨运行沉淀策略经验，越用越聪明
- 可选预热脚本导入历史样本

## 技术栈

| 类别 | 选型 |
|---|---|
| AI 框架 | CrewAI 0.95+ / LangChain 0.3+ |
| LLM | DeepSeek（推理）/ Grok（实时搜索） |
| Embeddings | 硅基流动 BAAI/bge-m3 |
| Web | Flask 3 + Vue3 + Element Plus + ECharts |
| 数据 | SQLite + SQLAlchemy ORM（15 张表）|
| 数据源 | **AKShare**（默认，免费开源） / 智兔 API（可选付费）+ 东方财富爬虫 + Tavily（备用新闻） |

## 快速开始

### 1. 环境

- Python 3.10+
- Windows / macOS / Linux

### 2. 安装

```bash
git clone https://github.com/<your-name>/crewai-astock.git
cd crewai-astock
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env：
#   DEEPSEEK_API_KEY     # 必需（AI 推理）
#   其他全是可选
```

**股票数据源说明**：

项目内置自动降级 —— **未配置 `ZHITU_API_TOKEN` 时自动使用 AKShare（免费开源）**，开箱即用，无需任何 Key。配置了 ZHITU Token 就自动切换到 ZHITU（数据更稳定）。

**API 申请入口**：

| API | 地址 | 状态 | 备注 |
|---|---|---|---|
| DeepSeek | https://platform.deepseek.com | ✅ **必需** | AI 推理引擎；注册送 500 万 tokens |
| AKShare | (无需 Key) | ✅ **默认数据源** | `pip install akshare`，开源免费 |
| 智兔 API | https://api.zhituapi.cn | 🟡 可选（付费） | 数据稳定性高于 AKShare（爬虫偶发抖动） |
| Grok / 中转 | https://x.ai 或国内中转 | 🟡 可选 | 新闻 + 社区情绪实时搜索；缺失则该维度走中性 60 分 |
| 硅基流动 | https://cloud.siliconflow.cn | 🟡 可选 | CrewAI Memory 长期记忆；不配则 Memory 关闭 |
| PushPlus | https://www.pushplus.plus | 🟡 可选 | 微信推送；不配则只在 Web 内显示 |
| Tavily | https://tavily.com | 🟡 可选 | 备用新闻源 |

> 💡 **最低运行成本**：只需 DeepSeek（注册送 500 万 tokens）即可跑完整推荐流程。其他全部可不配。

### 4. 初始化数据库

```bash
python -m src.database.init_db
# 可选：导入 5161 只 A 股基础信息
python scripts/init_stock_basic_info.py
# 可选：预热 Memory 历史经验
python scripts/warmup_memory.py
```

### 5. 启动 Web

```bash
python app.py
# 访问 http://localhost:5000
```

## 项目结构

```
crewai-astock/
├── app.py                          # Flask 主入口
├── scheduler.py                    # 定时任务（持仓监控 / 新闻监控 / 绩效更新）
├── global_news_scheduler.py        # 全局新闻调度
├── requirements.txt
├── src/
│   ├── agents/                     # 7 个 Agent 定义 + 48+ 工具
│   ├── crews/                      # 3 个 Crew 配置
│   ├── api/                        # Flask 蓝图
│   ├── core/                       # 用户容器 / 新闻监控
│   ├── tools/                      # 数据源适配（智兔 / 东财 / Grok / Tavily）
│   ├── database/                   # ORM 模型 + 数据库管理
│   ├── config/                     # LLM / Embeddings 配置
│   └── utils/                      # 工具库
├── templates/                      # Jinja2 模板（Vue3 嵌入）
├── docs/                           # 详细技术文档
├── scripts/                        # 初始化 / 维护脚本
└── tests/                          # 测试
```

详细架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 已移除的功能

本开源版本相对原工程移除了以下内容：

- 同花顺 / QMT 实盘交易接入（涉及券商协议与凭据管理）
- TrendRadar 新闻聚合服务（许可证兼容性原因，使用 Grok 替代）
- 自动买入 / 自动卖出闭环逻辑

如需研究上述功能，请参考各开源项目原仓库自行集成。

## 第三方依赖与协议

| 依赖 | 协议 |
|---|---|
| CrewAI / LangChain / Flask / SQLAlchemy | MIT / BSD |
| 智兔 API / DeepSeek / Grok / 硅基流动 / Tavily / PushPlus | 各自服务条款，使用前请阅读 |

## 社区讨论

🔗 Linux.do 开源推广帖：https://linux.do/t/topic/2206032

欢迎来贴讨论 / 反馈 / 吐槽。

## License

MIT License — 详见 [LICENSE](LICENSE)。

## 贡献

欢迎 Issue 和 Pull Request。**不接受涉及实盘交易、规避券商风控、绕过监管的内容。**
