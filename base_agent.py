#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基礎 Agent 類別和訊息匯流排
實現 Multi-Agent 架構的核心通訊機制
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict
from datetime import datetime

from models import AgentMessage, MessageType


class MessageBus:
    """
    訊息匯流排 - 負責代理間的訊息傳遞
    實現發布/訂閱模式
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.logger = logging.getLogger("MessageBus")
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.agents: Dict[str, 'BaseAgent'] = {}
        self._running = False
        self._initialized = True
    
    def register_agent(self, agent: 'BaseAgent'):
        """註冊代理"""
        self.agents[agent.name] = agent
        self.logger.info(f"✅ 代理已註冊: {agent.name}")
    
    def subscribe(self, agent_name: str, callback: Callable):
        """訂閱特定代理的訊息"""
        self.subscribers[agent_name].append(callback)
    
    async def publish(self, message: AgentMessage):
        """發布訊息"""
        await self.message_queue.put(message)
        self.logger.debug(
            f"📨 訊息已發布: {message.sender} -> {message.receiver} "
            f"[{message.msg_type.value}]"
        )
    
    async def send_direct(self, message: AgentMessage):
        """直接發送訊息給特定代理"""
        if message.receiver in self.agents:
            agent = self.agents[message.receiver]
            await agent.receive_message(message)
            self.logger.info(
                f"📬 直接傳送: {message.sender} -> {message.receiver} "
                f"[{message.msg_type.value}]"
            )
        else:
            self.logger.warning(f"⚠️ 找不到目標代理: {message.receiver}")
    
    async def start(self):
        """啟動訊息處理迴圈"""
        self._running = True
        self.logger.info("🚀 訊息匯流排已啟動")
        
        while self._running:
            try:
                # 使用 timeout 避免無限等待
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                await self._process_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"❌ 訊息處理錯誤: {e}")
    
    async def _process_message(self, message: AgentMessage):
        """處理單一訊息"""
        # 發送給特定接收者
        if message.receiver in self.agents:
            agent = self.agents[message.receiver]
            await agent.receive_message(message)
        
        # 觸發訂閱者回調
        for callback in self.subscribers.get(message.receiver, []):
            try:
                await callback(message)
            except Exception as e:
                self.logger.error(f"回調執行錯誤: {e}")
    
    def stop(self):
        """停止訊息匯流排"""
        self._running = False
        self.logger.info("🛑 訊息匯流排已停止")


class BaseAgent(ABC):
    """
    基礎代理類別
    所有代理都繼承此類別
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self.message_bus = MessageBus()
        self.message_bus.register_agent(self)
        self._message_handlers: Dict[MessageType, Callable] = {}
        self._setup_handlers()
    
    def _setup_handlers(self):
        """設定訊息處理器 - 子類別可覆寫"""
        pass
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """註冊特定訊息類型的處理器"""
        self._message_handlers[msg_type] = handler
    
    async def receive_message(self, message: AgentMessage):
        """接收並處理訊息"""
        self.logger.info(
            f"📩 收到訊息: 來自 {message.sender} [{message.msg_type.value}]"
        )
        
        handler = self._message_handlers.get(message.msg_type)
        if handler:
            await handler(message)
        else:
            await self.handle_message(message)
    
    @abstractmethod
    async def handle_message(self, message: AgentMessage):
        """處理訊息 - 子類別必須實作"""
        pass
    
    async def send_message(
        self,
        receiver: str,
        msg_type: MessageType,
        payload: Any
    ):
        """發送訊息給其他代理"""
        message = AgentMessage(
            msg_type=msg_type,
            sender=self.name,
            receiver=receiver,
            payload=payload
        )
        await self.message_bus.send_direct(message)
    
    def log_info(self, msg: str):
        self.logger.info(f"[{self.name}] {msg}")
    
    def log_error(self, msg: str):
        self.logger.error(f"[{self.name}] {msg}")
    
    def log_warning(self, msg: str):
        self.logger.warning(f"[{self.name}] {msg}")


class AgentOrchestrator:
    """
    代理協調器 - 管理所有代理的生命週期
    """
    
    def __init__(self):
        self.logger = logging.getLogger("Orchestrator")
        self.message_bus = MessageBus()
        self.agents: Dict[str, BaseAgent] = {}
        self._tasks: List[asyncio.Task] = []
    
    def add_agent(self, agent: BaseAgent):
        """添加代理"""
        self.agents[agent.name] = agent
        self.logger.info(f"✅ 代理已添加到協調器: {agent.name}")
    
    async def start(self):
        """啟動所有代理"""
        self.logger.info("🚀 正在啟動 Multi-Agent 系統...")
        
        # 啟動訊息匯流排
        bus_task = asyncio.create_task(self.message_bus.start())
        self._tasks.append(bus_task)
        
        self.logger.info(f"📊 已註冊 {len(self.agents)} 個代理")
        for name in self.agents:
            self.logger.info(f"   - {name}")
    
    async def stop(self):
        """停止所有代理"""
        self.logger.info("🛑 正在停止 Multi-Agent 系統...")
        self.message_bus.stop()
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("✅ 系統已停止")
