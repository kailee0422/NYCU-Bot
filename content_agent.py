#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Content Agent
使用 LangChain + Ollama (DeepSeek-R1) 生成社交媒體貼文內容
"""
import asyncio
import re
from typing import Optional, Dict, List

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models import (
    AwardAnnouncement, 
    GeneratedContent, 
    AgentMessage, 
    MessageType
)
from base_agent import BaseAgent
from config import Config


class ContentAgent(BaseAgent):
    """
    內容生成代理
    使用 LangChain + Ollama 生成中英文恭喜文章和 hashtags
    """
    
    def __init__(self):
        super().__init__("ContentAgent")
        self.config = Config()
        self.llm = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化 LLM"""
        ollama_config = self.config.get('ollama', {})
        base_url = ollama_config.get('base_url', 'http://localhost:11434')
        model = ollama_config.get('model', 'deepseek-r1:7b')
        
        try:
            self.llm = ChatOllama(
                base_url=base_url,
                model=model,
                temperature=0.7,
                num_predict=2048,
            )
            self.log_info(f"✅ LLM 初始化成功: {model} @ {base_url}")
        except Exception as e:
            self.log_error(f"❌ LLM 初始化失敗: {e}")
            self.llm = None
    
    def _setup_handlers(self):
        """設定訊息處理器"""
        self.register_handler(
            MessageType.TASK_ASSIGNMENT,
            self._handle_task_assignment
        )
    
    async def _handle_task_assignment(self, message: AgentMessage):
        """處理任務分配"""
        payload = message.payload
        announcement = payload.get('announcement')
        
        if announcement:
            self.log_info(f"📝 開始生成內容: {announcement.title[:40]}...")
            content = await self.generate_content(announcement)
            
            if content:
                # 回傳生成的內容給 Mother Agent
                await self.send_message(
                    receiver="MotherAgent",
                    msg_type=MessageType.CONTENT_GENERATED,
                    payload={
                        'announcement': announcement,
                        'generated_content': content
                    }
                )
    
    async def handle_message(self, message: AgentMessage):
        """處理其他訊息"""
        self.log_info(f"收到訊息: {message.msg_type.value}")
    
    async def generate_content(
        self,
        announcement: AwardAnnouncement
    ) -> Optional[GeneratedContent]:
        """生成社交媒體內容"""
        if not self.llm:
            self.log_error("LLM 未初始化，使用備用生成方式")
            return self._fallback_generate(announcement)
        
        try:
            # 生成中文內容
            content_zh = await self._generate_chinese_content(announcement)
            
            # 生成英文內容
            content_en = await self._generate_english_content(announcement)
            
            # 生成 hashtags
            hashtags_zh, hashtags_en = await self._generate_hashtags(announcement)
            
            # 生成平台特定內容
            platform_content = await self._generate_platform_specific(
                announcement, content_zh, content_en
            )
            
            result = GeneratedContent(
                title_zh=announcement.title,
                title_en=content_en.get('title', ''),
                content_zh=content_zh,
                content_en=content_en.get('content', ''),
                hashtags_zh=hashtags_zh,
                hashtags_en=hashtags_en,
                platform_specific=platform_content
            )
            
            self.log_info("✅ 內容生成完成")
            return result
            
        except Exception as e:
            self.log_error(f"內容生成失敗: {e}")
            return self._fallback_generate(announcement)
    
    async def _generate_chinese_content(
        self,
        announcement: AwardAnnouncement
    ) -> str:
        """生成中文恭喜內容"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是陽明交通大學 AI 學院的社交媒體編輯。
你的任務是將獲獎公告改寫成適合社交媒體發布的恭喜文章。

要求：
1. 保持正式但親切的語氣
2. 突出獲獎者的成就
3. 包含對學校和學院的正面形象
4. 適合在 Facebook、LinkedIn 等平台發布
5. 字數控制在 200 字以內"""),
            ("user", """請將以下獲獎公告改寫成社交媒體恭喜貼文：

標題：{title}

原文：{content}

請直接輸出改寫後的內容，不需要其他說明。""")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    chain.invoke,
                    {"title": announcement.title, "content": announcement.content}
                ),
                timeout=60
            )
            # 清理可能的思考過程標記
            result = self._clean_output(result)
            return result
        except asyncio.TimeoutError:
            self.log_warning("中文內容生成超時")
            return announcement.content
        except Exception as e:
            self.log_error(f"中文內容生成錯誤: {e}")
            return announcement.content
    
    async def _generate_english_content(
        self,
        announcement: AwardAnnouncement
    ) -> Dict[str, str]:
        """生成英文內容（標題和內文）"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a social media editor for National Yang Ming Chiao Tung University (NYCU) College of AI.
Your task is to create an English congratulatory post for award announcements.

Requirements:
1. Professional yet warm tone
2. Highlight the achievement
3. Keep it concise (under 150 words)
4. Suitable for Twitter, LinkedIn, and international audiences
5. Include the English translation of Chinese names in pinyin format (e.g., 王大明 -> Wang Da-Ming)"""),
            ("user", """Please create an English social media post for this award announcement:

Title: {title}

Content: {content}

Output format:
TITLE: [English title]
CONTENT: [English content]""")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    chain.invoke,
                    {"title": announcement.title, "content": announcement.content}
                ),
                timeout=60
            )
            
            result = self._clean_output(result)
            
            # 解析輸出
            title_en = ""
            content_en = ""
            
            lines = result.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('TITLE:'):
                    title_en = line.replace('TITLE:', '').strip()
                elif line.startswith('CONTENT:'):
                    content_en = '\n'.join(lines[i:]).replace('CONTENT:', '').strip()
                    break
            
            if not title_en:
                title_en = f"Congratulations! {announcement.title}"
            if not content_en:
                content_en = result
            
            return {"title": title_en, "content": content_en}
            
        except asyncio.TimeoutError:
            self.log_warning("英文內容生成超時")
            return {"title": announcement.title, "content": announcement.content}
        except Exception as e:
            self.log_error(f"英文內容生成錯誤: {e}")
            return {"title": announcement.title, "content": announcement.content}
    
    async def _generate_hashtags(
        self,
        announcement: AwardAnnouncement
    ) -> tuple:
        """生成中英文 hashtags"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate relevant hashtags for a university award announcement.
Output exactly 5 Chinese hashtags and 5 English hashtags.

Format:
ZH: #tag1 #tag2 #tag3 #tag4 #tag5
EN: #tag1 #tag2 #tag3 #tag4 #tag5"""),
            ("user", "Title: {title}\nContent: {content}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        default_zh = ["#陽明交大", "#AI學院", "#獲獎", "#人工智慧", "#研究"]
        default_en = ["#NYCU", "#AI", "#Award", "#Research", "#Achievement"]
        
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    chain.invoke,
                    {"title": announcement.title, "content": announcement.content}
                ),
                timeout=30
            )
            
            result = self._clean_output(result)
            
            hashtags_zh = default_zh
            hashtags_en = default_en
            
            for line in result.split('\n'):
                if line.startswith('ZH:'):
                    tags = re.findall(r'#[\w\u4e00-\u9fff]+', line)
                    if tags:
                        hashtags_zh = tags[:5]
                elif line.startswith('EN:'):
                    tags = re.findall(r'#\w+', line)
                    if tags:
                        hashtags_en = tags[:5]
            
            return hashtags_zh, hashtags_en
            
        except Exception as e:
            self.log_warning(f"Hashtag 生成使用預設值: {e}")
            return default_zh, default_en
    
    async def _generate_platform_specific(
        self,
        announcement: AwardAnnouncement,
        content_zh: str,
        content_en: Dict[str, str]
    ) -> Dict[str, str]:
        """生成平台特定內容"""
        platform_content = {}
        
        # Twitter - 需要精簡版本
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Create a tweet (max 250 characters) for this announcement.
Use English only. Include 2-3 relevant hashtags.
Be concise and impactful."""),
            ("user", "Title: {title}\nContent: {content}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            twitter_content = await asyncio.wait_for(
                asyncio.to_thread(
                    chain.invoke,
                    {
                        "title": announcement.title,
                        "content": content_en.get('content', announcement.content)
                    }
                ),
                timeout=30
            )
            twitter_content = self._clean_output(twitter_content)
            platform_content['twitter'] = twitter_content[:280]
        except Exception as e:
            self.log_warning(f"Twitter 內容生成失敗: {e}")
            platform_content['twitter'] = f"🎉 {content_en.get('title', announcement.title)[:200]}"
        
        return platform_content
    
    def _clean_output(self, text: str) -> str:
        """清理 LLM 輸出中的思考過程標記"""
        # 移除 <think>...</think> 標記
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # 移除其他常見的思考標記
        text = re.sub(r'\[思考\].*?\[/思考\]', '', text, flags=re.DOTALL)
        text = re.sub(r'\[thinking\].*?\[/thinking\]', '', text, flags=re.DOTALL | re.IGNORECASE)
        return text.strip()
    
    def _fallback_generate(
        self,
        announcement: AwardAnnouncement
    ) -> GeneratedContent:
        """備用生成方式（不使用 LLM）"""
        self.log_info("使用備用內容生成方式")
        
        return GeneratedContent(
            title_zh=announcement.title,
            title_en=f"Congratulations! {announcement.title}",
            content_zh=f"🎉 恭喜！{announcement.content}",
            content_en=f"🎉 Congratulations! We are proud to announce this achievement.",
            hashtags_zh=["#陽明交大", "#AI學院", "#獲獎", "#人工智慧", "#研究"],
            hashtags_en=["#NYCU", "#AI", "#Award", "#Research", "#Achievement"],
            platform_specific={
                'twitter': f"🎉 {announcement.title[:200]} #NYCU #AI #Award"
            }
        )
