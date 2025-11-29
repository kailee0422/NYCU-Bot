# NYCU AI Award Announcement Multi-Agent System

🤖 基於 Multi-Agent 架構的社交媒體獲獎公告自動發布系統

## 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Agent System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐                                           │
│  │ InformationAgent │  監控 NYCU AI 網站獲獎公告                 │
│  └────────┬─────────┘                                           │
│           │ NEW_ANNOUNCEMENT                                     │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │   FatherAgent    │  接收公告，記錄並轉交                       │
│  └────────┬─────────┘                                           │
│           │ TASK_ASSIGNMENT                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │   MotherAgent    │  任務分配師，協調子代理                     │
│  └────────┬─────────┘                                           │
│           │                                                      │
│     ┌─────┴─────┐                                               │
│     │           │                                                │
│     ▼           ▼                                                │
│  ┌──────────┐  ┌─────────────────────────────────────────┐      │
│  │ Content  │  │           Platform Agents               │      │
│  │  Agent   │  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ │      │
│  │ (Ollama) │  │  │ Twitter │ │ Facebook │ │Instagram │ │      │
│  └────┬─────┘  │  └─────────┘ └──────────┘ └──────────┘ │      │
│       │        │  ┌──────────┐ ┌──────────┐              │      │
│       │        │  │ LinkedIn │ │  Reddit  │              │      │
│       │        │  └──────────┘ └──────────┘              │      │
│       │        └─────────────────────────────────────────┘      │
│       │ CONTENT_GENERATED                                       │
│       └──────────────────────────────────────────────────►      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 代理說明

| 代理名稱 | 職責 |
|---------|------|
| **InformationAgent** | 監控 https://ai.nycu.edu.tw/category/hot-news/ 網站，發現新的獲獎公告 |
| **FatherAgent** | 接收 InformationAgent 的通知，記錄統計並轉交給 MotherAgent |
| **MotherAgent** | 任務分配師，協調 ContentAgent 生成內容後分配給各平台代理發布 |
| **ContentAgent** | 使用 Ollama (DeepSeek-R1 7B) 生成中英文恭喜文章和 hashtags |
| **TwitterAgent** | 發布到 Twitter/X |
| **FacebookAgent** | 發布到 Facebook 粉絲專頁 |
| **InstagramAgent** | 發布到 Instagram |
| **LinkedInAgent** | 發布到 LinkedIn |
| **RedditAgent** | 發布到 Reddit |

## 安裝步驟

### 1. 安裝 Python 依賴

```bash
cd nycu_bot
pip install -r requirements.txt
```

### 2. 安裝 Ollama (Windows)

1. 前往 https://ollama.com/download 下載 Windows 版本
2. 安裝後，開啟終端機執行：

```bash
# 下載 DeepSeek-R1 7B 模型
ollama pull deepseek-r1:7b

# 確認模型已安裝
ollama list

# 啟動 Ollama 服務 (通常會自動啟動)
ollama serve
```

### 3. 設定社交媒體憑證

```bash
python main.py setup
```

按照提示輸入各平台的 API 憑證：
- **Facebook**: Page ID 和 Access Token
- **Instagram**: Access Token 和 Instagram Account ID
- **Twitter**: API Key, API Secret, Access Token, Access Token Secret
- **Reddit**: Client ID, Client Secret, Username, Password
- **LinkedIn**: Access Token
- **Ollama**: Base URL (預設 http://localhost:11434) 和 Model 名稱

## 使用方式

### 測試網站掃描
```bash
python main.py test
```
只掃描網站顯示獲獎公告，不發布

### 測試 LLM 內容生成
```bash
python main.py test-llm
```
測試 Ollama 是否正常運作並生成內容

### 執行一次
```bash
python main.py run
```
執行一次完整的掃描和發布流程

### 持續監控
```bash
# 預設每 30 分鐘檢查一次
python main.py start

# 自訂檢查間隔（分鐘）
python main.py start 60
```

## 設定檔說明

### social_config.json

```json
{
  "twitter": {
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "access_token": "your_access_token",
    "access_token_secret": "your_access_token_secret"
  },
  "reddit": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "username": "your_username",
    "password": "your_password",
    "user_agent": "NYCUBot/1.0"
  },
  "facebook": {
    "page_id": "your_page_id",
    "access_token": "your_access_token"
  },
  "instagram": {
    "access_token": "your_access_token",
    "instagram_account_id": "your_instagram_account_id"
  },
  "linkedin": {
    "access_token": "your_access_token"
  },
  "ollama": {
    "base_url": "http://localhost:11434",
    "model": "deepseek-r1:7b"
  }
}
```

## 檔案結構

```
nycu_bot/
├── main.py                 # 主程式入口
├── models.py               # 資料模型定義
├── config.py               # 設定和工具函數
├── base_agent.py           # 基礎代理類別和訊息匯流排
├── information_agent.py    # 資訊代理（網站爬蟲）
├── coordinator_agents.py   # Father/Mother 協調代理
├── content_agent.py        # 內容生成代理（LangChain + Ollama）
├── social_agents_part1.py  # Twitter, Facebook, Instagram 代理
├── social_agents_part2.py  # LinkedIn, Reddit 代理
├── requirements.txt        # Python 依賴
├── social_config.json      # 憑證設定（自動生成）
├── processed_awards.json   # 已處理公告記錄（自動生成）
└── award_bot.log           # 日誌檔案（自動生成）
```

## 訊息流程

1. **InformationAgent** 掃描網站發現新公告
2. 發送 `NEW_ANNOUNCEMENT` 訊息給 **FatherAgent**
3. **FatherAgent** 記錄並發送 `TASK_ASSIGNMENT` 給 **MotherAgent**
4. **MotherAgent** 分配給 **ContentAgent** 生成內容
5. **ContentAgent** 完成後發送 `CONTENT_GENERATED` 回 **MotherAgent**
6. **MotherAgent** 發送 `POST_REQUEST` 給各平台代理
7. 各平台代理完成後發送 `POST_RESULT` 回 **MotherAgent**
8. **MotherAgent** 彙總結果並通知 **FatherAgent**

## 注意事項

1. **Ollama 必須在本地運行**: 確保 Windows 上的 Ollama 服務已啟動
2. **API 速率限制**: Twitter 有嚴格的速率限制，系統會自動等待
3. **Instagram 需要圖片**: 如果公告沒有圖片，Instagram 發布會跳過
4. **Facebook/Instagram**: 需要 Meta Business Suite 權限
5. **LinkedIn**: 需要 OAuth 2.0 授權

## 故障排除

### Ollama 連線失敗
```bash
# 確認 Ollama 正在運行
curl http://localhost:11434/api/tags

# 如果沒有回應，重新啟動 Ollama
ollama serve
```

### 內容生成超時
- 檢查 Ollama 模型是否正確載入
- 考慮使用更小的模型（如 `deepseek-r1:1.5b`）

### 社交媒體 API 錯誤
- 確認 API 憑證正確
- 檢查 Token 是否過期
- 確認應用程式權限設定

## 授權

MIT License
