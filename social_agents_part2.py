#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Social Media Posting Agents - Part 2
LinkedIn 和 Reddit 發文代理
"""
import os
import tempfile
from typing import Optional

import requests
import praw

from models import (
    SocialPost, 
    PostResult,
    AgentMessage, 
    MessageType
)
from base_agent import BaseAgent
from config import Config


class LinkedInAgent(BaseAgent):
    """LinkedIn 發文代理"""
    
    def __init__(self):
        super().__init__("LinkedInAgent")
        self.config = Config()
        self.api_url = "https://api.linkedin.com/v2"
        self.user_id = None
    
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
            payload={'platform': 'linkedin', 'result': result}
        )
    
    async def handle_message(self, message: AgentMessage):
        pass
    
    def _has_credentials(self) -> bool:
        creds = self.config.get('linkedin', {})
        return bool(creds.get('access_token'))
    
    async def _get_user_id(self) -> Optional[str]:
        """獲取 LinkedIn 用戶 ID"""
        if self.user_id:
            return self.user_id
        
        try:
            creds = self.config.get('linkedin', {})
            headers = {'Authorization': f"Bearer {creds['access_token']}"}
            
            response = requests.get(
                'https://api.linkedin.com/v2/userinfo',
                headers=headers
            )
            
            if response.status_code != 200:
                self.log_error("獲取用戶 ID 失敗")
                return None
            
            self.user_id = response.json().get('sub')
            return self.user_id
            
        except Exception as e:
            self.log_error(f"獲取用戶 ID 錯誤: {e}")
            return None
    
    async def _upload_image(self, image_url: str, user_id: str) -> Optional[str]:
        """上傳圖片到 LinkedIn"""
        try:
            creds = self.config.get('linkedin', {})
            headers = {
                'Authorization': f"Bearer {creds['access_token']}",
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0'
            }
            
            # 註冊上傳
            register_payload = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": f"urn:li:person:{user_id}",
                    "serviceRelationships": [{
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }]
                }
            }
            
            register_response = requests.post(
                f"{self.api_url}/assets?action=registerUpload",
                headers=headers,
                json=register_payload
            )
            
            if register_response.status_code not in [200, 201]:
                self.log_error(f"註冊上傳失敗: {register_response.text}")
                return None
            
            register_data = register_response.json()
            asset = register_data['value']['asset']
            upload_url = register_data['value']['uploadMechanism'][
                'com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            
            # 下載圖片
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()
            
            # 上傳圖片
            upload_headers = {
                'Authorization': f"Bearer {creds['access_token']}",
                'Content-Type': 'application/octet-stream'
            }
            
            upload_response = requests.put(
                upload_url,
                headers=upload_headers,
                data=image_response.content
            )
            
            if upload_response.status_code not in [200, 201]:
                return None
            
            return asset
            
        except Exception as e:
            self.log_error(f"上傳圖片錯誤: {e}")
            return None
    
    async def post(self, post: SocialPost, image_url: str = None) -> PostResult:
        """發布 LinkedIn 貼文"""
        if not self._has_credentials():
            return PostResult(False, "linkedin", error="憑證不完整")
        
        try:
            user_id = await self._get_user_id()
            if not user_id:
                return PostResult(False, "linkedin", error="無法獲取用戶 ID")
            
            creds = self.config.get('linkedin', {})
            post_content = self._format_post(post)
            final_image_url = image_url or post.image_url
            
            # 上傳圖片
            media_asset = None
            if final_image_url:
                media_asset = await self._upload_image(final_image_url, user_id)
            
            headers = {
                'Authorization': f"Bearer {creds['access_token']}",
                'Content-Type': 'application/json',
                'X-Restli-Protocol-Version': '2.0.0'
            }
            
            if media_asset:
                payload = {
                    "author": f"urn:li:person:{user_id}",
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": post_content},
                            "shareMediaCategory": "IMAGE",
                            "media": [{
                                "status": "READY",
                                "description": {"text": post.title[:200]},
                                "media": media_asset,
                                "title": {"text": post.title[:100]}
                            }]
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    }
                }
            else:
                payload = {
                    "author": f"urn:li:person:{user_id}",
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": post_content},
                            "shareMediaCategory": "NONE"
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    }
                }
            
            response = requests.post(
                f"{self.api_url}/ugcPosts",
                headers=headers,
                json=payload
            )
            
            if response.status_code not in [200, 201]:
                error = response.json().get('message', '未知錯誤')
                return PostResult(False, "linkedin", error=error)
            
            post_id = response.json().get('id', '')
            post_url = f"https://www.linkedin.com/feed/update/{post_id}/"
            
            self.log_info(f"✅ LinkedIn 發布成功: {post_url}")
            return PostResult(True, "linkedin", post_id, post_url)
            
        except Exception as e:
            self.log_error(f"發文失敗: {e}")
            return PostResult(False, "linkedin", error=str(e))
    
    def _format_post(self, post: SocialPost) -> str:
        content = post.generated_content
        hashtags = ' '.join(post.hashtags)
        
        if content:
            return f"""🎉 [陽明交通大學 AI 學院獲獎公告]
🎉 [NYCU AI College Award Announcement]

{content.content_zh}

{content.content_en}

{hashtags}

#NYCU #ArtificialIntelligence #Research #Innovation #Award"""
        else:
            return f"""🎉 [陽明交通大學 AI 學院獲獎公告]

{post.title}

{post.content}

{hashtags}

#NYCU #ArtificialIntelligence #Research #Innovation #Award"""


class RedditAgent(BaseAgent):
    """Reddit 發文代理"""
    
    def __init__(self):
        super().__init__("RedditAgent")
        self.config = Config()
        self.reddit = None
        self._init_client()
    
    def _init_client(self):
        """初始化 Reddit 客戶端"""
        creds = self.config.get('reddit', {})
        
        if not all(creds.get(k) for k in ['client_id', 'client_secret', 'username', 'password']):
            self.log_warning("Reddit 憑證不完整")
            return
        
        try:
            self.reddit = praw.Reddit(
                client_id=creds.get('client_id'),
                client_secret=creds.get('client_secret'),
                username=creds.get('username'),
                password=creds.get('password'),
                user_agent=creds.get('user_agent', 'NYCUBot/1.0')
            )
            self.reddit.user.me()
            self.log_info("✅ Reddit 客戶端初始化成功")
        except Exception as e:
            self.log_error(f"Reddit 初始化失敗: {e}")
            self.reddit = None
    
    def _setup_handlers(self):
        self.register_handler(MessageType.POST_REQUEST, self._handle_post_request)
    
    async def _handle_post_request(self, message: AgentMessage):
        payload = message.payload
        post = payload.get('post')
        image_url = payload.get('image_url')
        subreddit = payload.get('subreddit', 'test')
        
        result = await self.post(post, subreddit, image_url)
        
        await self.send_message(
            receiver="MotherAgent",
            msg_type=MessageType.POST_RESULT,
            payload={'platform': 'reddit', 'result': result}
        )
    
    async def handle_message(self, message: AgentMessage):
        pass
    
    async def post(
        self,
        post: SocialPost,
        subreddit: str = "test",
        image_url: str = None
    ) -> PostResult:
        """發布 Reddit 貼文"""
        if not self.reddit:
            return PostResult(False, "reddit", error="客戶端未初始化")
        
        try:
            title = f"🎉 {post.title}"[:300]
            final_image_url = image_url or post.image_url
            
            if final_image_url:
                return await self._post_with_image(title, post, subreddit, final_image_url)
            else:
                return await self._post_text(title, post, subreddit)
                
        except Exception as e:
            self.log_error(f"發文失敗: {e}")
            return PostResult(False, "reddit", error=str(e))
    
    async def _post_with_image(
        self,
        title: str,
        post: SocialPost,
        subreddit: str,
        image_url: str
    ) -> PostResult:
        temp_file = None
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            file_ext = '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(response.content)
                temp_file = tmp.name
            
            subreddit_obj = self.reddit.subreddit(subreddit)
            submission = subreddit_obj.submit_image(title=title, image_path=temp_file)
            
            # 添加評論
            comment_text = self._format_comment(post)
            submission.reply(comment_text)
            
            self.log_info(f"✅ Reddit 發布成功: {submission.url}")
            return PostResult(True, "reddit", submission.id, submission.url)
            
        except Exception as e:
            self.log_error(f"圖片發布失敗: {e}")
            return await self._post_text(title, post, subreddit)
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    async def _post_text(
        self,
        title: str,
        post: SocialPost,
        subreddit: str
    ) -> PostResult:
        try:
            post_content = self._format_post(post)
            subreddit_obj = self.reddit.subreddit(subreddit)
            submission = subreddit_obj.submit(title=title, selftext=post_content)
            
            self.log_info(f"✅ Reddit 發布成功: {submission.url}")
            return PostResult(True, "reddit", submission.id, submission.url)
            
        except Exception as e:
            self.log_error(f"發文失敗: {e}")
            return PostResult(False, "reddit", error=str(e))
    
    def _format_post(self, post: SocialPost) -> str:
        content = post.generated_content
        hashtags = ', '.join([tag.replace('#', '') for tag in post.hashtags])
        
        if content:
            return f"""**🎉 {content.title_zh}**
**{content.title_en}**

{content.content_zh}

{content.content_en}

---

*此為陽明交通大學 AI 學院獲獎公告*
*NYCU AI College Award Announcement*

相關標籤 / Tags: {hashtags}
"""
        else:
            return f"""**🎉 {post.title}**

{post.content}

---

*此為陽明交通大學 AI 學院獲獎公告*

相關標籤: {hashtags}
"""
    
    def _format_comment(self, post: SocialPost) -> str:
        content = post.generated_content
        hashtags = ', '.join([tag.replace('#', '') for tag in post.hashtags])
        
        if content:
            return f"""{content.content_zh}

{content.content_en}

---

*NYCU AI College Award Announcement*

Tags: {hashtags}
"""
        else:
            return f"""{post.content}

---

*NYCU AI College Award Announcement*

Tags: {hashtags}
"""
