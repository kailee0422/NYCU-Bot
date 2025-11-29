#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NYCU AI Award Announcement Multi-Agent System
資料模型和共用類別
"""
import hashlib
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class MessageType(Enum):
    """代理間訊息類型"""
    NEW_ANNOUNCEMENT = "new_announcement"
    TASK_ASSIGNMENT = "task_assignment"
    CONTENT_GENERATED = "content_generated"
    POST_REQUEST = "post_request"
    POST_RESULT = "post_result"
    STATUS_UPDATE = "status_update"


@dataclass
class AwardAnnouncement:
    """獲獎公告資料結構"""
    id: str
    title: str
    content: str
    url: str
    date: datetime
    image_url: Optional[str] = None
    
    def generate_id(self) -> str:
        """Generate unique ID for announcement"""
        content_hash = hashlib.md5(f"{self.title}{self.content}".encode()).hexdigest()[:8]
        return f"award_{self.date.strftime('%Y%m%d')}_{content_hash}"


@dataclass
class GeneratedContent:
    """LLM 生成的內容"""
    title_zh: str
    title_en: str
    content_zh: str
    content_en: str
    hashtags_zh: List[str]
    hashtags_en: List[str]
    platform_specific: Dict[str, str] = field(default_factory=dict)


@dataclass
class SocialPost:
    """社交媒體貼文資料結構"""
    title: str
    content: str
    hashtags: List[str]
    platform: str
    image_url: Optional[str] = None
    url: Optional[str] = None
    generated_content: Optional[GeneratedContent] = None


@dataclass
class PostResult:
    """發文結果"""
    success: bool
    platform: str
    post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AgentMessage:
    """代理間通訊訊息"""
    msg_type: MessageType
    sender: str
    receiver: str
    payload: Any
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: hashlib.md5(
        f"{datetime.now().isoformat()}".encode()
    ).hexdigest()[:12])
