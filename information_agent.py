#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Information Agent
負責監控 NYCU AI 網站並抓取獲獎公告
"""
import asyncio
from datetime import datetime
from typing import List, Optional
from urllib.parse import unquote

import aiohttp
from bs4 import BeautifulSoup

from models import AwardAnnouncement, AgentMessage, MessageType
from base_agent import BaseAgent
from config import ProcessedTracker


class InformationAgent(BaseAgent):
    """
    資訊代理
    負責從網站抓取獲獎公告並通知 Father Agent
    """
    
    def __init__(self):
        super().__init__("InformationAgent")
        self.base_url = "https://ai.nycu.edu.tw/category/hot-news/"
        self.tracker = ProcessedTracker()
        
        # 獲獎相關關鍵字
        self.award_keywords = [
            '賀', '恭賀', '恭喜', '獲獎', '獲得', '榮獲', '榮膺',
            '當選', '獲選', '入選', '得獎', '第一', '冠軍', '亞軍',
            '優等', '特優', '佳作', '優勝', '表揚', '殊榮', '榮譽',
            '最佳', '傑出', '優秀'
        ]
    
    async def handle_message(self, message: AgentMessage):
        """處理接收到的訊息"""
        if message.msg_type == MessageType.STATUS_UPDATE:
            self.log_info(f"收到狀態更新: {message.payload}")
    
    def _is_award_announcement(self, title: str, content: str = "") -> bool:
        """判斷是否為獲獎公告"""
        text_to_check = title + " " + content
        return any(keyword in text_to_check for keyword in self.award_keywords)
    
    async def _fetch_image_from_page(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Optional[str]:
        """從公告頁面抓取圖片"""
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 尋找文章內容中的圖片
                content_area = (
                    soup.find('div', class_='entry-content') or 
                    soup.find('article')
                )
                
                if content_area:
                    # 優先找 img 標籤
                    img = content_area.find('img')
                    if img and img.get('src'):
                        img_url = img['src']
                        if not img_url.startswith('http'):
                            img_url = f"https://ai.nycu.edu.tw{img_url}"
                        return img_url
                    
                    # 備選：找 figure 中的圖片
                    figure = content_area.find('figure')
                    if figure:
                        img = figure.find('img')
                        if img and img.get('src'):
                            img_url = img['src']
                            if not img_url.startswith('http'):
                                img_url = f"https://ai.nycu.edu.tw{img_url}"
                            return img_url
                
                return None
                
        except Exception as e:
            self.log_error(f"抓取圖片失敗 {url}: {e}")
            return None
    
    async def _fetch_full_content(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> str:
        """從公告頁面抓取完整內容"""
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    return ""
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                content_area = soup.find('div', class_='entry-content')
                if content_area:
                    # 移除腳本和樣式
                    for script in content_area(['script', 'style']):
                        script.decompose()
                    
                    # 取得純文字
                    text = content_area.get_text(separator='\n', strip=True)
                    return text[:1000]  # 限制長度
                
                return ""
                
        except Exception as e:
            self.log_error(f"抓取內容失敗 {url}: {e}")
            return ""
    
    async def scan_for_announcements(self) -> List[AwardAnnouncement]:
        """掃描網站獲取獲獎公告"""
        self.log_info("🔍 開始掃描獲獎公告...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, timeout=30) as response:
                    if response.status != 200:
                        self.log_error(f"無法訪問網站: {response.status}")
                        return []
                    
                    html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                announcements = []
                
                # 找所有文章
                articles = soup.find_all('article')
                self.log_info(f"找到 {len(articles)} 篇文章")
                
                for article in articles[:10]:  # 檢查最新10篇
                    try:
                        # 提取標題和URL
                        h2 = article.find('h2', class_='entry-title')
                        if not h2:
                            continue
                        
                        link = h2.find('a')
                        if not link:
                            continue
                        
                        title = link.get_text(strip=True)
                        url = unquote(link.get('href', ''))
                        
                        # 提取內容摘要
                        content = ""
                        summary_div = article.find('div', class_='entry-summary')
                        if summary_div:
                            content = summary_div.get_text(strip=True)
                        elif article.find('div', class_='entry-content'):
                            content = article.find('div', class_='entry-content').get_text(strip=True)
                        
                        # 檢查是否為獲獎公告
                        if not self._is_award_announcement(title, content):
                            self.log_info(f"跳過非獲獎公告: {title[:30]}...")
                            continue
                        
                        self.log_info(f"🎉 發現獲獎公告: {title}")
                        
                        # 抓取完整內容
                        if not content or len(content) < 50:
                            full_content = await self._fetch_full_content(session, url)
                            if full_content:
                                content = full_content
                            else:
                                content = title
                        
                        # 提取日期
                        date_published = datetime.now()
                        time_element = article.find('time', class_='entry-date published')
                        if time_element:
                            datetime_str = time_element.get('datetime', '')
                            try:
                                if datetime_str:
                                    dt = datetime.fromisoformat(
                                        datetime_str.replace('+08:00', '')
                                    )
                                    date_published = dt
                            except:
                                pass
                        
                        # 抓取圖片
                        image_url = await self._fetch_image_from_page(session, url)
                        if image_url:
                            self.log_info(f"   找到圖片: {image_url[:60]}...")
                        
                        # 建立獲獎公告物件
                        announcement = AwardAnnouncement(
                            id="",
                            title=title,
                            content=content,
                            url=url,
                            date=date_published,
                            image_url=image_url
                        )
                        announcement.id = announcement.generate_id()
                        
                        # 檢查是否已處理過
                        if self.tracker.is_processed(announcement.id):
                            self.log_info(f"   已處理過，跳過")
                            continue
                        
                        announcements.append(announcement)
                        
                    except Exception as e:
                        self.log_error(f"處理文章失敗: {e}")
                        continue
                
                self.log_info(f"✅ 找到 {len(announcements)} 個新獲獎公告")
                return announcements
                
        except Exception as e:
            self.log_error(f"掃描公告失敗: {e}")
            return []
    
    async def check_and_notify(self):
        """檢查新公告並通知 Father Agent"""
        announcements = await self.scan_for_announcements()
        
        if not announcements:
            self.log_info("沒有發現新的獲獎公告")
            return
        
        for announcement in announcements:
            self.log_info(f"📤 通知 FatherAgent: {announcement.title[:40]}...")
            
            # 發送訊息給 Father Agent
            await self.send_message(
                receiver="FatherAgent",
                msg_type=MessageType.NEW_ANNOUNCEMENT,
                payload={
                    'announcement': announcement,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            # 標記為已處理
            self.tracker.mark_processed(announcement.id)
            
            # 短暫延遲避免過快
            await asyncio.sleep(1)
    
    async def run_continuous(self, interval_minutes: int = 30):
        """持續監控模式"""
        self.log_info(f"🔄 開始持續監控 (間隔: {interval_minutes} 分鐘)")
        
        while True:
            try:
                await self.check_and_notify()
                self.log_info(f"⏰ {interval_minutes} 分鐘後再次檢查...")
                await asyncio.sleep(interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_error(f"監控錯誤: {e}")
                await asyncio.sleep(60)  # 錯誤後等待1分鐘重試
