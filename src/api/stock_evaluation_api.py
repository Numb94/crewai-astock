#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股票评估API

提供股票智能评估功能，调用完整的CrewAI流程
4个Agent协作：智能选股师 → 多维分析师 → 风险管理官 → 投资决策官
"""

from flask import Blueprint, request, jsonify, Response
from loguru import logger
import json

# 创建蓝图
stock_evaluation_api = Blueprint('stock_evaluation', __name__, url_prefix='/api/stock')


@stock_evaluation_api.route('/evaluate', methods=['GET'])
def evaluate_stock():
    """
    评估股票（SSE流式推送）

    Query Parameters:
        stock_codes: 股票代码（逗号分隔，如：600000,000001,002163）
        session_id: 用户session_id

    Returns:
        SSE流式推送CrewAI执行过程
    """
    try:
        # 获取请求参数
        stock_codes = request.args.get('stock_codes', '').strip()
        session_id = request.args.get('session_id', 'default')

        if not stock_codes:
            return jsonify({
                'success': False,
                'message': '请提供股票代码'
            }), 400

        # logger.info(f"开始评估股票: {stock_codes}, session_id={session_id[:8]}...")  # 🔴 注释掉INFO日志

        # 创建SSE生成器
        def generate():
            try:
                # 导入Crew
                from src.crews.stock_evaluation_crew import create_stock_evaluation_crew

                # 创建Crew
                crew = create_stock_evaluation_crew(
                    stock_codes=stock_codes,
                    session_id=session_id
                )

                # 发送开始消息
                yield f"data: {json.dumps({'type': 'start', 'message': f'开始评估股票: {stock_codes}'}, ensure_ascii=False)}\n\n"

                # 执行Crew（捕获输出）
                import sys
                from io import StringIO

                # 重定向stdout
                old_stdout = sys.stdout
                sys.stdout = StringIO()

                try:
                    # 执行Crew
                    result = crew.kickoff()

                    # 获取输出
                    output = sys.stdout.getvalue()

                    # 恢复stdout
                    sys.stdout = old_stdout

                    # 清理ANSI颜色代码和装饰性字符
                    import re

                    def clean_output(text):
                        """清理CrewAI输出中的ANSI代码和装饰性字符"""
                        # 清理ANSI颜色代码
                        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                        text = ansi_escape.sub('', text)

                        # 清理装饰性框线字符
                        box_chars = ['│', '╭', '╰', '├', '└', '─', '╮', '╯', '┤', '┴', '┬', '┼']
                        for char in box_chars:
                            text = text.replace(char, '')

                        # 清理多余的空行
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        return '\n'.join(lines)

                    # 发送输出（逐行，清理ANSI代码和装饰性字符）
                    for line in output.split('\n'):
                        if line.strip():
                            clean_line = clean_output(line)
                            if clean_line:
                                yield f"data: {json.dumps({'type': 'output', 'message': clean_line}, ensure_ascii=False)}\n\n"

                    # 发送结果（清理ANSI代码和装饰性字符）
                    clean_result = clean_output(str(result))
                    yield f"data: {json.dumps({'type': 'result', 'message': clean_result}, ensure_ascii=False)}\n\n"

                    # 发送完成消息
                    yield f"data: {json.dumps({'type': 'done', 'message': '评估完成'}, ensure_ascii=False)}\n\n"

                except Exception as e:
                    # 恢复stdout
                    sys.stdout = old_stdout

                    logger.error(f"Crew执行失败: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'评估失败: {str(e)}'}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"股票评估失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'评估失败: {str(e)}'}, ensure_ascii=False)}\n\n"

        # 返回SSE响应
        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"股票评估失败: {e}")
        return jsonify({
            'success': False,
            'message': f'评估失败: {str(e)}'
        }), 500

