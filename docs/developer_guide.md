# 开发者指南 (Developer Guide)

本指南旨在帮助开发者理解 CrewAI A-Stock 的代码结构，并指导如何进行二次开发。

## 📂 项目目录结构

```text
crewai-astock/
├── docs/                   # 文档
├── src/
│   ├── agents/            # AI Agent 定义
│   │   ├── smart_agents.py   # Agent 工厂函数
│   │   └── tools/        # Agent 可用的工具集
│   ├── crews/             # Crew 编排逻辑
│   │   ├── smart_recommendation_crew.py
│   │   ├── position_monitor_crew.py
│   │   └── stock_evaluation_crew.py
│   ├── tools/             # 核心数据工具类
│   │   ├── data_source_manager.py  # 数据源统一入口
│   │   ├── zhitu_api.py      # 智兔接口
│   │   └── eastmoney_crawler.py # 东财爬虫
│   ├── database/          # 数据库模型与管理
│   ├── api/               # Flask API 蓝图
│   ├── core/              # 核心组件 (Scheduler, UserContainer)
│   └── config/            # 配置文件
├── app.py                 # Web 应用入口
├── scheduler.py           # 独立调度器入口
└── requirements.txt       # 项目依赖
```

## 🛠️ 如何添加新的 Tool

Tool 是 Agent 与外部世界交互的桥梁。假设我们要添加一个"查询公司高管信息"的工具。

1. **定义工具函数**
   在 `src/agents/tools/fundamental_tools.py` (如果不存在则创建) 中添加：

   ```python
   from langchain.tools import tool

   @tool("get_executive_info")
   def get_executive_info(stock_code: str):
       """
       查询指定股票的公司高管信息。
       Args:
           stock_code: 股票代码，如 600000
       """
       # 实现查询逻辑，例如调用 DataSourceManager
       from src.tools.data_source_manager import get_stock_info
       # ...
       return "CEO: 张三, CFO: 李四..."
   ```

2. **导出工具**
   在 `src/agents/tools/__init__.py` 中暴露新工具。

3. **绑定到 Agent**
   在 `src/agents/smart_agents.py` 中，将工具添加到对应 Agent 的 tools 列表中：

   ```python
   def create_multi_analyst():
       return Agent(
           role='多维分析师',
           tools=[..., get_executive_info],
           # ...
       )
   ```

## 🤖 如何修改 Agent 提示词

Agent 的表现高度依赖于 Prompt。

1. 打开 `src/agents/smart_agents.py`。
2. 找到目标 Agent 的 `goal` 和 `backstory` 参数。
3. **Goal** 定义了 Agent 要达成什么结果。
4. **Backstory** 设定了 Agent 的人设、性格和思维方式。

**提示**：对于中文环境，建议直接使用中文编写 Prompt，以减少翻译损耗。

## 🔄 如何定制 Crew 流程

Crew 流程定义了 Task 的执行顺序和数据传递。

以 `src/crews/smart_recommendation_crew.py` 为例：

1. **定义 Task**：
   ```python
   task_analysis = Task(
       description='...',
       agent=analyst_agent,
       context=[previous_task]  # 依赖上一个任务的输出
   )
   ```

2. **编排 Crew**：
   ```python
   crew = Crew(
       agents=[agent1, agent2],
       tasks=[task1, task2],
       process=Process.sequential  # 顺序执行或层级执行
   )
   ```

## 💾 数据库迁移

本项目使用 SQLAlchemy ORM。

1. 在 `src/database/models.py` 中定义新的模型类。
2. 系统启动时 (`src/database/db_manager.py`) 会自动调用 `Base.metadata.create_all` 创建新表。
3. **注意**：目前的自动创建仅支持新增表。如果修改现有表结构（如增加字段），建议使用手动 SQL 或集成 Alembic 进行迁移。

## 🧪 调试与日志

- 系统使用 `loguru` 进行日志管理。
- 日志文件默认保存在 `logs/` 目录下，按天轮转。
- 在开发过程中，可以通过设置 `verbose=True` 来让 CrewAI 打印详细的 Agent 思考过程（CoT）。

```python
crew = Crew(
    # ...
    verbose=True
)
```
