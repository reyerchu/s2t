# 音頻轉文字服務 (Speech-to-Text Service)

這是一個基於 Whisper 和 FastAPI 的音頻轉文字服務，支持多種輸出格式。

## 功能特點

- 支持多種音頻/視頻格式輸入
- 使用 Whisper 進行高質量語音識別
- 支持中文繁體識別
- 輸出多種格式：
  - `.txt`: 純文字輸出
  - `.srt`: 帶時間碼的字幕文件
  - `.vtt`: 網頁視頻字幕格式
  - `.tsv`: 可用 Excel 打開的表格格式
  - `.json`: 完整的 Whisper 輸出結果

## 安裝要求

- Python 3.9+
- ffmpeg
- Node.js 14+ (前端開發)

## 安裝步驟

1. 克隆專案：
```bash
git clone [repository-url]
cd [project-directory]
```

2. 安裝 Python 依賴：
```bash
pip install -r requirements.txt
```

3. 安裝前端依賴：
```bash
cd frontend
npm install
```

## 運行服務

1. 啟動後端服務：
```bash
uvicorn app.main:app --reload
```

2. 啟動前端服務：
```bash
cd frontend
npm start
```

## Docker 部署

使用 Docker 構建和運行：

```bash
docker build -t speech-to-text .
docker run -p 8000:8000 speech-to-text
```

## API 使用

### 轉錄音頻

POST `/transcribe`

請求：
- Content-Type: multipart/form-data
- Body: file (音頻/視頻文件)

響應：
```json
{
  "status": "success",
  "data": {
    "txt": "純文字內容",
    "srt": "SRT 格式內容",
    "vtt": "VTT 格式內容",
    "tsv": "TSV 格式內容",
    "json": {
      // Whisper 完整輸出
    }
  }
}
```

## 開發計劃

- [ ] 添加用戶認證系統
- [ ] 實現文件存儲（S3）
- [ ] 添加任務隊列系統
- [ ] 添加進度顯示功能
- [ ] 實現計費系統
- [ ] 添加錯誤處理和日誌記錄
- [ ] 優化音頻預處理參數
- [ ] 添加批量處理功能
- [ ] 實現字幕編輯界面

## 許可證

MIT 