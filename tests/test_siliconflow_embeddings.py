#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试硅基流动Embeddings集成

运行方式:
    python tests/test_siliconflow_embeddings.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_embedder_config():
    """测试Embedder配置"""
    print("\n" + "=" * 50)
    print("📋 测试1: Embedder配置")
    print("=" * 50)
    
    from src.config.embeddings_config import get_siliconflow_embedder_config
    
    config = get_siliconflow_embedder_config()
    
    if config is None:
        print("❌ 未配置SILICONFLOW_API_KEY，请在.env中添加")
        print("   获取方式: https://cloud.siliconflow.cn/account/ak")
        return False
    
    print(f"✅ Embedder配置成功:")
    print(f"   Provider: {config['provider']}")
    print(f"   Model: {config['config']['model']}")
    print(f"   API Base: {config['config']['api_base']}")
    return True


def test_embedding_generation():
    """测试向量生成"""
    print("\n" + "=" * 50)
    print("📋 测试2: 向量生成")
    print("=" * 50)
    
    from src.config.embeddings_config import SiliconFlowEmbedder
    
    try:
        embedder = SiliconFlowEmbedder()
    except ValueError as e:
        print(f"❌ Embedder初始化失败: {e}")
        return False
    
    # 测试单个文本
    test_text = "龙头战法在HOT市场下胜率最高，适合追涨停板"
    
    print(f"\n📝 测试文本: {test_text}")
    
    try:
        embedding = embedder.embed_query(test_text)
        print(f"✅ 向量生成成功!")
        print(f"   向量维度: {len(embedding)}")
        print(f"   向量前5个值: {embedding[:5]}")
        return True
    except Exception as e:
        print(f"❌ 向量生成失败: {e}")
        return False


def test_batch_embedding():
    """测试批量向量生成"""
    print("\n" + "=" * 50)
    print("📋 测试3: 批量向量生成")
    print("=" * 50)
    
    from src.config.embeddings_config import SiliconFlowEmbedder
    
    try:
        embedder = SiliconFlowEmbedder()
    except ValueError as e:
        print(f"❌ Embedder初始化失败: {e}")
        return False
    
    # 测试批量文本
    test_texts = [
        "龙头战法适合HOT市场，追涨停板龙头",
        "低吸策略适合COLD市场，超跌反弹",
        "放量突破策略适合WARM市场，成交量放大"
    ]
    
    print(f"\n📝 测试文本数量: {len(test_texts)}")
    
    try:
        embeddings = embedder.embed_documents(test_texts)
        print(f"✅ 批量向量生成成功!")
        print(f"   生成向量数量: {len(embeddings)}")
        print(f"   每个向量维度: {len(embeddings[0])}")
        return True
    except Exception as e:
        print(f"❌ 批量向量生成失败: {e}")
        return False


def test_crewai_memory_config():
    """测试CrewAI Memory配置"""
    print("\n" + "=" * 50)
    print("📋 测试4: CrewAI Memory配置")
    print("=" * 50)
    
    from src.config.embeddings_config import get_siliconflow_embedder_config
    
    config = get_siliconflow_embedder_config()
    
    if config is None:
        print("❌ 无法测试CrewAI Memory配置（未配置API Key）")
        return False
    
    # 验证配置格式符合CrewAI要求
    required_keys = ["provider", "config"]
    config_keys = ["api_key", "model", "api_base"]
    
    for key in required_keys:
        if key not in config:
            print(f"❌ 缺少必需字段: {key}")
            return False
    
    for key in config_keys:
        if key not in config["config"]:
            print(f"❌ 缺少config子字段: {key}")
            return False
    
    print("✅ CrewAI Memory配置格式正确!")
    print("   可以在Crew中使用: memory=True, embedder=config")
    return True


if __name__ == "__main__":
    print("\n" + "🚀" * 20)
    print("   硅基流动 Embeddings 集成测试")
    print("🚀" * 20)
    
    results = []
    
    results.append(("配置测试", test_embedder_config()))
    results.append(("向量生成", test_embedding_generation()))
    results.append(("批量向量", test_batch_embedding()))
    results.append(("CrewAI配置", test_crewai_memory_config()))
    
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {name}: {status}")
    
    print(f"\n   总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！Memory功能已就绪。")
    else:
        print("\n⚠️ 部分测试失败，请检查配置。")

