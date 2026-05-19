[根目录](../../CLAUDE.md) > [src](../) > **config**

# Config 模块 - 配置管理层

## 📋 模块职责

管理系统配置，特别是 LLM（Large Language Model）配置，为 CrewAI 智能体提供不同类型的 LLM 实例。

## 🔧 核心配置

### LLM 配置 (`llm_config.py`)

提供三种类型的 LLM 配置：

```python
# 1. 决策型 LLM (Decision LLM)
- 用途：投资决策、风险评估、最终决策
- 模型：deepseek-chat
- 温度：0.7（平衡推理和创造性）
- max_tokens：8000（长文本输出）

# 2. 分析型 LLM (Analysis LLM)
- 用途：数据分析、技术指标计算、绩效分析
- 模型：deepseek-chat
- 温度：0.3（更注重准确性）
- max_tokens：4000（中等文本输出）

# 3. 创意型 LLM (Creative LLM)
- 用途：策略生成、市场洞察、热点发现
- 模型：deepseek-chat
- 温度：1.0（高创造性）
- max_tokens：8000（长文本输出）
```

## 🚀 使用方法

```python
from src.config.llm_config import get_decision_llm, get_analysis_llm, get_creative_llm

# 获取决策型LLM
decision_llm = get_decision_llm()

# 获取分析型LLM
analysis_llm = get_analysis_llm()

# 获取创意型LLM
creative_llm = get_creative_llm()

# 在Agent中使用
from crewai import Agent

agent = Agent(
    role='投资决策官',
    goal='做出最终投资决策',
    llm=decision_llm  # 使用决策型LLM
)
```

## 🔗 环境变量

```bash
# DeepSeek API (必需)
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com/v1

# OpenAI兼容配置（DeepSeek使用OpenAI SDK）
OPENAI_API_KEY=${DEEPSEEK_API_KEY}
OPENAI_API_BASE=${DEEPSEEK_API_BASE}
```

## 📁 相关文件

- `src/config/llm_config.py` - LLM配置定义

---

**维护者**: AI Architect
**模块状态**: ✅ LLM配置完整实现
**最后更新**: 2025-11-22 14:32:44
**依赖模块**: 无
