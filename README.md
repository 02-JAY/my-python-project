# 🤖 LINE 智慧助理與電商推薦系統 (Python LINE Bot)

本專案為基於 **Python Flask**、**LINE Messaging API SDK v3** 與 **LangChain (Gemini 2.5 Flash)** 開發的多功能智慧聊天機器人。整合即時氣象查詢、多模態音訊/影像辨識、非同步 GCS 雲端備份，並作為 **Spring Boot 購物商城** 的行銷推薦與自動發券前台介面。

---

## 🚀 核心功能與特色

* **🧠 LangChain ReAct AI Agent**：
    * 採用 Google Gemini 2.5 Flash 核心模型，具備智慧意圖判斷與多工具動態調用機制。
    * 整合 Firestore 保存使用者對話歷史（Context-aware Conversation）。

* **🛒 Spring Boot 電商後端深度整合**：
    * **智慧商品推薦**：透過 RESTful API 調用 Java 後端智慧推薦服務，自動推論商品分類（香氛防潮、除濕家電、電子防潮箱）。
    * **心理測驗活動自動發券**：支援將行銷活動限定折扣碼（如 `LINE_QUIZ_2026`）自動歸戶至 Java 後端資料庫，享高併發原子防超賣保護。

* **🎙️ 多模態語音與影像處理**：
    * **語音辨識**：支援 LINE 語音訊息接收，結合 Gemini Multimodal 與 GCP Speech-to-Text 轉文字。
    * **非同步背景備份**：採用多執行緒（`threading`）在背景將音訊/圖片非同步上傳至 Google Cloud Storage (GCS)，確保 LINE 回覆低延遲。
    * **Google Vision API**：支援圖片標籤辨識（Label Detection）。

* **🌤️ CWA 即時氣象雷達**：
    * 串接中央氣象署 OpenData API，支援輸入地名或直接傳送 GPS 定位查詢最近測站天氣。

---

## 🛠️ 技術棧 (Tech Stack)

* **程式語言與框架**：Python 3.10+, Flask
* **LINE SDK**：line-bot-sdk v3 (MessagingApi, WebhookHandler)
* **LLM & AI Agent**：LangChain, langchain-google-genai (Gemini 2.5 Flash)
* **GCP 雲端服務**：Cloud Storage (GCS), Firestore, Cloud Vision API, Cloud Speech-to-Text
* **地理與氣象**：Geopy (Nominatim), CWA OpenData API
* **非同步處理**：Python Threading

---

## ⚙️ 環境配置與啟動

### 1. 安裝相依套件
```bash
pip install flask requests pillow geopy google-cloud-storage google-cloud-firestore google-cloud-vision google-cloud-speech langchain langchain-google-genai line-bot-sdk
