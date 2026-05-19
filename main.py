#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - 主程序入口

手动触发式智能股票推荐系统
"""

# ❌ 必须在所有import之前设置环境变量和警告过滤器
import os
os.environ['PYTHONWARNINGS'] = 'ignore::UserWarning'  # 环境变量方式隐藏警告

import warnings
warnings.simplefilter('ignore', UserWarning)  # 使用simplefilter而不是filterwarnings

import sys
import io
import json
import argparse
from datetime import datetime
from pathlib import Path

# 设置stdout为utf-8编码(解决Windows中文显示问题)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.crews.smart_recommendation_crew import create_smart_recommendation_crew
from src.utils.pushplus_notifier import PushPlusNotifier
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/crewai_stock.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 🔴 降低第三方库和工具模块的日志级别（减少技术细节日志）
logging.getLogger('werkzeug').setLevel(logging.WARNING)  # HTTP请求日志
logging.getLogger('httpx').setLevel(logging.WARNING)  # HTTP客户端日志
logging.getLogger('httpcore').setLevel(logging.WARNING)  # HTTP核心日志
logging.getLogger('src.tools.data_source_manager').setLevel(logging.WARNING)  # 数据源管理器
logging.getLogger('src.tools.zhitu_api').setLevel(logging.WARNING)  # 智兔API
logging.getLogger('src.tools.eastmoney_crawler').setLevel(logging.WARNING)  # 东方财富爬虫
logging.getLogger('src.tools.mcp_client').setLevel(logging.WARNING)  # MCP客户端
logging.getLogger('src.tools.news_source_manager').setLevel(logging.WARNING)  # 新闻源管理器
logging.getLogger('src.agents.tools.context_tools').setLevel(logging.WARNING)  # 上下文工具
logging.getLogger('src.agents.tools.database_tools').setLevel(logging.WARNING)  # 数据库工具

# ✅ 保留LiteLLM的INFO日志（显示LLM调用和回复）
logging.getLogger('LiteLLM').setLevel(logging.INFO)


def print_banner():
    """打印系统横幅"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║       CrewAI Stock - 智能股票推荐系统 V2.0                     ║
║                                                               ║
║       基于CrewAI + DeepSeek的智能决策系统                      ║
║       手动触发 | 6个Agent | 6个Task | 并行优化                 ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def format_result(result_text: str) -> dict:
    """
    格式化Crew执行结果

    Args:
        result_text: Crew返回的文本结果

    Returns:
        dict: 解析后的推荐数据
    """
    try:
        # 尝试从文本中提取JSON
        # CEO应该返回JSON格式,但可能包含其他文本
        import re

        # 查找JSON部分
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        else:
            # 如果没有找到JSON,返回原始文本
            logger.warning("未找到JSON格式结果,返回原始文本")
            return {'raw_result': result_text}

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        return {'raw_result': result_text}


def print_recommendations(recommendations: dict):
    """
    打印推荐结果

    Args:
        recommendations: 推荐数据字典
    """
    print("\n" + "=" * 80)
    print("【最终推荐结果】")
    print("=" * 80)

    if 'raw_result' in recommendations:
        print(recommendations['raw_result'])
        return

    # 打印策略和市场状态
    print(f"\n市场状态: {recommendations.get('market_state', 'N/A').upper()}")
    print(f"推荐策略: {recommendations.get('strategy', 'N/A')}")

    # 打印推荐股票
    stocks = recommendations.get('stocks', [])
    if stocks:
        print(f"\n推荐股票数量: {len(stocks)}只\n")

        for i, stock in enumerate(stocks, 1):
            print(f"{i}. {stock['name']}({stock['code']})")
            print(f"   综合评分: {stock.get('final_score', 0):.1f}")
            print(f"   技术评分: {stock.get('tech_score', 0):.1f} | "
                  f"资金评分: {stock.get('fund_score', 0):.1f} | "
                  f"基本面评分: {stock.get('fundamental_score', 0):.1f}")
            print(f"   决策: {stock.get('decision', 'N/A')}")
            print(f"   建议买入价: {stock.get('recommend_price', 0):.2f}元")
            print(f"   建议数量: {stock.get('quantity', 0)}股 "
                  f"(约{stock.get('amount', 0):.0f}元, 仓位{stock.get('position_pct', 0)*100:.0f}%)")
            print(f"   止损: {stock.get('stop_loss', 0):.2f}元 | "
                  f"止盈: {stock.get('target_price', 0):.2f}元")
            print(f"   风险等级: {stock.get('risk_level', 'N/A')}")
            print(f"   理由: {stock.get('reason', 'N/A')}")
            print()

    # 打印CEO总结
    ceo_summary = recommendations.get('ceo_summary', '')
    if ceo_summary:
        print("CEO总结:")
        print(ceo_summary)

    print("=" * 80)


def push_to_wechat(recommendations: dict):
    """
    推送推荐结果到微信

    Args:
        recommendations: 推荐数据
    """
    try:
        notifier = PushPlusNotifier()

        # 构建推送内容
        market_state = recommendations.get('market_state', 'neutral').upper()
        strategy = recommendations.get('strategy', '未知策略')

        title = f"【股票推荐】{market_state}市场 - {strategy}"

        content = f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}**\n\n"
        content += f"市场状态: {market_state}\n"
        content += f"推荐策略: {strategy}\n\n"

        stocks = recommendations.get('stocks', [])
        if stocks:
            for i, stock in enumerate(stocks, 1):
                content += f"**{i}. {stock['name']}({stock['code']})**\n"
                content += f"- 决策: {stock.get('decision', 'N/A')} (评分:{stock.get('final_score', 0):.1f})\n"
                content += f"- 买入价: {stock.get('recommend_price', 0):.2f}元\n"
                content += f"- 数量: {stock.get('quantity', 0)}股 (仓位{stock.get('position_pct', 0)*100:.0f}%)\n"
                content += f"- 止损: {stock.get('stop_loss', 0):.2f} | 止盈: {stock.get('target_price', 0):.2f}\n"
                content += f"- 理由: {stock.get('reason', 'N/A')}\n\n"

        ceo_summary = recommendations.get('ceo_summary', '')
        if ceo_summary:
            content += f"**CEO总结:**\n{ceo_summary}\n"

        # 发送推送
        result = notifier.send(title, content, template='markdown')

        if result:
            print("✓ 已成功推送到微信!")
        else:
            print("× 推送失败,请检查PushPlus配置")

    except Exception as e:
        logger.error(f"推送失败: {e}")
        print(f"× 推送失败: {e}")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='CrewAI Stock - 智能股票推荐系统')
    parser.add_argument('--push', action='store_true', help='分析完成后推送到微信')
    parser.add_argument('--save', type=str, help='保存结果到文件')
    args = parser.parse_args()

    # 打印横幅
    print_banner()

    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        # 创建Crew
        logger.info("正在创建SmartRecommendationCrew...")
        crew = create_smart_recommendation_crew()

        # 执行分析
        logger.info("开始执行股票推荐分析...")
        print("\n🚀 启动6个智能Agent协作分析...\n")

        # ✅ 实时显示CrewAI过程，同时记录到日志
        import io
        import re

        # 🔴 Tee类：同时输出到终端和StringIO
        class Tee:
            def __init__(self, *files):
                self.files = files
            def write(self, data):
                for f in self.files:
                    f.write(data)
                    f.flush()
            def flush(self):
                for f in self.files:
                    f.flush()

        old_stdout = sys.stdout
        stdout_capture = io.StringIO()

        # 🔴 使用Tee同时输出到终端和StringIO（实时显示过程）
        sys.stdout = Tee(old_stdout, stdout_capture)

        try:
            result = crew.kickoff()

            # 获取CrewAI的输出
            crew_output = stdout_capture.getvalue()

            # 恢复stdout
            sys.stdout = old_stdout

            # 清理ANSI颜色代码和装饰性字符
            def clean_output(text):
                """清理CrewAI输出中的ANSI代码和装饰性字符"""
                # 清理ANSI颜色代码
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                text = ansi_escape.sub('', text)

                # 清理装饰性框线字符
                box_chars = ['│', '╭', '╰', '├', '└', '─', '╮', '╯', '┤', '┴', '┬', '┼']
                for char in box_chars:
                    text = text.replace(char, '')

                return text.strip()

            # 记录CrewAI输出到日志文件（清理后）
            if crew_output:
                logger.info("=== CrewAI执行输出 ===")
                for line in crew_output.split('\n'):
                    if line.strip():
                        clean_line = clean_output(line)
                        if clean_line:  # 只记录非空行
                            logger.info(clean_line)
                logger.info("=== CrewAI执行完成 ===")

            # 同时打印到终端（用户可见，保留美化格式）
            print(crew_output)

        except Exception as e:
            # 恢复stdout
            sys.stdout = old_stdout
            raise e

        # 格式化结果
        recommendations = format_result(str(result))

        # 打印结果
        print_recommendations(recommendations)

        # 保存结果到文件
        if args.save:
            output_file = args.save
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(recommendations, f, ensure_ascii=False, indent=2)
            print(f"\n✓ 结果已保存到: {output_file}")

        # 推送到微信
        if args.push:
            print("\n正在推送到微信...")
            push_to_wechat(recommendations)

        print("\n✓ 分析完成!")
        return 0

    except KeyboardInterrupt:
        print("\n\n× 用户中断执行")
        return 1

    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        print(f"\n× 执行失败: {e}")
        print("\n请检查:")
        print("1. .env文件中的API密钥是否正确配置")
        print("2. 数据库是否已初始化")
        print("3. 网络连接是否正常")
        return 1


if __name__ == "__main__":
    sys.exit(main())
