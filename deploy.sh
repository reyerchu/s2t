#!/bin/bash

# 錯誤處理
set -e

# 定義顏色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}開始部署 Speech to Text 應用程序...${NC}"

# 部署目錄
DEPLOY_DIR="/var/www/defintek.io/s2t"

# 建立目錄
echo "建立部署目錄..."
sudo mkdir -p $DEPLOY_DIR
sudo chown $(whoami):www-data $DEPLOY_DIR

# 複製應用程序文件
echo "複製應用程序文件..."
cp -r app $DEPLOY_DIR/
cp -r temp $DEPLOY_DIR/ || mkdir -p $DEPLOY_DIR/temp

# 建立虛擬環境
echo "建立 Python 虛擬環境..."
python3 -m venv $DEPLOY_DIR/.venv
source $DEPLOY_DIR/.venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 構建前端
echo "構建前端應用..."
cd frontend
npm install
npm run build
cd ..

# 複製前端構建文件
echo "複製前端構建文件..."
mkdir -p $DEPLOY_DIR/frontend
cp -r frontend/build $DEPLOY_DIR/frontend/

# 設置權限
echo "設置權限..."
sudo chown -R www-data:www-data $DEPLOY_DIR
sudo chmod -R 755 $DEPLOY_DIR

# 複製 systemd 服務文件
echo "設置 systemd 服務..."
sudo cp s2t.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable s2t.service
sudo systemctl start s2t.service

# 複製 Apache 配置
echo "配置 Apache..."
sudo cp s2t_apache.conf /etc/apache2/sites-available/
sudo a2ensite s2t_apache.conf
sudo a2enmod proxy proxy_http rewrite
sudo systemctl restart apache2

echo -e "${GREEN}部署完成！${NC}"
echo "應用程序現在應該可以通過 http://defintek.io/s2t 訪問了" 