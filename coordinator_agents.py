#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Father Agent 和 Mother Agent
負責協調和分配任務的核心代理
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from models import (
    AwardAnnouncement,
    SocialPost,
    GeneratedContent,
    PostResult,
    AgentMessage,
    MessageType
)
from base_agent import BaseAgent


class FatherAgent(BaseAgent):
    """
    Father Agent
    接收 Information Agent 的消息，轉交給 Mother Agent 處理
    負責整體流程的監控和日誌記錄
    """
    
    def __init__(self):
        super().__init__("FatherAgent")
        self.pending_announcements: Dict[str, AwardAnnouncement] = {}
        self.processing_stats = {
            'received': 0,
            'forwarded': 0,
            'completed': 0,
            'failed': 0
        }
    
    def _setup_handlers(self):
        """設定訊息處理器"""
        self.register_handler(
            MessageType.NEW_ANNOUNCEMENT,
            self._handle_new_announcement
        )
        self.register_handler(
            MessageType.STATUS_UPDATE,
            self._handle_status_update
        )
    
    async def _handle_new_announcement(self, message: AgentMessage):
        """處理來自 Information Agent 的新公告"""
        payload = message.payload
        announcement = payload.get('announcement')
        
        if not announcement:
            self.log_error("收到無效的公告訊息")
            return
        
        self.processing_stats['received'] += 1
        self.log_info(f"📥 收到新公告: {announcement.title[:50]}...")
        
        # 記錄待處理的公告
        self.pending_announcements[announcement.id] = announcement
        
        # 轉交給 Mother Agent
        self.log_info(f"📤 轉交任務給 MotherAgent...")
        await self.send_message(
            receiver="MotherAgent",
            msg_type=MessageType.TASK_ASSIGNMENT,
            payload={
                'announcement': announcement,
                'priority': self._calculate_priority(announcement),
                'timestamp': datetime.now().isoformat()
            }
        )
        self.processing_stats['forwarded'] += 1
    
    async def _handle_status_update(self, message: AgentMessage):
        """處理狀態更新"""
        payload = message.payload
        status = payload.get('status')
        announcement_id = payload.get('announcement_id')
        
        if status == 'completed':
            self.processing_stats['completed'] += 1
            if announcement_id in self.pending_announcements:
                del self.pending_announcements[announcement_id]
            self.log_info(f"✅ 公告處理完成: {announcement_id}")
        elif status == 'failed':
            self.processing_stats['failed'] += 1
            self.log_error(f"❌ 公告處理失敗: {announcement_id}")
        
        # 輸出統計資訊
        self._print_stats()
    
    def _calculate_priority(self, announcement: AwardAnnouncement) -> int:
        """計算公告優先級"""
        priority = 5  # 預設中等優先級
        
        # 標題包含特定關鍵字增加優先級
        high_priority_keywords = ['國際', '世界', '冠軍', '第一', '最佳', '傑出']
        for keyword in high_priority_keywords:
            if keyword in announcement.title:
                priority = min(priority + 1, 10)
        
        return priority
    
    def _print_stats(self):
        """輸出統計資訊"""
        stats = self.processing_stats
        self.log_info(
            f"📊 統計: 收到 {stats['received']} | "
            f"轉交 {stats['forwarded']} | "
            f"完成 {stats['completed']} | "
            f"失敗 {stats['failed']}"
        )
    
    async def handle_message(self, message: AgentMessage):
        """處理其他訊息"""
        self.log_info(f"收到訊息: {message.msg_type.value} 來自 {message.sender}")


class MotherAgent(BaseAgent):
    """
    Mother Agent (任務分配師)
    負責協調 Children Agents 完成任務：
    1. 先讓 Content Agent 生成內容
    2. 然後分配給各平台 Agent 發布
    """
    
    def __init__(self):
        super().__init__("MotherAgent")
        self.active_tasks: Dict[str, dict] = {}
        self.platform_agents = [
            'TwitterAgent',
            'FacebookAgent',
            'InstagramAgent',
            'LinkedInAgent',
            'RedditAgent'
        ]
        self.results_buffer: Dict[str, Dict[str, PostResult]] = {}
    
    def _setup_handlers(self):
        """設定訊息處理器"""
        self.register_handler(
            MessageType.TASK_ASSIGNMENT,
            self._handle_task_assignment
        )
        self.register_handler(
            MessageType.CONTENT_GENERATED,
            self._handle_content_generated
        )
        self.register_handler(
            MessageType.POST_RESULT,
            self._handle_post_result
        )
    
    async def _handle_task_assignment(self, message: AgentMessage):
        """處理來自 Father Agent 的任務分配"""
        payload = message.payload
        announcement = payload.get('announcement')
        
        if not announcement:
            self.log_error("收到無效的任務")
            return
        
        self.log_info(f"📋 收到任務: {announcement.title[:40]}...")
        
        # 記錄活動任務
        task_id = announcement.id
        self.active_tasks[task_id] = {
            'announcement': announcement,
            'status': 'generating_content',
            'started_at': datetime.now(),
            'generated_content': None,
            'post_results': {}
        }
        self.results_buffer[task_id] = {}
        
        # Step 1: 分配給 Content Agent 生成內容
        self.log_info(f"📝 分配給 ContentAgent 生成內容...")
        await self.send_message(
            receiver="ContentAgent",
            msg_type=MessageType.TASK_ASSIGNMENT,
            payload={
                'announcement': announcement,
                'task_id': task_id
            }
        )
    
    async def _handle_content_generated(self, message: AgentMessage):
        """處理 Content Agent 生成的內容"""
        payload = message.payload
        announcement = payload.get('announcement')
        generated_content = payload.get('generated_content')
        
        if not announcement or not generated_content:
            self.log_error("收到無效的內容生成結果")
            return
        
        task_id = announcement.id
        
        if task_id not in self.active_tasks:
            self.log_warning(f"找不到任務: {task_id}")
            return
        
        self.log_info(f"✅ 內容生成完成，開始分配發布任務...")
        
        # 更新任務狀態
        self.active_tasks[task_id]['status'] = 'posting'
        self.active_tasks[task_id]['generated_content'] = generated_content
        
        # Step 2: 建立 SocialPost 並分配給各平台 Agent
        post = self._create_social_post(announcement, generated_content)
        
        # 分配給各平台
        for agent_name in self.platform_agents:
            self.log_info(f"   📤 分配給 {agent_name}...")
            
            await self.send_message(
                receiver=agent_name,
                msg_type=MessageType.POST_REQUEST,
                payload={
                    'post': post,
                    'image_url': announcement.image_url,
                    'task_id': task_id,
                    'subreddit': 'nycu' if agent_name == 'RedditAgent' else None
                }
            )
            
            # 短暫延遲避免同時請求
            await asyncio.sleep(1)
    
    async def _handle_post_result(self, message: AgentMessage):
        """處理各平台的發布結果"""
        payload = message.payload
        platform = payload.get('platform')
        result = payload.get('result')
        
        if not platform or not result:
            return
        
        # 找到對應的任務
        task_id = None
        for tid, task in self.active_tasks.items():
            if task['status'] == 'posting':
                task_id = tid
                break
        
        if not task_id:
            self.log_warning(f"找不到對應的任務 (platform: {platform})")
            return
        
        # 記錄結果
        self.results_buffer[task_id][platform] = result
        
        if result.success:
            self.log_info(f"   ✅ {platform}: {result.url}")
        else:
            self.log_warning(f"   ⚠️ {platform}: {result.error}")
        
        # 檢查是否所有平台都完成了
        expected_count = len(self.platform_agents)
        received_count = len(self.results_buffer[task_id])
        
        if received_count >= expected_count:
            await self._finalize_task(task_id)
    
    async def _finalize_task(self, task_id: str):
        """完成任務並回報結果"""
        if task_id not in self.active_tasks:
            return
        
        task = self.active_tasks[task_id]
        results = self.results_buffer.get(task_id, {})
        
        success_count = sum(1 for r in results.values() if r.success)
        total_count = len(results)
        
        self.log_info(f"\n{'='*50}")
        self.log_info(f"📊 任務完成: {task['announcement'].title[:40]}...")
        self.log_info(f"   成功: {success_count}/{total_count} 個平台")
        self.log_info(f"{'='*50}\n")
        
        # 通知 Father Agent
        status = 'completed' if success_count > 0 else 'failed'
        await self.send_message(
            receiver="FatherAgent",
            msg_type=MessageType.STATUS_UPDATE,
            payload={
                'status': status,
                'announcement_id': task_id,
                'results': {
                    platform: {
                        'success': r.success,
                        'url': r.url,
                        'error': r.error
                    }
                    for platform, r in results.items()
                }
            }
        )
        
        # 清理
        del self.active_tasks[task_id]
        if task_id in self.results_buffer:
            del self.results_buffer[task_id]
    
    def _create_social_post(
        self,
        announcement: AwardAnnouncement,
        generated_content: GeneratedContent
    ) -> SocialPost:
        """建立 SocialPost 物件"""
        # 合併 hashtags
        all_hashtags = list(set(
            generated_content.hashtags_zh + 
            generated_content.hashtags_en
        ))
        
        return SocialPost(
            title=announcement.title,
            content=announcement.content,
            hashtags=all_hashtags,
            platform="all",
            image_url=announcement.image_url,
            url=announcement.url,
            generated_content=generated_content
        )
    
    async def handle_message(self, message: AgentMessage):
        """處理其他訊息"""
        self.log_info(f"收到訊息: {message.msg_type.value} 來自 {message.sender}")
