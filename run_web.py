#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock Web管理界面启动脚本

简化启动命令，提供更好的开发体验

作者: AI Architect
版本: v1.0.0-web-interface
日期: 2025-10-31
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_env_file():
    """创建.env文件模板"""
    env_file = project_root / '.env'
    if not env_file.exists():
        print("📝 创建.env配置文件...")
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("""# CrewAI Stock 环境配置

# 数据库配置
DATABASE_PATH=data/stock_trading.db

# 智兔API配置
ZHITU_API_TOKEN=your_zhitu_token_here
ZHITU_API_BASE_URL=https://api.zhituapi.cn

# Tavily API配置
TAVILY_API_KEY=your_tavily_key_here

# PushPlus推送配置
PUSHPLUS_TOKEN=your_pushplus_token_here
PUSHPLUS_TOPIC=your_group_topic_here

# Web服务配置
FLASK_SECRET_KEY=your-secret-key-here
WEB_PORT=7000
FLASK_DEBUG=False

# 日志配置
LOG_LEVEL=INFO
""")
        print("✅ .env文件已创建，请配置相应的API密钥")
        return True
    return False

def create_directories():
    """创建必要的目录"""
    directories = [
        'data',
        'logs',
        'data/backups'
    ]

    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 目录: {directory} ✓")

def check_dependencies():
    """检查依赖是否安装"""
    print("🔍 检查Python依赖...")

    required_packages = {
        'flask': 'Flask',
        'sqlalchemy': 'sqlalchemy',
        'requests': 'requests',
        'pandas': 'pandas',
        'loguru': 'loguru',
        'dotenv': 'python-dotenv'  # python-dotenv导入为dotenv
    }

    missing_packages = []

    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"  ✅ {package_name}")
        except ImportError:
            missing_packages.append(package_name)
            print(f"  ❌ {package_name}")

    if missing_packages:
        print(f"\n⚠️  缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False

    print("✅ 所有依赖已安装")
    return True

def check_database():
    """检查数据库状态"""
    print("🗄️  检查数据库...")

    try:
        from src.database.init_db import init_database
        init_database()
        print("✅ 数据库初始化完成")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False

def start_web_server(host='0.0.0.0', port=7000, debug=False):
    """启动Web服务器"""
    print(f"🚀 启动Web服务器...")
    print(f"   地址: http://{host}:{port}")
    print(f"   调试模式: {debug}")
    print("   按 Ctrl+C 停止服务器\n")

    # 设置环境变量
    os.environ['WEB_PORT'] = str(port)
    os.environ['FLASK_DEBUG'] = str(debug).lower()

    try:
        from app import app
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n👋 Web服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description='CrewAI Stock Web管理界面')
    parser.add_argument('--host', default='0.0.0.0', help='服务器地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=7000, help='服务器���口 (默认: 7000)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--init-only', action='store_true', help='仅初始化环境，不启动服务器')

    args = parser.parse_args()

    print("=" * 60)
    print("🎯 CrewAI Stock Web管理界面")
    print("=" * 60)

    # 创建目录
    create_directories()

    # 创建.env文件
    env_created = create_env_file()

    # 检查依赖
    if not check_dependencies():
        if not env_created:
            print("\n💡 提示: 请先安装依赖包")
            print("   pip install -r requirements.txt")
        return 1

    # 检查数据库
    if not check_database():
        print("\n💡 提示: 数据库初始化失败，请检查配置")
        return 1

    if args.init_only:
        print("\n✅ 环境初始化完成")
        return 0

    # 启动Web服务器
    if not start_web_server(args.host, args.port, args.debug):
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())