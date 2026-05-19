# 开发指南

##  开发环境搭建

### 系统要求

- **操作系统**：Windows 10/11, macOS 10.15+, Linux (Ubuntu 20.04+)
- **Python**：3.10 或更高版本
- **数据库**：SQLite 3（Python 自带）
- **内存**：建议 8GB 以上
- **磁盘空间**：至少 2GB

### 安装步骤

#### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/crewai-astock.git
cd crewai-astock
```

#### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 配置环境变量

创建 `.env` 文件：

```bash
# 必需配置
ZHITU_API_TOKEN=your_zhitu_api_token
DEEPSEEK_API_KEY=your_deepseek_api_key

# 可选配置
PUSHPLUS_TOKEN=your_pushplus_token
TAVILY_API_KEY=your_tavily_api_key
DATABASE_PATH=data/stock_trading.db
```

**环境变量说明**：

| 变量名 | 必需 | 说明 | 获取方式 |
|--------|------|------|----------|
| ZHITU_API_TOKEN |  | 智兔 API 令牌 | https://api.zhituapi.cn |
| DEEPSEEK_API_KEY |  | DeepSeek API 密钥 | https://platform.deepseek.com |
| PUSHPLUS_TOKEN |  | PushPlus 推送令牌 | http://www.pushplus.plus |
| TAVILY_API_KEY |  | Tavily 新闻 API 密钥 | https://tavily.com |
| DATABASE_PATH |  | 数据库路径 | 默认 `data/stock_trading.db` |

#### 5. 初始化数据库

```bash
# 创建所有数据表
python -m src.database.init_db

# 检查表结构
python -m src.database.init_db --check
```

#### 6. 初始化股票基础信息（可选）

```bash
# 下载并导入 5161 只股票的基础信息
python scripts/init_stock_basic_info.py
```

### 启动开发服务器

```bash
# 方式 1：直接运行 Flask 应用
python app.py

# 方式 2：使用 Flask 开发模式
export FLASK_ENV=development  # Windows: set FLASK_ENV=development
flask run

# 方式 3：使用 run_web.py
python run_web.py
```

访问 `http://localhost:5000` 即可使用系统。

##  项目结构

```
crewai-astock/
 app.py                      # Flask 应用主文件
 scheduler.py                # 主调度器
 main.py                     # CrewAI 入口（命令行模式）
 run_web.py                  # Web 应用启动脚本
 requirements.txt            # Python 依赖
 .env                        # 环境变量配置
 data/                       # 数据目录
    stock_trading.db        # SQLite 数据库
 logs/                       # 日志目录
    crewai_stock.log        # 系统日志
    web_app.log             # Web 应用日志
 templates/                  # Jinja2 模板
    base.html               # 基础模板
    trading.html            # 交易系统主页
    tools.html              # AI 工具中心
    login.html              # 登录页面
 scripts/                    # 脚本目录
    init_stock_basic_info.py # 初始化股票基础信息
 docs/                       # 文档目录
    API文档.md              # API 接口文档
    代码全面审查报告_2025-11-10.md
 src/                        # 源代码目录
    agents/                 # Agent 定义
       smart_agents.py     # 7 个 Agent 定义
       tasks.py            # Task 定义
       tools/              # Agent 工具
           database_tools.py
           market_tools.py
           news_tools.py
           notification_tools.py
    api/                    # API 接口
       position_api.py     # 持仓管理 API
       recommendation_api.py # 推荐 API
       strategy_api.py     # 策略 API
       market_api.py       # 市场 API
       account_api.py      # 账户 API
       market_insights_api.py # 市场洞察 API
       performance_api.py  # 绩效 API
       kline_api.py        # K 线 API
       crew_stream_api.py  # CrewAI 流式 API
       stock_evaluation_api.py # 股票评估 API
       market_data_api.py  # 市场数据 API
    config/                 # 配置模块
       llm_config.py       # LLM 配置
    core/                   # 核心模块
       user_container.py   # 用户容器管理器
       news_monitor_scheduler.py # 新闻监控调度器
    crews/                  # Crew 配置
       smart_recommendation_crew.py # 智能推荐 Crew
       stock_evaluation_crew.py # 股票评估 Crew
       position_monitor_crew.py # 持仓监控 Crew
    database/               # 数据库模块
       models.py           # ORM 模型（14 张表）
       db_manager.py       # 数据库管理器
       init_db.py          # 初始化脚本
       connection.py       # 连接管理
       migrations/         # 数据库迁移脚本
    tools/                  # 数据源工具
       zhitu_api.py        # 智兔 API
       eastmoney_crawler.py # 东方财富爬虫
       tavily_api.py       # Tavily 新闻 API
       google_news_rss.py  # Google News RSS
       data_source_manager.py # 数据源管理器
       news_source_manager.py # 新闻源管理器
       news_summary_generator.py # 新闻摘要生成器
    utils/                  # 工具模块
        pushplus_notifier.py # PushPlus 推送
        db_cache.py         # 数据库缓存
 tests/                      # 测试目录
     test_limit_up_analyzer.py
     test_market_intelligence_tools.py
     test_user_container.py
```

##  开发工作流

### 1. 添加新 Agent

**步骤**：

1. 在 `src/agents/smart_agents.py` 中定义新 Agent：

```python
def create_new_agent():
    \"\"\"
    Agent 8: 新 Agent 名称
    
    职责: 描述职责
    \"\"\"
    from crewai import Agent
    from .tools.your_tools import tool1, tool2
    
    return Agent(
        role="新 Agent 角色",
        goal="新 Agent 目标",
        backstory="新 Agent 背景故事",
        tools=[tool1, tool2],
        verbose=True,
        allow_delegation=False,
        max_iter=10
    )
```

2. 在 `src/agents/tools/` 中创建新工具（如需要）

3. 在 Crew 中使用新 Agent

### 2. 添加新 API 端点

**步骤**：

1. 在 `src/api/` 中创建新蓝图文件（或在现有文件中添加）：

```python
from flask import Blueprint, jsonify, request

new_api = Blueprint('new_api', __name__)

@new_api.route('/api/new/endpoint', methods=['GET'])
def new_endpoint():
    \"\"\"新端点描述\"\"\"
    try:
        # 处理逻辑
        return jsonify({
            'success': True,
            'data': {}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

2. 在 `app.py` 中注册蓝图：

```python
from src.api.new_api import new_api
app.register_blueprint(new_api)
```

### 3. 添加新数据库表

**步骤**：

1. 在 `src/database/models.py` 中定义新模型：

```python
class NewTable(Base):
    __tablename__ = 'new_table'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True, default='default')
    # 其他字段
    created_at = Column(DateTime, default=datetime.now)
```

2. 更新 `src/database/init_db.py` 中的 `expected_tables` 列表

3. 运行初始化脚本：

```bash
python -m src.database.init_db
```

### 4. 添加新数据源

**步骤**：

1. 在 `src/tools/` 中创建新数据源文件：

```python
class NewDataSource:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('NEW_API_KEY')
    
    def get_data(self, params):
        # 实现数据获取逻辑
        pass

def create_new_data_source():
    return NewDataSource()
```

2. 在 `src/tools/data_source_manager.py` 中集成新数据源（可选）

##  测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_user_container.py

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 编写测试

**示例**：

```python
import pytest
from src.database.models import Candidate
from src.database.db_manager import DatabaseManager

def test_create_candidate():
    db = DatabaseManager()
    candidate = Candidate(
        stock_code='600000',
        stock_name='浦发银行',
        recommend_price=10.50,
        session_id='test_session'
    )
    db.add(candidate)
    
    # 验证
    result = db.query(Candidate).filter_by(stock_code='600000').first()
    assert result is not None
    assert result.stock_name == '浦发银行'
```

##  API 文档

详见 `docs/API文档.md`，包含所有 11 个 API 蓝图的完整文档。

### 核心 API 端点

#### 1. 持仓管理 API

**获取所有持仓**

```http
GET /api/positions/all?session_id=<session_id>
```

**响应**：

```json
{
  \"success\": true,
  \"data\": [
    {
      \"id\": 1,
      \"stock_code\": \"600000\",
      \"stock_name\": \"浦发银行\",
      \"buy_price\": 10.50,
      \"sell_price\": 11.20,
      \"quantity\": 1000,
      \"status\": \"sold\",
      \"profit\": 700.00
    }
  ]
}
```

**买入股票**

```http
POST /api/positions/buy
Content-Type: application/json

{
  \"session_id\": \"user123\",
  \"stock_code\": \"600000\",
  \"stock_name\": \"浦发银行\",
  \"buy_price\": 10.50,
  \"quantity\": 1000
}
```

**卖出股票**

```http
POST /api/positions/sell
Content-Type: application/json

{
  \"session_id\": \"user123\",
  \"position_id\": 1,
  \"sell_price\": 11.20,
  \"quantity\": 1000
}
```

#### 2. 推荐 API

**获取最近推荐**

```http
GET /api/recommendations/latest?session_id=<session_id>&days=3
```

**响应**：

```json
{
  \"success\": true,
  \"data\": [
    {
      \"stock_code\": \"600000\",
      \"stock_name\": \"浦发银行\",
      \"recommend_price\": 10.50,
      \"track\": \"track1_tail\",
      \"reason\": \"技术面强势，资金流入\",
      \"created_at\": \"2025-11-10 09:30:00\"
    }
  ]
}
```

#### 3. CrewAI 流式 API

**启动 AI 推荐（SSE 流式）**

```http
GET /api/crew/stream?session_id=<session_id>
```

**响应**（Server-Sent Events）：

```
data: {\"type\": \"agent_start\", \"agent\": \"复盘分析师\", \"message\": \"开始分析昨日推荐表现...\"}

data: {\"type\": \"agent_output\", \"agent\": \"复盘分析师\", \"output\": \"昨日推荐 3 只股票，2 只上涨...\"}

data: {\"type\": \"agent_complete\", \"agent\": \"复盘分析师\"}

data: {\"type\": \"crew_complete\", \"result\": \"推荐完成\"}
```

##  部署

### 生产环境部署

#### 1. 使用 Gunicorn（推荐）

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动应用（4 个 worker）
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

#### 2. 使用 Docker

创建 `Dockerfile`：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD [\"gunicorn\", \"-w\", \"4\", \"-b\", \"0.0.0.0:5000\", \"app:app\"]
```

构建并运行：

```bash
docker build -t crewai-astock .
docker run -p 5000:5000 --env-file .env crewai-astock
```

#### 3. 使用 Nginx 反向代理

Nginx 配置：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \System.Management.Automation.Internal.Host.InternalHost;
        proxy_set_header X-Real-IP \;
        proxy_set_header X-Forwarded-For \;
    }
}
```

### 环境变量配置

生产环境建议使用环境变量而非 `.env` 文件：

```bash
export ZHITU_API_TOKEN=your_token
export DEEPSEEK_API_KEY=your_key
export PUSHPLUS_TOKEN=your_token
export DATABASE_PATH=/var/lib/crewai_stock/stock_trading.db
```

### 数据库备份

```bash
# 备份数据库
cp data/stock_trading.db data/backups/stock_trading_.db

# 定时备份（crontab）
0 2 * * * cp /path/to/data/stock_trading.db /path/to/backups/stock_trading_.db
```

##  调试技巧

### 1. 查看日志

```bash
# 系统日志
tail -f logs/crewai_stock.log

# Web 应用日志
tail -f logs/web_app.log
```

### 2. 数据库调试

```bash
# 进入 SQLite 命令行
sqlite3 data/stock_trading.db

# 查看所有表
.tables

# 查看表结构
.schema candidates

# 查询数据
SELECT * FROM candidates WHERE session_id='default' LIMIT 10;
```

### 3. API 调试

使用 `curl` 测试 API：

```bash
# 获取持仓
curl -X GET \"http://localhost:5000/api/positions/all?session_id=default\"

# 买入股票
curl -X POST \"http://localhost:5000/api/positions/buy\" \
  -H \"Content-Type: application/json\" \
  -d '{\"session_id\":\"default\",\"stock_code\":\"600000\",\"stock_name\":\"浦发银行\",\"buy_price\":10.50,\"quantity\":1000}'
```

### 4. CrewAI 调试

启用详细日志：

```python
# 在 smart_agents.py 中设置
agent = Agent(
    role=\"...\",
    goal=\"...\",
    backstory=\"...\",
    verbose=True,  # 启用详细日志
    allow_delegation=False
)
```

##  编码规范

### Python 规范

- 遵循 **PEP 8** 编码规范
- 使用 **type hints** 类型注解
- 函数文档字符串使用 **Google 风格**
- 类和函数命名采用 **snake_case**

**示例**：

```python
def get_stock_info(stock_code: str, session_id: str = 'default') -> Dict[str, Any]:
    \"\"\"
    获取股票信息
    
    Args:
        stock_code: 股票代码，如 '600000'
        session_id: 会话 ID，默认 'default'
    
    Returns:
        股票信息字典
    
    Raises:
        ValueError: 股票代码无效时抛出
    \"\"\"
    pass
```

### Git 提交规范

```
feat: 新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式调整
refactor: 重构
test: 测试相关
chore: 构建/工具相关
```

**示例**：

```bash
git commit -m \"feat: 添加持仓监控 Agent\"
git commit -m \"fix: 修复 K 线数据缓存问题\"
git commit -m \"docs: 更新 API 文档\"
```

##  相关链接

- **智兔 API 文档**：https://api.zhituapi.cn
- **CrewAI 官方文档**：https://docs.crewai.com/
- **PushPlus 推送服务**：http://www.pushplus.plus
- **DeepSeek API**：https://platform.deepseek.com
- **Tavily API**：https://tavily.com

---

**最后更新**：2025-11-10  
**版本**：v2.0.0
