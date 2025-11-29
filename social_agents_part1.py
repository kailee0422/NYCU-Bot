#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Social Media Posting Agents
各社交媒體平台的發文代理
"""
import asyncio
import io
import os
import tempfile
import time
from typing import Optional

import requests
import tweepy
from PIL import Image

from models import (
    SocialPost, 
    PostResult, 
    GeneratedContent,
    AgentMessage, 
    MessageType
)
from base_agent import BaseAgent
from config import Config, encode_image_url


class TwitterAgent(BaseAgent):
    """Twitter/X 發文代理"""
    
    _last_post_time = None
    _min_interval = 900  # 15分鐘
    
    def __init__(self):
        super().__init__("TwitterAgent")
        self.config = Config()
        self.client = None
        self.api = None
        self._init_client()
    
    def _init_client(self):
        """初始化 Twitter 客戶端"""
        creds = self.config.get('twitter', {})
        
        if not all(creds.get(k) for k in ['api_key', 'api_secret', 'access_token', 'access_token_secret']):
            self.log_warning("Twitter 憑證不完整")
            return
        
        try:
            self.client = tweepy.Client(
                consumer_key=creds.get('api_key'),
                consumer_secret=creds.get('api_secret'),
                access_token=creds.get('access_token'),
                access_token_secret=creds.get('access_token_secret'),
                wait_on_rate_limit=False
            )
            
            auth = tweepy.OAuth1UserHandler(
                creds.get('api_key'),
                creds.get('api_secret'),
                creds.get('access_token'),
                creds.get('access_token_secret')
            )
            self.api = tweepy.API(auth, wait_on_rate_limit=False)
            
            self.log_info("✅ Twitter 客戶端初始化成功")
        except Exception as e:
            self.log_error(f"Twitter 初始化失敗: {e}")
    
    def _setup_handlers(self):
        """設定訊息處理器"""
        self.register_handler(MessageType.POST_REQUEST, self._handle_post_request)
    
    async def _handle_post_request(self, message: AgentMessage):
        """處理發文請求"""
        payload = message.payload
        post = payload.get('post')
        image_url = payload.get('image_url')
        
        result = await self.post(post, image_url)
        
        # 回報結果
        await self.send_message(
            receiver="MotherAgent",
            msg_type=MessageType.POST_RESULT,
            payload={'platform': 'twitter', 'result': result}
        )
    
    async def handle_message(self, message: AgentMessage):
        """處理其他訊息"""
        pass
    
    async def post(self, post: SocialPost, image_url: str = None) -> PostResult:
        """發布推文"""
        if TwitterAgent._last_post_time:
            elapsed = time.time() - TwitterAgent._last_post_time
            if elapsed < self._min_interval:
                wait_time = self._min_interval - elapsed
                self.log_info(f"⏰ 速率限制保護，等待 {wait_time:.0f} 秒...")
                await asyncio.sleep(wait_time)
        
        if not self.client:
            return PostResult(False, "twitter", error="客戶端未初始化")
        
        try:
            tweet_text = self._format_tweet(post)
            final_image_url = image_url or post.image_url
            
            media_ids = []
            if final_image_url:
                media_id = await self._upload_media(final_image_url)
                if media_id:
                    media_ids = [media_id]
            
            if media_ids:
                response = self.client.create_tweet(text=tweet_text, media_ids=media_ids)
            else:
                response = self.client.create_tweet(text=tweet_text)
            
            TwitterAgent._last_post_time = time.time()
            
            if response.data:
                post_id = response.data['id']
                tweet_url = f"https://twitter.com/i/web/status/{post_id}"
                self.log_info(f"✅ 推文發布成功: {tweet_url}")
                return PostResult(True, "twitter", post_id, tweet_url)
            
            return PostResult(False, "twitter", error="無回應資料")
            
        except tweepy.errors.TooManyRequests as e:
            self.log_error(f"速率限制: {e}")
            return PostResult(False, "twitter", error=f"速率限制: {e}")
        except Exception as e:
            self.log_error(f"發文失敗: {e}")
            return PostResult(False, "twitter", error=str(e))
    
    async def _upload_media(self, image_url: str) -> Optional[str]:
        """上傳媒體"""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            image_data = io.BytesIO(response.content)
            
            img = Image.open(image_data)
            img.verify()
            image_data.seek(0)
            
            media = self.api.media_upload(filename="image.jpg", file=image_data)
            return str(media.media_id)
            
        except Exception as e:
            self.log_error(f"上傳媒體失敗: {e}")
            return None
    
    def _format_tweet(self, post: SocialPost) -> str:
        """格式化推文"""
        content = post.generated_content
        
        if content and content.platform_specific.get('twitter'):
            return content.platform_specific['twitter'][:280]
        
        hashtags = ' '.join(post.hashtags[:3])
        
        if content and content.title_en:
            text = f"🎉 {content.title_en}"
            if content.content_en:
                available = 280 - len(hashtags) - len(text) - 10
                if available > 50:
                    text += f"\n\n{content.content_en[:available]}"
        else:
            text = f"🎉 {post.title}"
        
        tweet = f"{text}\n\n{hashtags}"
        return tweet[:280]


class FacebookAgent(BaseAgent):
    """Facebook 發文代理"""
    
    def __init__(self):
        super().__init__("FacebookAgent")
        self.config = Config()
        self.api_url = "https://graph.facebook.com/v21.0"
    
    def _setup_handlers(self):
        self.register_handler(MessageType.POST_REQUEST, self._handle_post_request)
    
    async def _handle_post_request(self, message: AgentMessage):
        payload = message.payload
        post = payload.get('post')
        image_url = payload.get('image_url')
        
        result = await self.post(post, image_url)
        
        await self.send_message(
            receiver="MotherAgent",
            msg_type=MessageType.POST_RESULT,
            payload={'platform': 'facebook', 'result': result}
        )
    
    async def handle_message(self, message: AgentMessage):
        pass
    
    def _has_credentials(self) -> bool:
        creds = self.config.get('facebook', {})
        return bool(creds.get('page_id') and creds.get('access_token'))
    
    async def post(self, post: SocialPost, image_url: str = None) -> PostResult:
        """發布 Facebook 貼文"""
        if not self._has_credentials():
            return PostResult(False, "facebook", error="憑證不完整")
        
        try:
            creds = self.config.get('facebook', {})
            post_content = self._format_post(post)
            final_image_url = image_url or post.image_url
            
            if final_image_url:
                return await self._post_with_photo(post_content, final_image_url, creds)
            else:
                return await self._post_text(post_content, creds)
                
        except Exception as e:
            self.log_error(f"發文失敗: {e}")
            return PostResult(False, "facebook", error=str(e))
    
    async def _post_with_photo(self, caption: str, image_url: str, creds: dict) -> PostResult:
        encoded_url = encode_image_url(image_url)
        
        url = f"{self.api_url}/{creds['page_id']}/photos"
        params = {
            'url': encoded_url,
            'caption': caption,
            'access_token': creds['access_token']
        }
        
        response = requests.post(url, data=params)
        
        if response.status_code != 200:
            error = response.json().get('error', {}).get('message', '未知錯誤')
            return PostResult(False, "facebook", error=error)
        
        post_id = response.json().get('id')
        if post_id:
            post_url = f"https://www.facebook.com/photo.php?fbid={post_id}"
            self.log_info(f"✅ Facebook 發布成功: {post_url}")
            return PostResult(True, "facebook", post_id, post_url)
        
        return PostResult(False, "facebook", error="發布失敗")
    
    async def _post_text(self, message: str, creds: dict) -> PostResult:
        url = f"{self.api_url}/{creds['page_id']}/feed"
        params = {
            'message': message,
            'access_token': creds['access_token']
        }
        
        response = requests.post(url, data=params)
        
        if response.status_code != 200:
            error = response.json().get('error', {}).get('message', '未知錯誤')
            return PostResult(False, "facebook", error=error)
        
        post_id = response.json().get('id')
        if post_id:
            post_url = f"https://www.facebook.com/{post_id.replace('_', '/posts/')}"
            self.log_info(f"✅ Facebook 發布成功: {post_url}")
            return PostResult(True, "facebook", post_id, post_url)
        
        return PostResult(False, "facebook", error="發布失敗")
    
    def _format_post(self, post: SocialPost) -> str:
        content = post.generated_content
        hashtags = ' '.join(post.hashtags)
        
        if content:
            return f"""🎉 {content.title_zh}
{content.title_en}

{content.content_zh}

{content.content_en}

{hashtags}"""
        else:
            return f"""🎉 {post.title}

{post.content}

{hashtags}"""


class InstagramAgent(BaseAgent):
    """Instagram 發文代理"""
    
    def __init__(self):
        super().__init__("InstagramAgent")
        self.config = Config()
        self.api_url = "https://graph.facebook.com/v21.0"
    
    def _setup_handlers(self):
        self.register_handler(MessageType.POST_REQUEST, self._handle_post_request)
    
    async def _handle_post_request(self, message: AgentMessage):
        payload = message.payload
        post = payload.get('post')
        image_url = payload.get('image_url')
        
        result = await self.post(post, image_url)
        
        await self.send_message(
            receiver="MotherAgent",
            msg_type=MessageType.POST_RESULT,
            payload={'platform': 'instagram', 'result': result}
        )
    
    async def handle_message(self, message: AgentMessage):
        pass
    
    def _has_credentials(self) -> bool:
        creds = self.config.get('instagram', {})
        return bool(creds.get('access_token') and creds.get('instagram_account_id'))
    
    async def post(self, post: SocialPost, image_url: str = None) -> PostResult:
        """發布 Instagram 貼文"""
        if not self._has_credentials():
            return PostResult(False, "instagram", error="憑證不完整")
        
        final_image_url = image_url or post.image_url
        if not final_image_url:
            return PostResult(False, "instagram", error="Instagram 需要圖片")
        
        try:
            creds = self.config.get('instagram', {})
            caption = self._format_post(post)
            
            ig_account_id = creds.get('instagram_account_id')
            access_token = creds.get('access_token')
            encoded_url = encode_image_url(final_image_url)
            
            # Step 1: Create media container
            create_url = f"{self.api_url}/{ig_account_id}/media"
            create_params = {
                'image_url': encoded_url,
                'caption': caption,
                'media_type': 'IMAGE',
                'access_token': access_token
            }
            
            create_response = requests.post(create_url, params=create_params)
            
            if create_response.status_code != 200:
                error = create_response.json().get('error', {}).get('message', '未知錯誤')
                return PostResult(False, "instagram", error=f"建立媒體失敗: {error}")
            
            container_id = create_response.json().get('id')
            
            # Step 2: Publish
            publish_url = f"{self.api_url}/{ig_account_id}/media_publish"
            publish_params = {
                'creation_id': container_id,
                'access_token': access_token
            }
            
            publish_response = requests.post(publish_url, params=publish_params)
            
            if publish_response.status_code != 200:
                error = publish_response.json().get('error', {}).get('message', '未知錯誤')
                return PostResult(False, "instagram", error=f"發布失敗: {error}")
            
            post_id = publish_response.json().get('id')
            post_url = f"https://www.instagram.com/p/{post_id}/"
            
            self.log_info(f"✅ Instagram 發布成功: {post_url}")
            return PostResult(True, "instagram", post_id, post_url)
            
        except Exception as e:
            self.log_error(f"發文失敗: {e}")
            return PostResult(False, "instagram", error=str(e))
    
    def _format_post(self, post: SocialPost) -> str:
        content = post.generated_content
        hashtags = ' '.join(post.hashtags)
        
        if content:
            text = f"""🎉 {content.title_zh}
{content.title_en}

{content.content_zh[:150]}

{content.content_en[:150]}

{hashtags}

#NYCU #AI #Research #Innovation #Taiwan #Award"""
        else:
            text = f"""🎉 {post.title}

{post.content[:250]}

{hashtags}

#NYCU #AI #Research #Innovation #Taiwan #Award"""
        
        return text[:2200]
