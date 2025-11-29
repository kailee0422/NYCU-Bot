#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NYCU AI Award Announcement Multi-Agent System
主程式入口點

Multi-Agent 架構說明：
├── InformationAgent (資訊代理)
│   └── 監控網站，發現新公告時通知 FatherAgent
│
├── FatherAgent (父代理)
│   └── 接收公告，轉交給 MotherAgent 處理
│
├── MotherAgent (母代理/任務分配師)
│   └── 協調 Children Agents 完成任務
│       ├── 1. 先分配給 ContentAgent 生成內容
│       └── 2. 再分配給各平台 Agent 發布
│
└── Children Agents (子代理們)
    ├── ContentAgent (使用 Ollama/LangChain 生成內容)
    ├── TwitterAgent
    ├── FacebookAgent
    ├── InstagramAgent
    ├── LinkedInAgent
    └── RedditAgent
"""
import sys
import asyncio
import logging
from datetime import datetime

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('award_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 匯入代理
from base_agent import AgentOrchestrator, MessageBus
from information_agent import InformationAgent
from coordinator_agents import FatherAgent, MotherAgent
from content_agent import ContentAgent
from social_agents_part1 import TwitterAgent, FacebookAgent, InstagramAgent
from social_agents_part2 import LinkedInAgent, RedditAgent
from config import Config


class MultiAgentSystem:
    """Multi-Agent 系統主類別"""
    
    def __init__(self):
        self.orchestrator = AgentOrchestrator()
        self.agents = {}
        self._init_agents()
    
    def _init_agents(self):
        """初始化所有代理"""
        logger.info("\n" + "="*60)
        logger.info("🤖 初始化 Multi-Agent 系統")
        logger.info("="*60 + "\n")
        
        # 建立代理
        self.agents = {
            'information': InformationAgent(),
            'father': FatherAgent(),
            'mother': MotherAgent(),
            'content': ContentAgent(),
            'twitter': TwitterAgent(),
            'facebook': FacebookAgent(),
            'instagram': InstagramAgent(),
            'linkedin': LinkedInAgent(),
            'reddit': RedditAgent()
        }
        
        # 註冊到協調器
        for name, agent in self.agents.items():
            self.orchestrator.add_agent(agent)
        
        logger.info("\n✅ 所有代理初始化完成\n")
    
    async def run_once(self):
        """執行一次檢查和發布流程"""
        logger.info("\n" + "="*60)
        logger.info("🚀 開始執行單次檢查")
        logger.info("="*60 + "\n")
        
        # 啟動協調器
        await self.orchestrator.start()
        
        # 讓 InformationAgent 檢查並通知
        await self.agents['information'].check_and_notify()
        
        # 等待處理完成（給予足夠時間）
        logger.info("⏳ 等待任務處理完成...")
        await asyncio.sleep(60)  # 根據需要調整
        
        # 停止系統
        await self.orchestrator.stop()
        
        logger.info("\n✅ 單次執行完成\n")
    
    async def run_continuous(self, interval_minutes: int = 30):
        """持續監控模式"""
        logger.info("\n" + "="*60)
        logger.info("🤖 NYCU AI 獲獎公告 Multi-Agent 系統")
        logger.info("="*60)
        logger.info(f"📍 監控網址: https://ai.nycu.edu.tw/category/hot-news/")
        logger.info(f"⏰ 檢查間隔: {interval_minutes} 分鐘")
        logger.info(f"📝 日誌檔案: award_bot.log")
        logger.info("\n系統架構:")
        logger.info("  InformationAgent → FatherAgent → MotherAgent")
        logger.info("                                   ├── ContentAgent (LLM)")
        logger.info("                                   ├── TwitterAgent")
        logger.info("                                   ├── FacebookAgent")
        logger.info("                                   ├── InstagramAgent")
        logger.info("                                   ├── LinkedInAgent")
        logger.info("                                   └── RedditAgent")
        logger.info("\n按 Ctrl+C 停止程式\n")
        logger.info("-"*60 + "\n")
        
        # 啟動協調器
        await self.orchestrator.start()
        
        try:
            while True:
                # 執行檢查
                await self.agents['information'].check_and_notify()
                
                # 等待處理完成
                await asyncio.sleep(120)  # 2 分鐘內完成所有發布
                
                # 顯示下次檢查時間
                next_check = datetime.now()
                logger.info(
                    f"\n⏰ {next_check.strftime('%H:%M')} - 檢查完成，"
                    f"{interval_minutes} 分鐘後再次檢查...\n"
                )
                
                # 等待下次檢查
                await asyncio.sleep((interval_minutes - 2) * 60)
                
        except KeyboardInterrupt:
            logger.info("\n\n🛑 收到停止信號...")
        finally:
            await self.orchestrator.stop()
            logger.info("✅ 系統已停止")
    
    async def test_content_generation(self):
        """測試內容生成功能"""
        from models import AwardAnnouncement
        
        logger.info("\n" + "="*60)
        logger.info("🧪 測試內容生成功能")
        logger.info("="*60 + "\n")
        
        # 建立測試公告
        test_announcement = AwardAnnouncement(
            id="test_001",
            title="賀！本院王大明教授榮獲2024年度最佳論文獎",
            content="本院王大明教授發表之論文「基於深度學習的智慧型系統」"
                   "榮獲2024年度台灣人工智慧學會最佳論文獎，"
                   "此論文提出創新的神經網路架構，在多項任務上達到最佳效能。",
            url="https://ai.nycu.edu.tw/test",
            date=datetime.now(),
            image_url=None
        )
        
        content_agent = self.agents['content']
        
        logger.info(f"📝 測試公告: {test_announcement.title}")
        logger.info(f"   內容: {test_announcement.content[:50]}...\n")
        
        # 生成內容
        result = await content_agent.generate_content(test_announcement)
        
        if result:
            logger.info("✅ 內容生成成功！\n")
            logger.info(f"中文標題: {result.title_zh}")
            logger.info(f"英文標題: {result.title_en}")
            logger.info(f"\n中文內容:\n{result.content_zh}")
            logger.info(f"\n英文內容:\n{result.content_en}")
            logger.info(f"\n中文 Hashtags: {' '.join(result.hashtags_zh)}")
            logger.info(f"英文 Hashtags: {' '.join(result.hashtags_en)}")
            
            if result.platform_specific.get('twitter'):
                logger.info(f"\nTwitter 專用:\n{result.platform_specific['twitter']}")
        else:
            logger.error("❌ 內容生成失敗")


def setup_credentials():
    """設定社交媒體憑證"""
    print("\n" + "="*60)
    print("    社交媒體憑證設定")
    print("="*60 + "\n")
    
    config = Config()
    credentials = config.credentials.copy()
    
    print("📘 Facebook 設定:")
    print("   (留空跳過)")
    credentials['facebook'] = {
        'page_id': input("   Page ID: ") or credentials.get('facebook', {}).get('page_id', ''),
        'access_token': input("   Access Token: ") or credentials.get('facebook', {}).get('access_token', '')
    }
    
    print("\n📷 Instagram 設定:")
    print("   (留空跳過)")
    credentials['instagram'] = {
        'access_token': input("   Access Token: ") or credentials.get('instagram', {}).get('access_token', ''),
        'instagram_account_id': input("   Instagram Account ID: ") or credentials.get('instagram', {}).get('instagram_account_id', '')
    }
    
    print("\n🐦 Twitter/X 設定:")
    print("   (留空跳過)")
    credentials['twitter'] = {
        'api_key': input("   API Key: ") or credentials.get('twitter', {}).get('api_key', ''),
        'api_secret': input("   API Secret: ") or credentials.get('twitter', {}).get('api_secret', ''),
        'access_token': input("   Access Token: ") or credentials.get('twitter', {}).get('access_token', ''),
        'access_token_secret': input("   Access Token Secret: ") or credentials.get('twitter', {}).get('access_token_secret', '')
    }
    
    print("\n🤖 Reddit 設定:")
    print("   (留空跳過)")
    credentials['reddit'] = {
        'client_id': input("   Client ID: ") or credentials.get('reddit', {}).get('client_id', ''),
        'client_secret': input("   Client Secret: ") or credentials.get('reddit', {}).get('client_secret', ''),
        'username': input("   Username: ") or credentials.get('reddit', {}).get('username', ''),
        'password': input("   Password: ") or credentials.get('reddit', {}).get('password', ''),
        'user_agent': 'NYCUBot/1.0'
    }
    
    print("\n💼 LinkedIn 設定:")
    print("   (留空跳過)")
    credentials['linkedin'] = {
        'access_token': input("   Access Token: ") or credentials.get('linkedin', {}).get('access_token', '')
    }
    
    print("\n🤖 Ollama 設定:")
    print("   (用於內容生成的本地 LLM)")
    ollama_url = input(f"   Ollama URL [{credentials.get('ollama', {}).get('base_url', 'http://localhost:11434')}]: ")
    ollama_model = input(f"   Model [{credentials.get('ollama', {}).get('model', 'deepseek-r1:7b')}]: ")
    
    credentials['ollama'] = {
        'base_url': ollama_url or credentials.get('ollama', {}).get('base_url', 'http://localhost:11434'),
        'model': ollama_model or credentials.get('ollama', {}).get('model', 'deepseek-r1:7b')
    }
    
    # 儲存設定
    import json
    with open('social_config.json', 'w', encoding='utf-8') as f:
        json.dump(credentials, f, indent=2, ensure_ascii=False)
    
    print("\n✅ 憑證已儲存到 social_config.json")


async def test_scan():
    """測試網站掃描功能"""
    print("\n🧪 測試模式 - 只顯示獲獎公告，不進行發布\n")
    
    info_agent = InformationAgent()
    announcements = await info_agent.scan_for_announcements()
    
    if announcements:
        print(f"\n找到 {len(announcements)} 個獲獎公告:\n")
        for ann in announcements:
            print(f"📌 {ann.title}")
            print(f"   日期: {ann.date.strftime('%Y-%m-%d')}")
            print(f"   連結: {ann.url}")
            print(f"   圖片: {'有' if ann.image_url else '無'}")
            print(f"   內容: {ann.content[:100]}...")
            print()
    else:
        print("\n沒有找到獲獎公告")


def print_help():
    """印出幫助訊息"""
    print("\n🤖 NYCU AI 獲獎公告 Multi-Agent 自動發布系統")
    print("\n可用指令:")
    print("  python main.py setup          - 設定社交媒體憑證和 Ollama")
    print("  python main.py test           - 測試模式(只掃描不發布)")
    print("  python main.py test-llm       - 測試 LLM 內容生成")
    print("  python main.py run            - 執行一次檢查並發布")
    print("  python main.py start [分鐘]   - 背景持續執行(預設30分鐘)")
    print("\nMulti-Agent 架構:")
    print("  InformationAgent → FatherAgent → MotherAgent")
    print("                                   ├── ContentAgent (Ollama LLM)")
    print("                                   ├── TwitterAgent")
    print("                                   ├── FacebookAgent")
    print("                                   ├── InstagramAgent")
    print("                                   ├── LinkedInAgent")
    print("                                   └── RedditAgent")
    print("\n建議執行順序:")
    print("  1. python main.py setup      # 設定憑證")
    print("  2. python main.py test       # 測試網站掃描")
    print("  3. python main.py test-llm   # 測試 LLM 內容生成")
    print("  4. python main.py run        # 執行一次")
    print("  5. python main.py start      # 開始背景監控")
    print("\n⚠️  請確保 Ollama 已在 Windows 上運行，並已下載 deepseek-r1:7b 模型")
    print("   安裝指令: ollama pull deepseek-r1:7b")


async def main():
    """主程式入口"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'setup':
            setup_credentials()
        
        elif command == 'test':
            await test_scan()
        
        elif command == 'test-llm':
            system = MultiAgentSystem()
            await system.test_content_generation()
        
        elif command == 'run':
            system = MultiAgentSystem()
            await system.run_once()
        
        elif command == 'start':
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            system = MultiAgentSystem()
            await system.run_continuous(interval)
        
        else:
            print(f"❌ 未知指令: {command}")
            print_help()
    
    else:
        print_help()


if __name__ == "__main__":
    asyncio.run(main())
