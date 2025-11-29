#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定檔和工具函數
"""
import os
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse, quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('award_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def encode_image_url(url: str) -> str:
    """
    Properly encode image URL for API requests.
    Chinese characters and special characters need to be percent-encoded.
    """
    if not url:
        return url

    parsed = urlparse(url)
    path_parts = parsed.path.split('/')
    encoded_parts = [quote(part, safe='') for part in path_parts]
    encoded_path = '/'.join(encoded_parts)
    encoded_url = f"{parsed.scheme}://{parsed.netloc}{encoded_path}"

    if parsed.query:
        encoded_url += f"?{parsed.query}"

    return encoded_url


class Config:
    """設定管理類別"""
    
    DEFAULT_CONFIG = {
        "twitter": {
            "api_key": "",
            "api_secret": "",
            "access_token": "",
            "access_token_secret": ""
        },
        "reddit": {
            "client_id": "",
            "client_secret": "",
            "username": "",
            "password": "",
            "user_agent": "NYCUBot/1.0"
        },
        "facebook": {
            "page_id": "",
            "access_token": ""
        },
        "instagram": {
            "access_token": "",
            "instagram_account_id": ""
        },
        "linkedin": {
            "access_token": ""
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "deepseek-r1:7b"
        }
    }
    
    def __init__(self, config_file: str = "social_config.json"):
        self.config_file = config_file
        self.credentials = self._load_or_create_config()
    
    def _load_or_create_config(self) -> Dict:
        """載入或建立設定檔"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 確保 ollama 設定存在
                if 'ollama' not in config:
                    config['ollama'] = self.DEFAULT_CONFIG['ollama']
                    self._save_config(config)
                return config
        else:
            self._save_config(self.DEFAULT_CONFIG)
            logger.info(f"已建立預設設定檔: {self.config_file}")
            return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self, config: Dict):
        """儲存設定檔"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get(self, key: str, default=None):
        """取得設定值"""
        return self.credentials.get(key, default)
    
    def update(self, key: str, value: Dict):
        """更新設定"""
        self.credentials[key] = value
        self._save_config(self.credentials)


class ProcessedTracker:
    """追蹤已處理的公告"""
    
    def __init__(self, file_path: str = "processed_awards.json"):
        self.file_path = file_path
        self.processed_ids = self._load()
    
    def _load(self) -> set:
        """載入已處理的ID"""
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        return set()
    
    def _save(self):
        """儲存已處理的ID"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(list(self.processed_ids), f, ensure_ascii=False)
    
    def is_processed(self, announcement_id: str) -> bool:
        """檢查是否已處理"""
        return announcement_id in self.processed_ids
    
    def mark_processed(self, announcement_id: str):
        """標記為已處理"""
        self.processed_ids.add(announcement_id)
        self._save()
    
    def clear(self):
        """清除所有記錄"""
        self.processed_ids.clear()
        self._save()
