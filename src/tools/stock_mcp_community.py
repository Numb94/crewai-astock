#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stock MCP 社区评论工具

提供雪球、东方财富股吧、淘股吧的社区评论获取功能
"""

import os
import asyncio
from typing import Dict, List, Optional
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class StockMCPCommunity:
    """Stock MCP 社区评论客户端"""
    
    def __init__(self, url: Optional[str] = None):
        """
        初始化MCP客户端
        
        Args:
            url: MCP服务器URL，默认从环境变量读取
        """
        self.url = url or os.getenv("STOCK_MCP_URL", "https://stock.doiiars.com/mcp")
        self.default_timeout = float(os.getenv("STOCK_MCP_CONNECT_TIMEOUT", "30"))
        self.default_format = os.getenv("STOCK_MCP_RESPONSE_FORMAT", "toon")
    
    async def get_xueqiu_comments(
        self, 
        symbol: str, 
        max_items: int = 20,
        timeout: Optional[float] = None
    ) -> str:
        """
        获取雪球评论
        
        Args:
            symbol: 股票代码（6位数字）
            max_items: 最大评论数，默认20条
            timeout: 超时时间（秒）
            
        Returns:
            TOON格式的评论数据
        """
        try:
            async with streamablehttp_client(self.url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool("get_xueqiu_comments", {
                        "symbol": symbol,
                        "max_items": max_items,
                        "timeout": timeout or self.default_timeout,
                        "response_format": self.default_format
                    })
                    
                    return result.content[0].text if result.content else ""
        except Exception as e:
            logger.error(f"获取雪球评论失败: {e}")
            return f"获取雪球评论失败: {str(e)}"
    
    async def get_eastmoney_comments(
        self, 
        symbol: str, 
        max_items: int = 20,
        timeout: Optional[float] = None
    ) -> str:
        """
        获取东方财富股吧评论
        
        Args:
            symbol: 股票代码（6位数字）
            max_items: 最大评论数，默认20条
            timeout: 超时时间（秒）
            
        Returns:
            TOON格式的评论数据
        """
        try:
            async with streamablehttp_client(self.url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool("get_eastmoney_guba_comments", {
                        "symbol": symbol,
                        "max_items": max_items,
                        "timeout": timeout or self.default_timeout,
                        "response_format": self.default_format
                    })
                    
                    return result.content[0].text if result.content else ""
        except Exception as e:
            logger.error(f"获取东财股吧评论失败: {e}")
            return f"获取东财股吧评论失败: {str(e)}"
    
    async def get_taoguba_comments(
        self, 
        symbol: str, 
        max_items: int = 20,
        timeout: Optional[float] = None
    ) -> str:
        """
        获取淘股吧评论
        
        Args:
            symbol: 股票代码（6位数字）
            max_items: 最大评论数，默认20条
            timeout: 超时时间（秒）
            
        Returns:
            TOON格式的评论数据
        """
        try:
            async with streamablehttp_client(self.url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool("get_tgb_comments", {
                        "symbol": symbol,
                        "max_items": max_items,
                        "timeout": timeout or self.default_timeout,
                        "response_format": self.default_format
                    })
                    
                    return result.content[0].text if result.content else ""
        except Exception as e:
            logger.error(f"获取淘股吧评论失败: {e}")
            return f"获取淘股吧评论失败: {str(e)}"
    
    async def get_all_platforms_comments(
        self,
        symbol: str,
        max_items: int = 40,
        timeout: Optional[float] = None
    ) -> str:
        """
        一次性获取所有平台评论（雪球+东财+淘股吧）

        Args:
            symbol: 股票代码（6位数字）
            max_items: 每个平台的最大评论数，默认40条
            timeout: 超时时间（秒）

        Returns:
            TOON格式的综合评论数据
        """
        try:
            async with streamablehttp_client(self.url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result = await session.call_tool("get_all_platforms_comments", {
                        "symbol": symbol,
                        "max_items": max_items,
                        "timeout": timeout or self.default_timeout,
                        "response_format": self.default_format
                    })

                    return result.content[0].text if result.content else ""
        except Exception as e:
            logger.error(f"获取所有平台评论失败: {e}")
            return f"获取所有平台评论失败: {str(e)}"


# 便捷函数
def get_community_client() -> StockMCPCommunity:
    """获取社区评论客户端实例"""
    return StockMCPCommunity()

