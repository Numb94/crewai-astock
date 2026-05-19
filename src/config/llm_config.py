#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - LLM配置模块

作者: AI Architect
日期: 2025-11-01
描述: 配置DeepSeek LLM,供CrewAI Agent使用
"""

import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# HACK: CrewAI 需要 OPENAI_API_KEY 和 OPENAI_API_BASE 环境变量
# 我们将 DEEPSEEK 的配置映射到 OPENAI 的环境变量
deepseek_key = os.getenv("DEEPSEEK_API_KEY")
deepseek_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if deepseek_key and deepseek_key != "sk-your_deepseek_api_key_here":
    os.environ["OPENAI_API_KEY"] = deepseek_key
    os.environ["OPENAI_API_BASE"] = deepseek_base
    os.environ["OPENAI_BASE_URL"] = deepseek_base


def get_deepseek_llm(temperature: float = 0.1, model: str = None, for_crewai: bool = True):
    """
    获取DeepSeek LLM实例

    Args:
        temperature: 温度参数,控制随机性 (0-1)
                    0.1 = 更确定性的输出(推荐用于决策)
                    0.7 = 更有创造性的输出
        model: 模型名称,默认从环境变量读取
        for_crewai: 是否用于CrewAI（需要openai/前缀）

    Returns:
        ChatOpenAI: 配置好的DeepSeek LLM实例
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or api_key == "sk-your_deepseek_api_key_here":
        raise ValueError(
            "请在.env文件中配置DEEPSEEK_API_KEY! "
            "获取方式: https://platform.deepseek.com/api_keys"
        )

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model_name = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # CrewAI 需要 openai/ 前缀（告诉 litellm 使用 OpenAI 兼容接口）
    # 直接调用 LangChain 不需要前缀
    if for_crewai and not model_name.startswith("openai/"):
        model_name = f"openai/{model_name}"
    elif not for_crewai and model_name.startswith("openai/"):
        model_name = model_name.replace("openai/", "")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=2000,
        timeout=60,
    )


# 预定义不同场景的LLM（用于CrewAI Agent）
def get_analysis_llm():
    """分析型LLM - 用于技术分析、资金分析等（CrewAI）"""
    return get_deepseek_llm(temperature=0.1, for_crewai=True)


def get_decision_llm():
    """决策型LLM - 用于CEO、CSO等决策Agent（CrewAI）"""
    return get_deepseek_llm(temperature=0.05, for_crewai=True)


def get_creative_llm():
    """创造型LLM - 用于市场分析、策略研究等（CrewAI）"""
    return get_deepseek_llm(temperature=0.3, for_crewai=True)


# 直接调用LLM（非CrewAI场景）
def get_direct_llm(temperature: float = 0.1):
    """直接调用LLM - 用于工具函数内部调用（非CrewAI）"""
    return get_deepseek_llm(temperature=temperature, for_crewai=False)


if __name__ == "__main__":
    # 测试LLM配置
    import sys
    import io

    # 设置stdout为utf-8编码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("正在测试DeepSeek LLM配置...")

    try:
        llm = get_deepseek_llm()
        print("✓ LLM配置成功!")
        print(f"  模型: {llm.model_name}")
        print(f"  Base URL: {llm.openai_api_base}")

        # 简单测试
        print("\n正在测试LLM调用...")
        response = llm.invoke("你好,请用一句话介绍你自己")
        print("✓ LLM调用成功!")
        print(f"  响应: {response.content}")

    except Exception as e:
        print(f"× LLM配置失败: {e}")
