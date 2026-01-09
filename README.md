# 語音轉文字服務 (Speech to Text)

基於 Groq Whisper large-v3 的高精度語音辨識服務，支援多種音訊來源和輸出格式。

🌐 **線上服務**: https://defintek.io/s2t

## ✨ 功能特點

### 語音辨識
- **Groq Whisper large-v3** - 高精度雲端語音辨識引擎
- **自動語言偵測** - 支援多國語言
- **繁體中文輸出** - 使用 OpenCC 自動轉換為台灣繁體中文

### 支援來源
- 📁 **本地檔案上傳** - 支援 MP3、WAV、M4A、MP4、MOV、AVI 等格式
- 🎬 **YouTube 影片** - 直接輸入影片連結
- 📘 **Facebook 影片** - 支援 Facebook 影片/Reels 連結
- ☁️ **Google Drive** - 支援 Google Drive 音訊/視訊連結

### 輸出格式
- **TXT** - 純文字檔案
- **SRT** - 字幕檔案（含時間軸）
- **VTT** - WebVTT 字幕格式
- **TSV** - Tab 分隔值格式
- **JSON** - 結構化資料格式

### 進階功能
- **LLM 文字校正** - 使用 Llama 3.3 70B 自動修正錯字和標點符號
- **大檔案支援** - 自動壓縮超過 25MB 的音訊檔案
- **拖放上傳** - 支援拖放檔案上傳
- **即時進度** - 顯示處理進度

## 🛠️ 技術架構

### 後端
- **FastAPI** - Python 非同步 Web 框架
- **Groq API** - Whisper large-v3 語音辨識 + Llama 3.3 70B 文字校正
- **OpenCC** - 簡體轉繁體中文轉換
- **yt-dlp** - YouTube/Facebook 影片下載
- **ffmpeg** - 音訊處理與壓縮

### 前端
- **React** - 使用者介面
- **TailwindCSS** - 樣式框架
- **Axios** - HTTP 客戶端

### 部署
- **Uvicorn** - ASGI 伺服器
- **Apache** - 反向代理
- **Systemd** - 服務管理

## 📦 安裝部署

### 系統需求
- Python 3.10+
- Node.js 20+ (yt-dlp JavaScript runtime)
- ffmpeg
- Apache2

### 環境設定

1. **建立虛擬環境**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **設定環境變數**
```bash
# 建立 .env 檔案
cat > app/.env << EOL
GROQ_API_KEY=your_groq_api_key_here
EOL
```

3. **建構前端**
```bash
cd frontend
npm install
npm run build
```

4. **啟動服務**
```bash
./deploy.sh
```

### Systemd 服務

```bash
# 複製服務檔案
sudo cp s2t.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable s2t
sudo systemctl start s2t
```

### Apache 設定

```bash
sudo cp s2t_apache.conf /etc/apache2/sites-available/
sudo a2ensite s2t_apache.conf
sudo systemctl restart apache2
```

## 📖 使用說明

1. 開啟 https://defintek.io/s2t
2. 選擇輸出格式（TXT、SRT、VTT、TSV、JSON）
3. 上傳檔案或貼上連結：
   - **本地檔案**: 點擊上傳或拖放檔案
   - **YouTube**: 貼上影片連結 (如 `https://www.youtube.com/watch?v=...`)
   - **Facebook**: 貼上影片連結 (如 `https://www.facebook.com/share/r/...`)
   - **Google Drive**: 貼上分享連結
4. 等待處理完成
5. 下載轉換結果 (ZIP 壓縮檔)

## 🔧 管理功能

### 清空暫存檔案
1. 點擊「清空暫存檔案」按鈕
2. 輸入管理員密碼
3. 確認清空

### 服務管理
```bash
# 查看服務狀態
sudo systemctl status s2t

# 重啟服務
sudo systemctl restart s2t

# 查看日誌
sudo journalctl -u s2t -f
```

## 📝 更新記錄

### 2026-01-10
- 升級至 Groq Whisper large-v3
- 新增 OpenCC 簡體轉繁體中文
- 新增 Facebook 影片連結支援
- 前端翻譯為繁體中文
- 新增 LLM 文字校正功能

### 2025-06-22
- 初始版本發布
- 支援本地 Whisper 模型
- 支援 YouTube 和 Google Drive 連結

## 📄 授權

MIT License
