#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
市场数据API

提供板块涨跌、市场热点等市场数据
"""

from flask import Blueprint, request, jsonify
from loguru import logger

# 创建蓝图
market_data_api = Blueprint('market_data', __name__, url_prefix='/api/market')


@market_data_api.route('/sectors', methods=['GET'])
def get_sectors():
    """
    获取板块涨跌数据
    
    Query Parameters:
        limit: 返回板块数量，默认50个
    
    Returns:
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
                },
                ...
            ]
        }
    """
    try:
        # 获取请求参数
        limit = request.args.get('limit', 50, type=int)
        
        logger.info(f"获取板块涨跌数据，limit={limit}")
        
        # 调用东方财富爬虫
        from src.tools.eastmoney_crawler import EastMoneyCrawler
        
        crawler = EastMoneyCrawler()
        sectors = crawler.get_sector_performance(limit=limit)
        
        logger.info(f"成功获取{len(sectors)}个板块数据")
        
        return jsonify({
            'success': True,
            'data': sectors
        })
    
    except Exception as e:
        logger.error(f"获取板块数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取板块数据失败: {str(e)}'
        }), 500


@market_data_api.route('/hotspots', methods=['GET'])
def get_hotspots():
    """
    获取市场热点数据
    
    Query Parameters:
        limit: 返回热点数量，默认20个
    
    Returns:
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
                },
                ...
            ]
        }
    """
    try:
        # 获取请求参数
        limit = request.args.get('limit', 20, type=int)
        
        logger.info(f"获取市场热点数据，limit={limit}")
        
        # 调用东方财富爬虫
        from src.tools.eastmoney_crawler import EastMoneyCrawler
        
        crawler = EastMoneyCrawler()
        hotspots = crawler.get_market_hotspots(limit=limit)
        
        logger.info(f"成功获取{len(hotspots)}个热点数据")
        
        return jsonify({
            'success': True,
            'data': hotspots
        })
    
    except Exception as e:
        logger.error(f"获取热点数据失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取热点数据失败: {str(e)}'
        }), 500

