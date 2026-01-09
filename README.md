# 影音轉文字服務 (Speech to Text)

這是一個基於 Whisper 的語音識別應用程序，可以將音頻/視頻文件轉換為多種格式的文字內容。

## 功能

- 支持多種格式的音頻/視頻文件上傳
- 支持多種輸出格式：TXT、SRT、VTT、TSV、JSON
- 拖放上傳功能
- 實時處理進度顯示
- 清空暫存文件功能
- 美觀的用戶界面

## 技術棧

- 前端：React, TailwindCSS, Axios
- 後端：FastAPI, Whisper, FFmpeg
- 部署：Apache, Systemd, Python venv

## 部署說明

本應用已配置為在 http://defintek.io/s2t 下運行。

### 自動部署

使用提供的部署腳本：

```bash
./deploy.sh
```

### 手動部署

1. 準備環境

```bash
# 建立部署目錄
sudo mkdir -p /var/www/defintek.io/s2t
sudo chown $(whoami):www-data /var/www/defintek.io/s2t

# 複製應用程序文件
cp -r app /var/www/defintek.io/s2t/
mkdir -p /var/www/defintek.io/s2t/temp

# 建立虛擬環境
python3 -m venv /var/www/defintek.io/s2t/.venv
source /var/www/defintek.io/s2t/.venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

2. 構建前端

```bash
cd frontend
npm install
npm run build
mkdir -p /var/www/defintek.io/s2t/frontend
cp -r build /var/www/defintek.io/s2t/frontend/
```

3. 配置服務

```bash
# 複製 systemd 服務文件
sudo cp s2t.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable s2t.service
sudo systemctl start s2t.service

# 複製 Apache 配置
sudo cp s2t_apache.conf /etc/apache2/sites-available/
sudo a2ensite s2t_apache.conf
sudo a2enmod proxy proxy_http rewrite
sudo systemctl restart apache2
```

## 使用說明

1. 訪問 http://defintek.io/s2t
2. 選擇所需的輸出格式
3. 上傳音頻/視頻文件（支持拖放）
4. 等待處理完成
5. 下載轉換結果

## 管理員功能

清空暫存文件：
1. 點擊「清空暫存檔案」按鈕
2. 輸入管理員密碼（預設：admin123）
3. 點擊確認 